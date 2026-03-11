from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.utils import timezone
from .models import FacultyAttendance
from .serializers import FacultyPunchSerializer, FacultyAttendanceReportSerializer
from core.auth import JWTAuthentication

class FacultyPunchInView(generics.CreateAPIView):
    """
    API for faculty to punch in for the day.
    """
    serializer_class = FacultyPunchSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        if user.role.code != 'FACULTY' and user.role.code != 'HOD':
             return Response({"error": "Only faculty/HOD can punch in."}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.now().date()
        attendance, created = FacultyAttendance.objects.get_or_create(
            faculty=user,
            date=today
        )
        
        if attendance.punch_in_time:
            return Response({"error": "Already punched in for today."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(attendance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Set punch in time
        attendance.punch_in_time = timezone.now()
        
        # Basic late check (e.g., after 9:30 AM)
        if attendance.punch_in_time.time() > timezone.datetime.strptime("09:30:00", "%H:%M:%S").time():
            attendance.is_late = True
            
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

class FacultyPunchOutView(generics.UpdateAPIView):
    """
    API for faculty to punch out for the day.
    """
    serializer_class = FacultyPunchSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        today = timezone.now().date()
        
        try:
            attendance = FacultyAttendance.objects.get(faculty=user, date=today)
        except FacultyAttendance.DoesNotExist:
            return Response({"error": "No punch-in record found for today."}, status=status.HTTP_400_BAD_REQUEST)
            
        if attendance.punch_out_time:
            return Response({"error": "Already punched out for today."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(attendance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        attendance.punch_out_time = timezone.now()
        serializer.save()
        
        return Response(serializer.data, status=status.HTTP_200_OK)

class HODFacultyAttendanceView(generics.ListAPIView):
    """
    API for HOD to view faculty attendance in their department.
    """
    serializer_class = FacultyAttendanceReportSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role.code != 'HOD' and not user.is_superuser:
            return FacultyAttendance.objects.none()
            
        queryset = FacultyAttendance.objects.all()
        
        if not user.is_superuser:
            queryset = queryset.filter(faculty__department=user.department)
            
        date = self.request.query_params.get('date')
        if date:
            queryset = queryset.filter(date=date)
            
        return queryset
