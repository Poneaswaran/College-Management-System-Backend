from rest_framework import generics, status, permissions
from rest_framework.response import Response
from .serializers import InvigilationAttendanceSerializer
from .models import ExamSchedule
from .services import SeatingService
from core.auth import JWTAuthentication

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
