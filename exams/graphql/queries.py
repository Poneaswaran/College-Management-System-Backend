"""
GraphQL Queries for Exam Management System.
"""
import strawberry
from typing import List, Optional
from strawberry.types import Info

from exams.models import (
    Exam, ExamSchedule, ExamSeatingArrangement,
    ExamResult, HallTicket
)
from exams.services import ResultService
from exams.graphql.types import (
    ExamType,
    ExamScheduleType,
    ExamSeatingType,
    ExamResultType,
    HallTicketType,
    ExamResultStatisticsType,
)
from core.graphql.auth import require_auth, require_role


@strawberry.type
class ExamQuery:
    """Exam-related queries."""

    # ==================================================
    # EXAM QUERIES
    # ==================================================

    @strawberry.field
    @require_auth
    def exam(self, info: Info, id: int) -> Optional[ExamType]:
        """Get a single exam by ID."""
        try:
            return Exam.objects.select_related(
                'semester', 'department', 'created_by'
            ).get(id=id)
        except Exam.DoesNotExist:
            return None

    @strawberry.field
    @require_auth
    def exams(
        self,
        info: Info,
        semester_id: Optional[int] = None,
        exam_type: Optional[str] = None,
        status: Optional[str] = None,
        department_id: Optional[int] = None,
    ) -> List[ExamType]:
        """List exams with optional filters."""
        qs = Exam.objects.select_related(
            'semester', 'department', 'created_by'
        )

        if semester_id:
            qs = qs.filter(semester_id=semester_id)
        if exam_type:
            qs = qs.filter(exam_type=exam_type)
        if status:
            qs = qs.filter(status=status)
        if department_id:
            qs = qs.filter(department_id=department_id)

        return qs

    @strawberry.field
    @require_auth
    def upcoming_exams(self, info: Info) -> List[ExamType]:
        """Get upcoming/ongoing exams for the current user."""
        from django.utils import timezone
        user = info.context.request.user

        qs = Exam.objects.filter(
            end_date__gte=timezone.now().date(),
            status__in=['SCHEDULED', 'ONGOING']
        ).select_related('semester', 'department')

        # If student, filter by department
        if hasattr(user, 'role') and user.role.code == 'STUDENT':
            qs = qs.filter(
                models.Q(department=user.department) |
                models.Q(department__isnull=True)
            )

        return qs

    # ==================================================
    # EXAM SCHEDULE QUERIES
    # ==================================================

    @strawberry.field
    @require_auth
    def exam_schedule(self, info: Info, id: int) -> Optional[ExamScheduleType]:
        """Get a single exam schedule by ID."""
        try:
            return ExamSchedule.objects.select_related(
                'exam', 'subject', 'section', 'room', 'invigilator'
            ).get(id=id)
        except ExamSchedule.DoesNotExist:
            return None

    @strawberry.field
    @require_auth
    def exam_schedules(
        self,
        info: Info,
        exam_id: int,
        section_id: Optional[int] = None,
    ) -> List[ExamScheduleType]:
        """List exam schedules for a specific exam."""
        qs = ExamSchedule.objects.filter(
            exam_id=exam_id
        ).select_related(
            'exam', 'subject', 'section', 'room', 'invigilator'
        )

        if section_id:
            qs = qs.filter(section_id=section_id)

        return qs

    @strawberry.field
    @require_auth
    def my_exam_schedule(
        self,
        info: Info,
        exam_id: int,
    ) -> List[ExamScheduleType]:
        """Get exam schedule for the current student."""
        user = info.context.request.user

        if not hasattr(user, 'role') or user.role.code != 'STUDENT':
            raise Exception("Only students can view their exam schedule")

        try:
            from profile_management.models import StudentProfile
            student = StudentProfile.objects.get(user=user)
        except StudentProfile.DoesNotExist:
            raise Exception("Student profile not found")

        return ExamSchedule.objects.filter(
            exam_id=exam_id,
            section=student.section
        ).select_related(
            'exam', 'subject', 'section', 'room', 'invigilator'
        ).order_by('date', 'start_time')

    # ==================================================
    # SEATING QUERIES
    # ==================================================

    @strawberry.field
    @require_auth
    def seating_arrangement(
        self,
        info: Info,
        schedule_id: int,
    ) -> List[ExamSeatingType]:
        """Get seating arrangement for a specific exam schedule."""
        return ExamSeatingArrangement.objects.filter(
            schedule_id=schedule_id
        ).select_related('student', 'room', 'schedule')

    @strawberry.field
    @require_auth
    def my_seat(
        self,
        info: Info,
        schedule_id: int,
    ) -> Optional[ExamSeatingType]:
        """Get current student's seat for a specific exam."""
        user = info.context.request.user

        try:
            from profile_management.models import StudentProfile
            student = StudentProfile.objects.get(user=user)
        except StudentProfile.DoesNotExist:
            return None

        try:
            return ExamSeatingArrangement.objects.select_related(
                'room', 'schedule', 'schedule__subject'
            ).get(schedule_id=schedule_id, student=student)
        except ExamSeatingArrangement.DoesNotExist:
            return None

    # ==================================================
    # RESULT QUERIES
    # ==================================================

    @strawberry.field
    @require_auth
    def exam_results(
        self,
        info: Info,
        schedule_id: int,
        status: Optional[str] = None,
    ) -> List[ExamResultType]:
        """Get results for a specific exam schedule (faculty/admin)."""
        qs = ExamResult.objects.filter(
            schedule_id=schedule_id
        ).select_related('student', 'schedule', 'entered_by', 'verified_by')

        if status:
            qs = qs.filter(status=status)

        return qs

    @strawberry.field
    @require_auth
    def my_results(
        self,
        info: Info,
        exam_id: Optional[int] = None,
        semester_id: Optional[int] = None,
    ) -> List[ExamResultType]:
        """Get current student's exam results."""
        user = info.context.request.user

        try:
            from profile_management.models import StudentProfile
            student = StudentProfile.objects.get(user=user)
        except StudentProfile.DoesNotExist:
            raise Exception("Student profile not found")

        qs = ExamResult.objects.filter(
            student=student,
            status='PUBLISHED'
        ).select_related(
            'schedule', 'schedule__subject', 'schedule__exam'
        )

        if exam_id:
            qs = qs.filter(schedule__exam_id=exam_id)
        if semester_id:
            qs = qs.filter(schedule__exam__semester_id=semester_id)

        return qs.order_by('schedule__date')

    @strawberry.field
    @require_role('FACULTY', 'HOD', 'ADMIN')
    def exam_result_statistics(
        self,
        info: Info,
        schedule_id: int,
    ) -> ExamResultStatisticsType:
        """Get result statistics for a specific exam schedule."""
        stats = ResultService.get_result_statistics(schedule_id)
        return ExamResultStatisticsType(**stats)

    # ==================================================
    # HALL TICKET QUERIES
    # ==================================================

    @strawberry.field
    @require_auth
    def hall_tickets(
        self,
        info: Info,
        exam_id: int,
        section_id: Optional[int] = None,
    ) -> List[HallTicketType]:
        """List hall tickets for an exam (admin/faculty)."""
        qs = HallTicket.objects.filter(
            exam_id=exam_id
        ).select_related('student', 'exam')

        if section_id:
            qs = qs.filter(student__section_id=section_id)

        return qs

    @strawberry.field
    @require_auth
    def my_hall_ticket(
        self,
        info: Info,
        exam_id: int,
    ) -> Optional[HallTicketType]:
        """Get current student's hall ticket."""
        user = info.context.request.user

        try:
            from profile_management.models import StudentProfile
            student = StudentProfile.objects.get(user=user)
        except StudentProfile.DoesNotExist:
            return None

        try:
            return HallTicket.objects.select_related(
                'exam', 'student'
            ).get(student=student, exam_id=exam_id)
        except HallTicket.DoesNotExist:
            return None
