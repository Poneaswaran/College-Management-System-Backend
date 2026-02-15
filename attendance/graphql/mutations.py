"""
GraphQL Mutations for Attendance System
"""
import strawberry
from typing import Optional
from datetime import date
from strawberry.types import Info
from django.utils import timezone
from django.core.files.base import ContentFile
import base64

from attendance.models import AttendanceSession, StudentAttendance, AttendanceReport
from attendance.validators import AttendanceValidator
from attendance.utils import auto_mark_absent_students
from attendance.graphql.types import (
    AttendanceSessionType,
    StudentAttendanceType,
    AttendanceReportType,
    MarkAttendanceInput,
    OpenSessionInput,
    BlockSessionInput,
    ManualMarkAttendanceInput,
    MarkAttendanceResponse
)
from core.graphql.auth import require_auth


@strawberry.type
class AttendanceMutation:
    """Attendance-related mutations"""
    
    @strawberry.mutation
    @require_auth
    def open_attendance_session(
        self,
        info: Info,
        input: OpenSessionInput
    ) -> AttendanceSessionType:
        """
        Faculty opens an attendance session
        Creates or activates a session for marking attendance
        """
        user = info.context.request.user
        
        # Check if user is faculty
        if user.role.name != 'FACULTY':
            raise Exception("Only faculty can open attendance sessions")
        
        # Get timetable entry
        from timetable.models import TimetableEntry
        try:
            timetable_entry = TimetableEntry.objects.get(id=input.timetable_entry_id)
        except TimetableEntry.DoesNotExist:
            raise Exception("Timetable entry not found")
        
        # Validate
        is_valid, error_message = AttendanceValidator.validate_session_opening(
            timetable_entry,
            input.date,
            user
        )
        
        if not is_valid:
            raise Exception(error_message)
        
        # Create or get session
        session, created = AttendanceSession.objects.get_or_create(
            timetable_entry=timetable_entry,
            date=input.date,
            defaults={
                'status': 'ACTIVE',
                'opened_by': user,
                'opened_at': timezone.now(),
                'attendance_window_minutes': input.attendance_window_minutes or 10
            }
        )
        
        # If session exists but not active, activate it
        if not created:
            if session.status == 'SCHEDULED':
                session.status = 'ACTIVE'
                session.opened_by = user
                session.opened_at = timezone.now()
                session.attendance_window_minutes = input.attendance_window_minutes or session.attendance_window_minutes
                session.save()
            elif session.status in ['BLOCKED', 'CANCELLED']:
                raise Exception(f"Cannot open: {session.cancellation_reason}")
            elif session.status == 'CLOSED':
                raise Exception("Session is already closed")
        
        return session
    
    @strawberry.mutation
    @require_auth
    def mark_attendance(
        self,
        info: Info,
        input: MarkAttendanceInput
    ) -> MarkAttendanceResponse:
        """
        Student marks their attendance with image capture
        Requires camera photo (no gallery upload)
        """
        user = info.context.request.user
        
        # Check if user has student profile
        if not hasattr(user, 'student_profile'):
            raise Exception("Only students can mark attendance")
        
        student = user.student_profile
        
        # Get session
        try:
            session = AttendanceSession.objects.select_related(
                'timetable_entry__section'
            ).get(id=int(input.session_id))
        except AttendanceSession.DoesNotExist:
            raise Exception("Attendance session not found")
        
        # Validate
        is_valid, error_message = AttendanceValidator.validate_student_marking(
            session,
            student,
            image_file=input.image_data
        )
        
        if not is_valid:
            raise Exception(error_message)
        
        # Decode base64 image
        try:
            image_format, image_string = input.image_data.split(';base64,')
            ext = image_format.split('/')[-1]
            image_data = ContentFile(
                base64.b64decode(image_string),
                name=f'attendance_{student.id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.{ext}'
            )
        except Exception as e:
            raise Exception(f"Invalid image data: {str(e)}")
        
        # Create or update attendance record
        attendance, created = StudentAttendance.objects.update_or_create(
            session=session,
            student=student,
            defaults={
                'status': 'PRESENT',
                'attendance_image': image_data,
                'marked_at': timezone.now(),
                'latitude': input.latitude,
                'longitude': input.longitude,
                'device_info': input.device_info or {},
                'is_manually_marked': False
            }
        )
        
        # Update attendance report
        AttendanceReport.update_for_student_subject(
            student=student,
            subject=session.timetable_entry.subject,
            semester=session.timetable_entry.semester
        )
        
        return MarkAttendanceResponse(
            attendance=attendance,
            message="Attendance marked successfully" if created else "Attendance updated successfully",
            success=True
        )
    
    @strawberry.mutation
    @require_auth
    def close_attendance_session(
        self,
        info: Info,
        session_id: int
    ) -> AttendanceSessionType:
        """
        Faculty closes an attendance session
        Automatically marks absent students who didn't mark attendance
        """
        user = info.context.request.user
        
        # Check if user is faculty
        if user.role.name != 'FACULTY':
            raise Exception("Only faculty can close attendance sessions")
        
        # Get session
        try:
            session = AttendanceSession.objects.select_related(
                'timetable_entry__faculty'
            ).get(id=session_id)
        except AttendanceSession.DoesNotExist:
            raise Exception("Attendance session not found")
        
        # Check if faculty owns this session
        if session.timetable_entry.faculty.id != user.id:
            raise Exception("You can only close your own sessions")
        
        # Check if session is active
        if session.status != 'ACTIVE':
            raise Exception(f"Cannot close: Session is {session.status}")
        
        # Close session
        session.status = 'CLOSED'
        session.closed_at = timezone.now()
        session.save()
        
        # Auto-mark absent students
        auto_mark_absent_students(session)
        
        # Update all attendance reports for students in this session
        for attendance in session.student_attendances.all():
            AttendanceReport.update_for_student_subject(
                student=attendance.student,
                subject=session.timetable_entry.subject,
                semester=session.timetable_entry.semester
            )
        
        return session
    
    @strawberry.mutation
    @require_auth
    def block_attendance_session(
        self,
        info: Info,
        input: BlockSessionInput
    ) -> AttendanceSessionType:
        """
        Faculty/Admin blocks/cancels an attendance session
        Used when class is cancelled (teacher sick, holiday, etc.)
        """
        user = info.context.request.user
        
        # Get session
        try:
            session = AttendanceSession.objects.select_related(
                'timetable_entry__faculty'
            ).get(id=input.session_id)
        except AttendanceSession.DoesNotExist:
            raise Exception("Attendance session not found")
        
        # Validate
        is_valid, error_message = AttendanceValidator.validate_session_blocking(
            session,
            user
        )
        
        if not is_valid:
            raise Exception(error_message)
        
        # Block session
        session.status = 'BLOCKED'
        session.cancellation_reason = input.cancellation_reason
        session.blocked_by = user
        session.blocked_at = timezone.now()
        session.save()
        
        return session
    
    @strawberry.mutation
    @require_auth
    def reopen_blocked_session(
        self,
        info: Info,
        session_id: int
    ) -> AttendanceSessionType:
        """
        Reopen a blocked/cancelled session
        Only admin or faculty who teaches can reopen
        """
        user = info.context.request.user
        
        # Get session
        try:
            session = AttendanceSession.objects.select_related(
                'timetable_entry__faculty'
            ).get(id=session_id)
        except AttendanceSession.DoesNotExist:
            raise Exception("Attendance session not found")
        
        # Check if session is blocked
        if session.status not in ['BLOCKED', 'CANCELLED']:
            raise Exception("Only blocked/cancelled sessions can be reopened")
        
        # Check permissions
        can_reopen = False
        if user.role.name in ['ADMIN', 'SUPER_ADMIN']:
            can_reopen = True
        elif user.role.name == 'FACULTY' and session.timetable_entry.faculty.id == user.id:
            can_reopen = True
        
        if not can_reopen:
            raise Exception("You don't have permission to reopen this session")
        
        # Reopen session
        session.status = 'SCHEDULED'
        session.cancellation_reason = ''
        session.blocked_by = None
        session.blocked_at = None
        session.save()
        
        return session
    
    @strawberry.mutation
    @require_auth
    def manual_mark_attendance(
        self,
        info: Info,
        input: ManualMarkAttendanceInput
    ) -> StudentAttendanceType:
        """
        Faculty/Admin manually marks attendance for a student
        Used for corrections or when student can't mark (technical issues, etc.)
        """
        user = info.context.request.user
        
        # Get session and student
        try:
            session = AttendanceSession.objects.select_related(
                'timetable_entry__faculty'
            ).get(id=input.session_id)
        except AttendanceSession.DoesNotExist:
            raise Exception("Attendance session not found")
        
        from profile_management.models import StudentProfile
        try:
            student = StudentProfile.objects.get(id=input.student_id)
        except StudentProfile.DoesNotExist:
            raise Exception("Student not found")
        
        # Validate
        is_valid, error_message = AttendanceValidator.validate_manual_marking(
            session,
            student,
            user
        )
        
        if not is_valid:
            raise Exception(error_message)
        
        # Validate status
        if input.status not in ['PRESENT', 'ABSENT', 'LATE']:
            raise Exception("Invalid status. Must be PRESENT, ABSENT, or LATE")
        
        # Create or update attendance record
        attendance, created = StudentAttendance.objects.update_or_create(
            session=session,
            student=student,
            defaults={
                'status': input.status,
                'is_manually_marked': True,
                'marked_by': user,
                'marked_at': timezone.now(),
                'notes': input.notes or f"Manually marked {input.status.lower()} by {user.get_full_name()}"
            }
        )
        
        # Update attendance report
        AttendanceReport.update_for_student_subject(
            student=student,
            subject=session.timetable_entry.subject,
            semester=session.timetable_entry.semester
        )
        
        return attendance
    
    @strawberry.mutation
    @require_auth
    def bulk_mark_present(
        self,
        info: Info,
        session_id: int,
        student_ids: list[int]
    ) -> list[StudentAttendanceType]:
        """
        Bulk mark multiple students as present
        Only faculty teaching the class or admin
        """
        user = info.context.request.user
        
        # Get session
        try:
            session = AttendanceSession.objects.select_related(
                'timetable_entry__faculty',
                'timetable_entry__section'
            ).get(id=session_id)
        except AttendanceSession.DoesNotExist:
            raise Exception("Attendance session not found")
        
        # Check permissions
        if user.role.name not in ['ADMIN', 'SUPER_ADMIN']:
            if user.role.name != 'FACULTY' or session.timetable_entry.faculty.id != user.id:
                raise Exception("You don't have permission to mark attendance for this session")
        
        from profile_management.models import StudentProfile
        
        attendances = []
        for student_id in student_ids:
            try:
                student = StudentProfile.objects.get(id=student_id)
                
                # Verify student is in section
                if not session.timetable_entry.section.students.filter(id=student_id).exists():
                    continue
                
                # Create/update attendance
                attendance, created = StudentAttendance.objects.update_or_create(
                    session=session,
                    student=student,
                    defaults={
                        'status': 'PRESENT',
                        'is_manually_marked': True,
                        'marked_by': user,
                        'marked_at': timezone.now(),
                        'notes': f"Bulk marked present by {user.get_full_name()}"
                    }
                )
                attendances.append(attendance)
                
                # Update report
                AttendanceReport.update_for_student_subject(
                    student=student,
                    subject=session.timetable_entry.subject,
                    semester=session.timetable_entry.semester
                )
            except StudentProfile.DoesNotExist:
                continue
        
        return attendances
    
    @strawberry.mutation
    @require_auth
    def recalculate_attendance_report(
        self,
        info: Info,
        report_id: int
    ) -> AttendanceReportType:
        """
        Recalculate an attendance report
        Useful after manual corrections
        """
        user = info.context.request.user
        
        try:
            report = AttendanceReport.objects.get(id=report_id)
        except AttendanceReport.DoesNotExist:
            raise Exception("Attendance report not found")
        
        # Check permissions
        has_access = False
        if hasattr(user, 'student_profile') and user.student_profile.id == report.student.id:
            has_access = True
        elif user.role.name in ['ADMIN', 'SUPER_ADMIN', 'FACULTY']:
            has_access = True
        
        if not has_access:
            raise Exception("You don't have permission to access this report")
        
        # Recalculate
        report.calculate()
        
        return report
