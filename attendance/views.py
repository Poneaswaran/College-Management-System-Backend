from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.utils import timezone
from .models import FacultyAttendance, AttendanceSession, StudentAttendance, AttendanceReport
from .serializers import (
    FacultyPunchSerializer, 
    FacultyAttendanceReportSerializer,
    StudentAttendanceReportSerializer,
    StudentAttendanceHistorySerializer,
    ActiveAttendanceSessionSerializer,
    StudentMarkAttendanceSerializer
)
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


class StudentAttendanceReportsView(generics.ListAPIView):
    """
    API for students to view their attendance reports.
    """
    serializer_class = StudentAttendanceReportSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from configuration.services.feature_flag_service import FeatureFlagService
        if not FeatureFlagService.is_enabled("attendance_analytics"):
            return AttendanceReport.objects.none()

        user = self.request.user
        if not hasattr(user, 'student_profile'):
            return AttendanceReport.objects.none()
            
        student = user.student_profile
        from profile_management.models import Semester
        from timetable.models import TimetableEntry, CombinedClassSession
        
        semester = Semester.objects.filter(is_current=True).first()
        if not semester:
            return AttendanceReport.objects.none()

        # Find all unique subjects for this student's section this semester
        # to ensure the reports exist and are updated.
        section = student.section
        if section:
            subject_ids = TimetableEntry.objects.filter(
                section=section,
                semester=semester,
                is_active=True
            ).values_list('subject_id', flat=True).distinct()
            
            combined_subject_ids = CombinedClassSession.objects.filter(
                sections=section,
                semester=semester,
                is_active=True
            ).values_list('subject_id', flat=True).distinct()
            
            all_subject_ids = set(list(subject_ids) + list(combined_subject_ids))
            
            for subject_id in all_subject_ids:
                report, created = AttendanceReport.objects.get_or_create(
                    student=student,
                    subject_id=subject_id,
                    semester=semester
                )
                if created or (timezone.now() - report.last_calculated).days > 0:
                    report.calculate()

        return AttendanceReport.objects.filter(
            student=student,
            semester=semester
        ).select_related('subject', 'semester').order_by('-attendance_percentage')


class StudentAttendanceHistoryView(generics.ListAPIView):
    """
    API for students to view their attendance log history.
    """
    serializer_class = StudentAttendanceHistorySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from configuration.services.feature_flag_service import FeatureFlagService
        if not FeatureFlagService.is_enabled("attendance_analytics"):
            return StudentAttendance.objects.none()

        user = self.request.user
        if not hasattr(user, 'student_profile'):
            return StudentAttendance.objects.none()
            
        student = user.student_profile
        queryset = StudentAttendance.objects.filter(student=student)
        
        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(session__timetable_entry__subject_id=subject_id)
                | Q(session__combined_session__subject_id=subject_id)
            )
            
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(session__date__gte=start_date)
            
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(session__date__lte=end_date)
            
        return queryset.select_related(
            'session__timetable_entry__subject',
            'session__combined_session__subject',
            'session__timetable_entry__period_definition',
            'session__combined_session__period_definition'
        ).order_by('-session__date', '-marked_at')


class ActiveStudentSessionsView(generics.ListAPIView):
    """
    API for students to fetch today's active sessions open for self-marking.
    """
    serializer_class = ActiveAttendanceSessionSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'student_profile'):
            return AttendanceSession.objects.none()
            
        student = user.student_profile
        today = timezone.now().date()
        from django.db.models import Q
        
        sessions = AttendanceSession.objects.filter(
            Q(timetable_entry__section=student.section) | Q(combined_session__sections=student.section),
            date=today,
            status='ACTIVE'
        ).distinct().select_related(
            'timetable_entry__subject',
            'timetable_entry__faculty',
            'timetable_entry__period_definition',
            'combined_session__subject',
            'combined_session__faculty',
            'combined_session__period_definition'
        ).order_by(
            'timetable_entry__period_definition__start_time',
            'combined_session__period_definition__start_time'
        )
        
        # Only return sessions that are currently active (within the time window)
        active_sessions = [s for s in sessions if s.is_active]
        return active_sessions


class StudentMarkAttendanceView(generics.GenericAPIView):
    """
    API for students to submit and mark their own attendance via multipart selfie image and GPS coordinates.
    """
    serializer_class = StudentMarkAttendanceSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    from rest_framework.parsers import MultiPartParser, FormParser
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        from configuration.services.feature_flag_service import FeatureFlagService
        if not FeatureFlagService.is_enabled("attendance_analytics"):
            return Response({"error": "Attendance marking is not enabled for this tenant."}, status=status.HTTP_403_FORBIDDEN)

        user = request.user
        if not hasattr(user, 'student_profile'):
            return Response({"error": "Only students can mark attendance."}, status=status.HTTP_403_FORBIDDEN)
            
        student = user.student_profile
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        session_id = serializer.validated_data['session_id']
        image_data = serializer.validated_data['image_data']  # File object from serializer.ImageField
        latitude = serializer.validated_data.get('latitude')
        longitude = serializer.validated_data.get('longitude')
        device_info = serializer.validated_data.get('device_info', {})
        
        # Fetch active session
        try:
            session = AttendanceSession.objects.select_related(
                'timetable_entry__section',
                'timetable_entry__subject',
                'timetable_entry__semester',
                'combined_session__subject',
                'combined_session__semester'
            ).get(id=session_id)
        except AttendanceSession.DoesNotExist:
            return Response({"error": "Attendance session not found."}, status=status.HTTP_404_NOT_FOUND)
            
        # Validate marking rules
        from .validators import AttendanceValidator
        is_valid, error_message = AttendanceValidator.validate_student_marking(
            session,
            student,
            image_file=image_data
        )
        if not is_valid:
            return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)

        # Convert coordinates to Decimal
        from decimal import Decimal, ROUND_HALF_UP
        def to_dec(val):
            if val is None:
                return None
            return Decimal(str(val)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

        # Save/update attendance record
        from .models import StudentAttendance, AttendanceReport
        attendance, created = StudentAttendance.objects.update_or_create(
            session=session,
            student=student,
            defaults={
                'status': 'PRESENT',
                'attendance_image': image_data,
                'marked_at': timezone.now(),
                'latitude': to_dec(latitude),
                'longitude': to_dec(longitude),
                'device_info': device_info,
                'is_manually_marked': False
            }
        )
        
        # Update attendance report
        AttendanceReport.update_for_student_subject(
            student=student,
            subject=session.subject,
            semester=session.semester
        )
        
        return Response({
            "success": True,
            "message": "Attendance marked successfully" if created else "Attendance updated successfully",
            "attendance_id": attendance.id
        }, status=status.HTTP_200_OK)

