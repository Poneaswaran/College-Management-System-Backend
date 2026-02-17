"""
Validators for Attendance System
"""
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q


class AttendanceValidator:
    """
    Validates attendance operations
    """
    
    @staticmethod
    def validate_session_opening(timetable_entry, date, faculty_user):
        """
        Validate if faculty can open attendance session
        
        Args:
            timetable_entry: TimetableEntry instance
            date: Date for the session
            faculty_user: User instance (faculty)
        
        Returns:
            tuple: (is_valid, error_message)
        """
        from attendance.models import AttendanceSession
        
        # Check if timetable entry is active
        if not timetable_entry.is_active:
            return False, "Timetable entry is not active"
        
        # Check if faculty is the assigned teacher
        if timetable_entry.faculty.id != faculty_user.id:
            return False, "You are not assigned to teach this class"
        
        # Check if date is valid (not too far in past or future)
        today = timezone.now().date()
        if date < today - timezone.timedelta(days=7):
            return False, "Cannot open attendance session for more than 7 days in the past"
        
        if date > today + timezone.timedelta(days=7):
            return False, "Cannot open attendance session for more than 7 days in the future"
        
        # Check if session already exists
        existing_session = AttendanceSession.objects.filter(
            timetable_entry=timetable_entry,
            date=date
        ).first()
        
        if existing_session:
            if existing_session.status in ['BLOCKED', 'CANCELLED']:
                return False, f"Session is {existing_session.status}. Reason: {existing_session.cancellation_reason}"
            elif existing_session.status == 'ACTIVE':
                return False, "Session is already active"
            elif existing_session.status == 'CLOSED':
                return False, "Session is already closed"
        
        return True, ""
    
    @staticmethod
    def validate_session_blocking(session, faculty_user):
        """
        Validate if faculty can block/cancel a session
        
        Args:
            session: AttendanceSession instance
            faculty_user: User instance
        
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check if user is the assigned faculty or admin
        if faculty_user.role.code not in ['ADMIN', 'HOD']:
            if session.timetable_entry.faculty.id != faculty_user.id:
                return False, "Only the assigned faculty or admin can block this session"
        
        # Check if session is already closed
        if session.status == 'CLOSED':
            # Allow blocking of closed sessions (for corrections)
            pass
        
        return True, ""
    
    @staticmethod
    def validate_student_marking(session, student_profile, image_file=None):
        """
        Validate if student can mark attendance
        
        Args:
            session: AttendanceSession instance
            student_profile: StudentProfile instance
            image_file: Uploaded image file (optional)
        
        Returns:
            tuple: (is_valid, error_message)
        """
        from attendance.models import StudentAttendance
        
        # Check if session is active
        if session.status != 'ACTIVE':
            if session.status in ['BLOCKED', 'CANCELLED']:
                return False, f"Class cancelled. Reason: {session.cancellation_reason or 'Not specified'}"
            elif session.status == 'CLOSED':
                return False, "Attendance session has been closed"
            elif session.status == 'SCHEDULED':
                return False, "Attendance session has not been opened yet"
        
        # Check if session is within time window
        if not session.can_mark_attendance:
            return False, "Attendance window has expired"
        
        # Check if student belongs to the section
        section = session.timetable_entry.section
        if not section.student_profiles.filter(id=student_profile.id).exists():
            return False, "You are not enrolled in this section"
        
        # Check if attendance already marked
        existing_attendance = StudentAttendance.objects.filter(
            session=session,
            student=student_profile
        ).first()
        
        if existing_attendance and existing_attendance.status == 'PRESENT':
            return False, "Attendance already marked for this session"
        
        # Validate image is provided
        if not image_file:
            return False, "Photo capture is required to mark attendance"
        
        return True, ""
    
    @staticmethod
    def validate_manual_marking(session, student_profile, faculty_user):
        """
        Validate if faculty can manually mark attendance
        
        Args:
            session: AttendanceSession instance
            student_profile: StudentProfile instance
            faculty_user: User instance (faculty/admin)
        
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check if user is faculty or admin
        if faculty_user.role.code not in ['FACULTY', 'ADMIN', 'HOD']:
            return False, "Only faculty or admin can manually mark attendance"
        
        # Check if faculty teaches this class (unless admin)
        if faculty_user.role.code not in ['ADMIN', 'HOD']:
            if session.timetable_entry.faculty.id != faculty_user.id:
                return False, "You can only manually mark attendance for classes you teach"
        
        # Check if student belongs to section
        section = session.timetable_entry.section
        if not section.students.filter(id=student_profile.id).exists():
            return False, "Student is not enrolled in this section"
        
        # Check if session is blocked
        if session.status in ['BLOCKED', 'CANCELLED']:
            return False, "Cannot mark attendance for blocked/cancelled sessions"
        
        return True, ""
    
    @staticmethod
    def validate_image_access(attendance, requesting_user):
        """
        Validate if user can access attendance image
        
        Args:
            attendance: StudentAttendance instance
            requesting_user: User instance
        
        Returns:
            tuple: (has_access, error_message)
        """
        # Student can view their own attendance image
        if hasattr(requesting_user, 'student_profile'):
            if requesting_user.student_profile.id == attendance.student.id:
                return True, ""
        
        # Faculty can view images of students in classes they teach
        if requesting_user.role.code == 'FACULTY':
            if attendance.session.timetable_entry.faculty.id == requesting_user.id:
                return True, ""
        
        # Admin can view all
        if requesting_user.role.code in ['ADMIN', 'HOD']:
            return True, ""
        
        return False, "You do not have permission to view this image"


class AttendanceReportValidator:
    """
    Validates attendance report operations
    """
    
    @staticmethod
    def validate_report_access(student_profile, subject, requesting_user):
        """
        Validate if user can access attendance report
        
        Args:
            student_profile: StudentProfile instance
            subject: Subject instance
            requesting_user: User instance
        
        Returns:
            tuple: (has_access, error_message)
        """
        # Student can view their own report
        if hasattr(requesting_user, 'student_profile'):
            if requesting_user.student_profile.id == student_profile.id:
                return True, ""
        
        # Parent can view their child's report
        if hasattr(requesting_user, 'parent_profile'):
            parent = requesting_user.parent_profile
            if parent.students.filter(id=student_profile.id).exists():
                return True, ""
        
        # Faculty can view reports of students in classes they teach
        if requesting_user.role.code == 'FACULTY':
            # Check if faculty teaches this subject to this student
            from timetable.models import TimetableEntry
            teaches_student = TimetableEntry.objects.filter(
                subject=subject,
                faculty=requesting_user,
                section__students=student_profile,
                is_active=True
            ).exists()
            
            if teaches_student:
                return True, ""
        
        # Admin can view all
        if requesting_user.role.code in ['ADMIN', 'HOD']:
            return True, ""
        
        return False, "You do not have permission to view this report"
