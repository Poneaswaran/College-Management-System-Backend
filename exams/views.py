from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from .serializers import InvigilationAttendanceSerializer, ArrearResultSerializer
from .models import ExamSchedule, ExamResult
from .services import SeatingService
from core.auth import JWTAuthentication
from configuration.services.feature_flag_service import FeatureFlagService

class MarkInvigilationAttendanceView(generics.GenericAPIView):
    """
    API view for faculty to mark attendance for exams they are invigilating.
    """
    serializer_class = InvigilationAttendanceSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        schedule_id = serializer.validated_data['schedule_id']
        attendance_data = serializer.validated_data['attendance_data']
        
        try:
            schedule = ExamSchedule.objects.get(id=schedule_id)
        except ExamSchedule.DoesNotExist:
            return Response(
                {"error": "Exam schedule not found."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Permission check: Only the assigned invigilator, HOD, or Admin can mark attendance
        user = request.user
        is_invigilator = schedule.invigilator == user
        is_privileged = user.role.code in ['HOD', 'ADMIN']
        
        if not (is_invigilator or is_privileged):
            return Response(
                {"error": "You do not have permission to mark attendance for this exam."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        try:
            SeatingService.bulk_mark_exam_attendance(
                schedule_id=schedule_id,
                attendance_data=attendance_data,
                marked_by=user
            )
            return Response(
                {"message": "Attendance marked successfully."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class HODArrearListView(generics.ListAPIView):
    """
    API view for HOD to list all students in their department who have arrears (failed subjects).
    """
    serializer_class = ArrearResultSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not FeatureFlagService.is_enabled("hod_arrears"):
            raise PermissionDenied("HOD Arrears feature is currently disabled.")
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if user.role.code != 'HOD':
            return ExamResult.objects.none()
        
        try:
            department = user.faculty_profile.department
        except AttributeError:
            return ExamResult.objects.none()
            
        return ExamResult.objects.filter(
            student__department=department,
            is_pass=False
        ).select_related(
            'student', 
            'student__user', 
            'schedule', 
            'schedule__subject', 
            'schedule__exam'
        ).order_by('student__register_number', 'schedule__date')
