"""
Utility functions for Attendance System
"""
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import datetime, timedelta


def get_active_sessions_for_student(student_profile):
    """
    Get all active attendance sessions for a student
    
    Args:
        student_profile: StudentProfile instance
    
    Returns:
        QuerySet of AttendanceSession
    """
    from attendance.models import AttendanceSession
    
    today = timezone.now().date()
    section = student_profile.section
    
    # Get active sessions for student's section today
    return AttendanceSession.objects.filter(
        timetable_entry__section=section,
        date=today,
        status='ACTIVE',
        opened_at__isnull=False
    ).select_related(
        'timetable_entry__subject',
        'timetable_entry__faculty__user',
        'timetable_entry__period_definition'
    )


def get_pending_sessions_for_student(student_profile):
    """
    Get sessions where student hasn't marked attendance yet
    
    Args:
        student_profile: StudentProfile instance
    
    Returns:
        QuerySet of AttendanceSession
    """
    from attendance.models import AttendanceSession, StudentAttendance
    
    # Get active sessions
    active_sessions = get_active_sessions_for_student(student_profile)
    
    # Filter out sessions where attendance is already marked
    marked_session_ids = StudentAttendance.objects.filter(
        student=student_profile,
        session__in=active_sessions,
        status='PRESENT'
    ).values_list('session_id', flat=True)
    
    return active_sessions.exclude(id__in=marked_session_ids)


def get_faculty_sessions_for_today(faculty_user):
    """
    Get all sessions for a faculty member today
    
    Args:
        faculty_user: User instance with role FACULTY
    
    Returns:
        QuerySet of AttendanceSession
    """
    from attendance.models import AttendanceSession
    from timetable.models import TimetableEntry
    
    today = timezone.now().date()
    
    # Get faculty's timetable entries
    timetable_entries = TimetableEntry.objects.filter(
        faculty=faculty_user,
        is_active=True
    )
    
    # Get or create sessions for today
    sessions = AttendanceSession.objects.filter(
        timetable_entry__in=timetable_entries,
        date=today
    ).select_related(
        'timetable_entry__subject',
        'timetable_entry__section',
        'timetable_entry__period_definition'
    ).order_by('timetable_entry__period_definition__start_time')
    
    return sessions


def auto_create_sessions_for_faculty(faculty_user, date=None):
    """
    Automatically create scheduled sessions for faculty's classes
    
    Args:
        faculty_user: User instance
        date: Date for sessions (defaults to today)
    
    Returns:
        List of created AttendanceSession instances
    """
    from attendance.models import AttendanceSession
    from timetable.models import TimetableEntry
    
    if date is None:
        date = timezone.now().date()
    
    # Get faculty's timetable entries for the day
    day_of_week = date.isoweekday()  # 1=Monday, 7=Sunday
    
    timetable_entries = TimetableEntry.objects.filter(
        faculty=faculty_user,
        is_active=True,
        period_definition__day_of_week=day_of_week
    ).select_related('period_definition')
    
    created_sessions = []
    for entry in timetable_entries:
        # Create session if doesn't exist
        session, created = AttendanceSession.objects.get_or_create(
            timetable_entry=entry,
            date=date,
            defaults={
                'status': 'SCHEDULED',
                'attendance_window_minutes': 10
            }
        )
        if created:
            created_sessions.append(session)
    
    return created_sessions


def calculate_student_attendance_summary(student_profile, semester=None):
    """
    Calculate overall attendance summary for a student
    
    Args:
        student_profile: StudentProfile instance
        semester: Semester instance (optional, defaults to current)
    
    Returns:
        dict with attendance statistics
    """
    from attendance.models import StudentAttendance
    from profile_management.models import Semester
    
    if semester is None:
        semester = Semester.objects.filter(is_current=True).first()
    
    if not semester:
        return {
            'total_classes': 0,
            'present': 0,
            'absent': 0,
            'late': 0,
            'percentage': 0.0
        }
    
    # Get all attendances for student in semester (excluding blocked sessions)
    attendances = StudentAttendance.objects.filter(
        student=student_profile,
        session__timetable_entry__semester=semester,
        session__status='CLOSED'
    ).exclude(
        session__status__in=['BLOCKED', 'CANCELLED']
    )
    
    total = attendances.count()
    present = attendances.filter(status='PRESENT').count()
    absent = attendances.filter(status='ABSENT').count()
    late = attendances.filter(status='LATE').count()
    
    # Calculate percentage (late counts as present)
    effective_present = present + late
    percentage = round((effective_present / total * 100), 2) if total > 0 else 0.0
    
    return {
        'total_classes': total,
        'present': present,
        'absent': absent,
        'late': late,
        'percentage': percentage
    }


def calculate_subject_attendance(student_profile, subject, semester=None):
    """
    Calculate attendance for a specific subject
    
    Args:
        student_profile: StudentProfile instance
        subject: Subject instance
        semester: Semester instance (optional)
    
    Returns:
        dict with subject attendance statistics
    """
    from attendance.models import StudentAttendance
    from profile_management.models import Semester
    
    if semester is None:
        semester = Semester.objects.filter(is_current=True).first()
    
    attendances = StudentAttendance.objects.filter(
        student=student_profile,
        session__timetable_entry__subject=subject,
        session__timetable_entry__semester=semester,
        session__status='CLOSED'
    ).exclude(
        session__status__in=['BLOCKED', 'CANCELLED']
    )
    
    total = attendances.count()
    present = attendances.filter(status='PRESENT').count()
    absent = attendances.filter(status='ABSENT').count()
    late = attendances.filter(status='LATE').count()
    
    effective_present = present + late
    percentage = round((effective_present / total * 100), 2) if total > 0 else 0.0
    
    return {
        'subject': subject.name,
        'total_classes': total,
        'present': present,
        'absent': absent,
        'late': late,
        'percentage': percentage,
        'is_below_threshold': percentage < 75.0
    }


def get_low_attendance_students(section, subject, threshold=75.0):
    """
    Get students with attendance below threshold
    
    Args:
        section: Section instance
        subject: Subject instance
        threshold: Minimum attendance percentage (default 75%)
    
    Returns:
        QuerySet of StudentProfile with low attendance
    """
    from attendance.models import AttendanceReport
    
    return AttendanceReport.objects.filter(
        subject=subject,
        student__section=section,
        attendance_percentage__lt=threshold,
        is_below_threshold=True
    ).select_related('student__user').order_by('attendance_percentage')


def auto_close_expired_sessions():
    """
    Automatically close sessions that have expired
    Should be run periodically (e.g., via cron job or celery task)
    
    Returns:
        int: Number of sessions closed
    """
    from attendance.models import AttendanceSession
    
    now = timezone.now()
    
    # Find active sessions where window has expired
    expired_sessions = AttendanceSession.objects.filter(
        status='ACTIVE',
        opened_at__isnull=False
    )
    
    closed_count = 0
    for session in expired_sessions:
        window_end = session.opened_at + timedelta(minutes=session.attendance_window_minutes)
        if now > window_end:
            session.status = 'CLOSED'
            session.closed_at = now
            session.save(update_fields=['status', 'closed_at', 'updated_at'])
            closed_count += 1
    
    return closed_count


def auto_mark_absent_students(session):
    """
    Automatically mark students as absent who didn't mark attendance
    Called when session is closed
    
    Args:
        session: AttendanceSession instance
    
    Returns:
        int: Number of students marked absent
    """
    from attendance.models import StudentAttendance
    
    # Get all students in the section
    section = session.timetable_entry.section
    all_students = section.students.all()
    
    # Get students who already marked attendance
    marked_students = StudentAttendance.objects.filter(
        session=session
    ).values_list('student_id', flat=True)
    
    # Mark remaining students as absent
    absent_count = 0
    for student in all_students:
        if student.id not in marked_students:
            StudentAttendance.objects.create(
                session=session,
                student=student,
                status='ABSENT',
                notes='Auto-marked absent (did not mark attendance)'
            )
            absent_count += 1
    
    return absent_count


def get_session_statistics(session):
    """
    Get detailed statistics for an attendance session
    
    Args:
        session: AttendanceSession instance
    
    Returns:
        dict with session statistics
    """
    from attendance.models import StudentAttendance
    
    total_students = session.timetable_entry.section.students.count()
    present = session.student_attendances.filter(status='PRESENT').count()
    absent = session.student_attendances.filter(status='ABSENT').count()
    late = session.student_attendances.filter(status='LATE').count()
    not_marked = total_students - (present + absent + late)
    
    return {
        'total_students': total_students,
        'present': present,
        'absent': absent,
        'late': late,
        'not_marked': not_marked,
        'attendance_percentage': round((present / total_students * 100), 2) if total_students > 0 else 0.0,
        'is_active': session.can_mark_attendance,
        'time_remaining': session.time_remaining
    }


def bulk_update_attendance_reports(semester):
    """
    Update all attendance reports for a semester
    Useful for end-of-day or end-of-semester calculations
    
    Args:
        semester: Semester instance
    
    Returns:
        int: Number of reports updated
    """
    from attendance.models import AttendanceReport, StudentAttendance
    from profile_management.models import StudentProfile
    from timetable.models import Subject
    
    # Get all unique student-subject combinations in the semester
    combinations = StudentAttendance.objects.filter(
        session__timetable_entry__semester=semester
    ).values('student', 'session__timetable_entry__subject').distinct()
    
    updated_count = 0
    for combo in combinations:
        student = StudentProfile.objects.get(id=combo['student'])
        subject = Subject.objects.get(id=combo['session__timetable_entry__subject'])
        
        AttendanceReport.update_for_student_subject(student, subject, semester)
        updated_count += 1
    
    return updated_count
