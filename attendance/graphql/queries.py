"""
GraphQL Queries for Attendance System
"""
import strawberry
from typing import List, Optional
from datetime import date
from django.utils import timezone

from attendance.models import AttendanceSession, StudentAttendance, AttendanceReport
from attendance.graphql.types import (
    AttendanceSessionType,
    StudentAttendanceType,
    AttendanceReportType
)


@strawberry.type
class AttendanceQuery:
    """Attendance-related queries"""
    
    @strawberry.field
    def active_sessions_for_student(self, info) -> List[AttendanceSessionType]:
        """
        Get all active attendance sessions for current student
        Student can see sessions where they can mark attendance
        """
        user = info.context.request.user
        
        if not hasattr(user, 'student_profile'):
            return []
        
        student = user.student_profile
        today = timezone.now().date()
        
        # Get active sessions for student's section
        sessions = AttendanceSession.objects.filter(
            timetable_entry__section=student.section,
            date=today,
            status='ACTIVE'
        ).select_related(
            'timetable_entry__subject',
            'timetable_entry__faculty__user',
            'timetable_entry__period_definition',
            'timetable_entry__section',
            'timetable_entry__semester'
        ).order_by('timetable_entry__period_definition__start_time')
        
        return list(sessions)
    
    @strawberry.field
    def faculty_sessions_today(self, info) -> List[AttendanceSessionType]:
        """
        Get all sessions for current faculty member today
        Faculty can see all their classes for the day
        """
        user = info.context.request.user
        
        if user.role.name != 'FACULTY':
            return []
        
        today = timezone.now().date()
        day_of_week = today.isoweekday()
        
        # Get faculty's timetable entries for today
        from timetable.models import TimetableEntry
        timetable_entries = TimetableEntry.objects.filter(
            faculty=user,
            is_active=True,
            period_definition__day_of_week=day_of_week
        ).values_list('id', flat=True)
        
        # Get or list sessions
        sessions = AttendanceSession.objects.filter(
            timetable_entry__id__in=timetable_entries,
            date=today
        ).select_related(
            'timetable_entry__subject',
            'timetable_entry__section',
            'timetable_entry__period_definition',
            'timetable_entry__semester',
            'opened_by',
            'blocked_by'
        ).order_by('timetable_entry__period_definition__start_time')
        
        return list(sessions)
    
    @strawberry.field
    def attendance_session(self, info, session_id: int) -> Optional[AttendanceSessionType]:
        """
        Get details of a specific attendance session
        Access control: Student (if in section), Faculty (if teaches), Admin (all)
        """
        user = info.context.request.user
        
        try:
            session = AttendanceSession.objects.select_related(
                'timetable_entry__subject',
                'timetable_entry__section',
                'timetable_entry__faculty__user',
                'timetable_entry__period_definition',
                'timetable_entry__semester'
            ).get(id=session_id)
        except AttendanceSession.DoesNotExist:
            return None
        
        # Check access
        has_access = False
        
        # Student access
        if hasattr(user, 'student_profile'):
            if session.timetable_entry.section.students.filter(id=user.student_profile.id).exists():
                has_access = True
        
        # Faculty access
        if user.role.name == 'FACULTY':
            if session.timetable_entry.faculty.id == user.id:
                has_access = True
        
        # Admin access
        if user.role.name in ['ADMIN', 'SUPER_ADMIN']:
            has_access = True
        
        if not has_access:
            return None
        
        return session
    
    @strawberry.field
    def student_attendance_history(
        self,
        info,
        student_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[StudentAttendanceType]:
        """
        Get attendance history for a student
        If student_id not provided, uses current user's student profile
        """
        user = info.context.request.user
        
        # Determine which student to query
        if student_id:
            # Check if user has permission to view this student's attendance
            if hasattr(user, 'student_profile') and user.student_profile.id != student_id:
                # Student can only see their own
                return []
            
            # Faculty can see students they teach
            if user.role.name == 'FACULTY':
                from timetable.models import TimetableEntry
                teaches_student = TimetableEntry.objects.filter(
                    faculty=user,
                    section__students__id=student_id,
                    is_active=True
                ).exists()
                if not teaches_student and user.role.name not in ['ADMIN', 'SUPER_ADMIN']:
                    return []
            
            from profile_management.models import StudentProfile
            try:
                student = StudentProfile.objects.get(id=student_id)
            except StudentProfile.DoesNotExist:
                return []
        else:
            # Use current user's student profile
            if not hasattr(user, 'student_profile'):
                return []
            student = user.student_profile
        
        # Build query
        query = StudentAttendance.objects.filter(student=student)
        
        if subject_id:
            query = query.filter(session__timetable_entry__subject_id=subject_id)
        
        if start_date:
            query = query.filter(session__date__gte=start_date)
        
        if end_date:
            query = query.filter(session__date__lte=end_date)
        
        query = query.select_related(
            'session__timetable_entry__subject',
            'session__timetable_entry__section',
            'student__user',
            'marked_by'
        ).order_by('-session__date', '-marked_at')
        
        return list(query)
    
    @strawberry.field
    def attendance_report(
        self,
        info,
        student_id: Optional[int] = None,
        subject_id: Optional[int] = None
    ) -> Optional[AttendanceReportType]:
        """
        Get attendance report for a student in a subject
        If not provided, uses current student and requires subject_id
        """
        user = info.context.request.user
        
        # Determine student
        if student_id:
            from profile_management.models import StudentProfile
            try:
                student = StudentProfile.objects.get(id=student_id)
            except StudentProfile.DoesNotExist:
                return None
            
            # Check access
            has_access = False
            if hasattr(user, 'student_profile') and user.student_profile.id == student_id:
                has_access = True
            elif user.role.name in ['ADMIN', 'SUPER_ADMIN']:
                has_access = True
            
            if not has_access:
                return None
        else:
            if not hasattr(user, 'student_profile'):
                return None
            student = user.student_profile
        
        if not subject_id:
            return None
        
        from timetable.models import Subject
        from profile_management.models import Semester
        
        try:
            subject = Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            return None
        
        # Get current semester
        semester = Semester.objects.filter(is_current=True).first()
        if not semester:
            return None
        
        # Get or create report
        report, created = AttendanceReport.objects.get_or_create(
            student=student,
            subject=subject,
            semester=semester
        )
        
        # Update if old
        if created or (timezone.now() - report.last_calculated).days > 0:
            report.calculate()
        
        return report
    
    @strawberry.field
    def all_reports_for_student(
        self,
        info,
        student_id: Optional[int] = None
    ) -> List[AttendanceReportType]:
        """
        Get all attendance reports for a student (all subjects)
        """
        user = info.context.request.user
        
        # Determine student
        if student_id:
            from profile_management.models import StudentProfile
            try:
                student = StudentProfile.objects.get(id=student_id)
            except StudentProfile.DoesNotExist:
                return []
            
            # Check access
            has_access = False
            if hasattr(user, 'student_profile') and user.student_profile.id == student_id:
                has_access = True
            elif user.role.name in ['ADMIN', 'SUPER_ADMIN']:
                has_access = True
            
            if not has_access:
                return []
        else:
            if not hasattr(user, 'student_profile'):
                return []
            student = user.student_profile
        
        from profile_management.models import Semester
        semester = Semester.objects.filter(is_current=True).first()
        
        if not semester:
            return []
        
        reports = AttendanceReport.objects.filter(
            student=student,
            semester=semester
        ).select_related(
            'subject',
            'semester__academic_year',
            'student__user'
        ).order_by('-attendance_percentage')
        
        return list(reports)
    
    @strawberry.field
    def section_attendance_for_session(
        self,
        info,
        session_id: int
    ) -> List[StudentAttendanceType]:
        """
        Get all student attendances for a specific session
        Only faculty teaching the class or admin can access
        """
        user = info.context.request.user
        
        try:
            session = AttendanceSession.objects.get(id=session_id)
        except AttendanceSession.DoesNotExist:
            return []
        
        # Check access - only faculty teaching or admin
        if user.role.name not in ['ADMIN', 'SUPER_ADMIN']:
            if user.role.name != 'FACULTY' or session.timetable_entry.faculty.id != user.id:
                return []
        
        attendances = StudentAttendance.objects.filter(
            session=session
        ).select_related(
            'student__user',
            'marked_by'
        ).order_by('student__user__first_name')
        
        return list(attendances)
    
    @strawberry.field
    def low_attendance_students(
        self,
        info,
        subject_id: int,
        threshold: Optional[float] = 75.0
    ) -> List[AttendanceReportType]:
        """
        Get students with low attendance in a subject
        Only faculty teaching the subject or admin can access
        """
        user = info.context.request.user
        
        from timetable.models import Subject, TimetableEntry
        
        try:
            subject = Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            return []
        
        # Check access
        if user.role.name not in ['ADMIN', 'SUPER_ADMIN']:
            if user.role.name != 'FACULTY':
                return []
            
            # Check if faculty teaches this subject
            teaches_subject = TimetableEntry.objects.filter(
                faculty=user,
                subject=subject,
                is_active=True
            ).exists()
            
            if not teaches_subject:
                return []
        
        reports = AttendanceReport.objects.filter(
            subject=subject,
            attendance_percentage__lt=threshold,
            is_below_threshold=True
        ).select_related(
            'student__user',
            'subject',
            'semester__academic_year'
        ).order_by('attendance_percentage')
        
        return list(reports)
