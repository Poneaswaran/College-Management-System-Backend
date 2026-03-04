"""
GraphQL Queries for Attendance System
"""
import strawberry
from typing import List, Optional
from datetime import date
from strawberry.types import Info
from django.utils import timezone

from attendance.models import AttendanceSession, StudentAttendance, AttendanceReport
from attendance.graphql.types import (
    AttendanceSessionType,
    StudentAttendanceType,
    AttendanceReportType
)
from attendance.graphql.hod_types import (
    HODAttendanceReportData,
    StudentAttendanceDetail,
    ClassAttendanceDetail
)
from core.graphql.auth import require_auth


@strawberry.type
class AttendanceQuery:
    """Attendance-related queries"""
    
    @strawberry.field
    @require_auth
    def active_sessions_for_student(self, info: Info) -> List[AttendanceSessionType]:
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
            'timetable_entry__faculty',
            'timetable_entry__period_definition',
            'timetable_entry__section',
            'timetable_entry__semester'
        ).order_by('timetable_entry__period_definition__start_time')
        
        return list(sessions)
    
    @strawberry.field
    @require_auth
    def faculty_sessions_today(self, info: Info) -> List[AttendanceSessionType]:
        """
        Get all sessions for current faculty member today
        Faculty can see all their classes for the day
        """
        user = info.context.request.user
        
        if user.role.code != 'FACULTY':
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
    @require_auth
    def attendance_session(self, info: Info, session_id: int) -> Optional[AttendanceSessionType]:
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
            if session.timetable_entry.section.student_profiles.filter(id=user.student_profile.id).exists():
                has_access = True
        
        # Faculty access
        if user.role.code == 'FACULTY':
            if session.timetable_entry.faculty.id == user.id:
                has_access = True
        
        # Admin access
        if user.role.code in ['ADMIN', 'HOD']:
            has_access = True
        
        if not has_access:
            return None
        
        return session
    
    @strawberry.field
    @require_auth
    def student_attendance_history(
        self,
        info: Info,
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
            if user.role.code == 'FACULTY':
                from timetable.models import TimetableEntry
                teaches_student = TimetableEntry.objects.filter(
                    faculty=user,
                    section__student_profiles__id=student_id,
                    is_active=True
                ).exists()
                if not teaches_student and user.role.code not in ['ADMIN', 'HOD']:
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
    @require_auth
    def attendance_report(
        self,
        info: Info,
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
            elif user.role.code in ['ADMIN', 'HOD']:
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
    @require_auth
    def all_reports_for_student(
        self,
        info: Info,
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
            elif user.role.code in ['ADMIN', 'HOD']:
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
    @require_auth
    def section_attendance_for_session(
        self,
        info: Info,
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
        if user.role.code not in ['ADMIN', 'HOD']:
            if user.role.code != 'FACULTY' or session.timetable_entry.faculty.id != user.id:
                return []
        
        attendances = StudentAttendance.objects.filter(
            session=session
        ).select_related(
            'student',
            'marked_by'
        ).order_by('student__first_name')
        
        return list(attendances)
    
    @strawberry.field
    @require_auth
    def student_attendance_detail(
        self,
        info: Info,
        session_id: int,
        student_id: int
    ) -> Optional[StudentAttendanceType]:
        """
        Get a single student's attendance record for a specific session.
        Returns marked_at, image_url, latitude, longitude, register_number, etc.
        Faculty teaching the class, admin, or the student themselves can access.
        """
        user = info.context.request.user

        try:
            session = AttendanceSession.objects.select_related(
                'timetable_entry__faculty'
            ).get(id=session_id)
        except AttendanceSession.DoesNotExist:
            return None

        # Access control
        is_own_record = (
            hasattr(user, 'student_profile') and
            user.student_profile.id == student_id
        )
        is_faculty = (
            user.role.code == 'FACULTY' and
            session.timetable_entry.faculty_id == user.id
        )
        is_admin = user.role.code in ['ADMIN', 'HOD']

        if not (is_own_record or is_faculty or is_admin):
            return None

        try:
            attendance = StudentAttendance.objects.select_related(
                'student__user',
                'session__timetable_entry__subject',
                'session__timetable_entry__section',
                'marked_by'
            ).get(session_id=session_id, student_id=student_id)
        except StudentAttendance.DoesNotExist:
            return None

        return attendance
    

    @strawberry.field
    @require_auth
    def low_attendance_students(
        self,
        info: Info,
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
        if user.role.code not in ['ADMIN', 'HOD']:
            if user.role.code != 'FACULTY':
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
    
    # ==================== HOD Attendance Reports ====================
    
    @strawberry.field
    @require_auth
    def hod_attendance_report(
        self,
        info: Info,
        department_id: Optional[int] = None,
        semester_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        period_number: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> HODAttendanceReportData:
        """
        Returns a full attendance report for the HOD's department.
        Supports filtering by semester, subject, period, and date range.
        """
        from attendance.graphql.hod_queries import HODAttendanceQuery
        hod_query = HODAttendanceQuery()
        return hod_query.hod_attendance_report(
            info, department_id, semester_id, subject_id, period_number, date_from, date_to
        )
    
    @strawberry.field
    @require_auth
    def hod_student_attendance_detail(
        self,
        info: Info,
        student_id: int,
        semester_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> StudentAttendanceDetail:
        """
        Drill-down for a single student showing per-subject breakdown
        and period-level records.
        """
        from attendance.graphql.hod_queries import HODAttendanceQuery
        hod_query = HODAttendanceQuery()
        return hod_query.hod_student_attendance_detail(
            info, student_id, semester_id, date_from, date_to
        )
    
    @strawberry.field
    @require_auth
    def hod_class_attendance_detail(
        self,
        info: Info,
        section_id: int,
        semester_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> ClassAttendanceDetail:
        """
        Drill-down for a class/section showing all students and subject breakdown.
        """
        from attendance.graphql.hod_queries import HODAttendanceQuery
        hod_query = HODAttendanceQuery()
        return hod_query.hod_class_attendance_detail(
            info, section_id, semester_id, subject_id, date_from, date_to
        )
