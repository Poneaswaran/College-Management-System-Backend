"""
GraphQL Mutations for Exam Management System.
"""
import strawberry
from typing import Optional, List
from strawberry.types import Info
from decimal import Decimal
from django.utils import timezone
import logging

from exams.services import (
    ExamService, ExamScheduleService,
    SeatingService, ResultService, HallTicketService
)
from exams.graphql.types import (
    ExamType,
    ExamScheduleType,
    ExamResultType,
    HallTicketType,
    ExamMutationResponse,
    CreateExamResponse,
    CreateScheduleResponse,
    EnterMarksResponse,
    BulkEnterMarksResponse,
    HallTicketResponse,
    BulkHallTicketResponse,
    CreateExamInput,
    UpdateExamInput,
    CreateExamScheduleInput,
    EnterMarksInput,
    BulkEnterMarksInput,
    AssignSeatingInput,
    GenerateHallTicketInput,
)
from core.graphql.auth import require_auth, require_role

logger = logging.getLogger(__name__)


@strawberry.type
class ExamMutation:
    """Exam-related mutations."""

    # ==================================================
    # EXAM CRUD
    # ==================================================

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def create_exam(self, info: Info, input: CreateExamInput) -> CreateExamResponse:
        """Create a new exam cycle."""
        try:
            user = info.context.request.user
            exam = ExamService.create_exam(
                name=input.name,
                exam_type=input.exam_type,
                semester_id=input.semester_id,
                start_date=input.start_date,
                end_date=input.end_date,
                created_by=user,
                department_id=input.department_id,
                max_marks=input.max_marks,
                pass_marks_percentage=input.pass_marks_percentage,
                instructions=input.instructions,
            )
            return CreateExamResponse(
                success=True,
                message="Exam created successfully",
                exam=exam
            )
        except Exception as e:
            logger.exception("Error creating exam")
            return CreateExamResponse(
                success=False,
                message=str(e)
            )

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def update_exam(self, info: Info, input: UpdateExamInput) -> CreateExamResponse:
        """Update an existing exam."""
        try:
            from exams.models import Exam
            exam = Exam.objects.get(id=input.exam_id)

            if input.name is not None:
                exam.name = input.name
            if input.start_date is not None:
                exam.start_date = input.start_date
            if input.end_date is not None:
                exam.end_date = input.end_date
            if input.max_marks is not None:
                exam.max_marks = input.max_marks
            if input.pass_marks_percentage is not None:
                exam.pass_marks_percentage = input.pass_marks_percentage
            if input.instructions is not None:
                exam.instructions = input.instructions

            exam.full_clean()
            exam.save()

            return CreateExamResponse(
                success=True,
                message="Exam updated successfully",
                exam=exam
            )
        except Exam.DoesNotExist:
            return CreateExamResponse(success=False, message="Exam not found")
        except Exception as e:
            logger.exception("Error updating exam")
            return CreateExamResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def update_exam_status(
        self, info: Info, exam_id: int, status: str
    ) -> ExamMutationResponse:
        """Update exam status (DRAFT -> SCHEDULED -> ONGOING -> COMPLETED)."""
        try:
            user = info.context.request.user
            ExamService.update_exam_status(exam_id, status, user)
            return ExamMutationResponse(
                success=True,
                message=f"Exam status updated to '{status}'"
            )
        except ValueError as e:
            return ExamMutationResponse(success=False, message=str(e))
        except Exception as e:
            logger.exception("Error updating exam status")
            return ExamMutationResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def delete_exam(self, info: Info, exam_id: int) -> ExamMutationResponse:
        """Delete an exam (only if in DRAFT status)."""
        try:
            from exams.models import Exam
            exam = Exam.objects.get(id=exam_id)
            if exam.status != 'DRAFT':
                return ExamMutationResponse(
                    success=False,
                    message="Only DRAFT exams can be deleted"
                )
            exam.delete()
            return ExamMutationResponse(
                success=True,
                message="Exam deleted successfully"
            )
        except Exam.DoesNotExist:
            return ExamMutationResponse(success=False, message="Exam not found")
        except Exception as e:
            logger.exception("Error deleting exam")
            return ExamMutationResponse(success=False, message=str(e))

    # ==================================================
    # EXAM SCHEDULE
    # ==================================================

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def create_exam_schedule(
        self, info: Info, input: CreateExamScheduleInput
    ) -> CreateScheduleResponse:
        """Create a schedule entry within an exam cycle."""
        try:
            schedule = ExamScheduleService.create_schedule(
                exam_id=input.exam_id,
                subject_id=input.subject_id,
                section_id=input.section_id,
                date=input.date,
                start_time=input.start_time,
                end_time=input.end_time,
                shift=input.shift,
                duration_minutes=input.duration_minutes,
                room_id=input.room_id,
                invigilator_id=input.invigilator_id,
                max_marks=input.max_marks,
                notes=input.notes,
            )
            return CreateScheduleResponse(
                success=True,
                message="Exam schedule created",
                schedule=schedule
            )
        except ValueError as e:
            return CreateScheduleResponse(success=False, message=str(e))
        except Exception as e:
            logger.exception("Error creating exam schedule")
            return CreateScheduleResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def delete_exam_schedule(
        self, info: Info, schedule_id: int
    ) -> ExamMutationResponse:
        """Delete an exam schedule entry."""
        try:
            from exams.models import ExamSchedule
            schedule = ExamSchedule.objects.get(id=schedule_id)
            schedule.delete()
            return ExamMutationResponse(
                success=True,
                message="Exam schedule deleted"
            )
        except ExamSchedule.DoesNotExist:
            return ExamMutationResponse(success=False, message="Schedule not found")
        except Exception as e:
            logger.exception("Error deleting exam schedule")
            return ExamMutationResponse(success=False, message=str(e))

    # ==================================================
    # SEATING ARRANGEMENT
    # ==================================================

    @strawberry.mutation
    @require_role('FACULTY', 'HOD', 'ADMIN')
    def assign_seat(
        self, info: Info, input: AssignSeatingInput
    ) -> ExamMutationResponse:
        """Assign a seat to a student."""
        try:
            SeatingService.assign_seating(
                schedule_id=input.schedule_id,
                student_id=input.student_id,
                seat_number=input.seat_number,
                room_id=input.room_id,
            )
            return ExamMutationResponse(
                success=True,
                message="Seat assigned"
            )
        except Exception as e:
            logger.exception("Error assigning seat")
            return ExamMutationResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def auto_assign_seating(
        self, info: Info, schedule_id: int, room_id: Optional[int] = None
    ) -> ExamMutationResponse:
        """Auto-assign seating for all students in a section for an exam."""
        try:
            from exams.models import ExamSchedule
            from profile_management.models import StudentProfile

            schedule = ExamSchedule.objects.get(id=schedule_id)
            student_ids = list(
                StudentProfile.objects.filter(
                    section=schedule.section,
                    academic_status='ACTIVE'
                ).values_list('id', flat=True)
            )

            if not student_ids:
                return ExamMutationResponse(
                    success=False,
                    message="No active students found in this section"
                )

            created = SeatingService.bulk_assign_seating(
                schedule_id=schedule_id,
                student_ids=student_ids,
                room_id=room_id
            )

            return ExamMutationResponse(
                success=True,
                message=f"Seating assigned for {len(created)} students"
            )
        except Exception as e:
            logger.exception("Error auto-assigning seating")
            return ExamMutationResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('FACULTY', 'HOD', 'ADMIN')
    def mark_exam_attendance(
        self, info: Info, schedule_id: int, student_id: int, is_present: bool
    ) -> ExamMutationResponse:
        """Mark attendance for a student in an exam."""
        try:
            SeatingService.mark_exam_attendance(
                schedule_id=schedule_id,
                student_id=student_id,
                is_present=is_present
            )
            status = "present" if is_present else "absent"
            return ExamMutationResponse(
                success=True,
                message=f"Student marked as {status}"
            )
        except Exception as e:
            logger.exception("Error marking exam attendance")
            return ExamMutationResponse(success=False, message=str(e))

    # ==================================================
    # MARKS ENTRY
    # ==================================================

    @strawberry.mutation
    @require_role('FACULTY', 'HOD', 'ADMIN')
    def enter_marks(
        self, info: Info, input: EnterMarksInput
    ) -> EnterMarksResponse:
        """Enter marks for a single student."""
        try:
            user = info.context.request.user
            result = ResultService.enter_marks(
                schedule_id=input.schedule_id,
                student_id=input.student_id,
                marks_obtained=input.marks_obtained,
                entered_by=user,
                is_absent=input.is_absent,
                remarks=input.remarks,
            )
            return EnterMarksResponse(
                success=True,
                message="Marks entered successfully",
                result=result
            )
        except Exception as e:
            logger.exception("Error entering marks")
            return EnterMarksResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('FACULTY', 'HOD', 'ADMIN')
    def bulk_enter_marks(
        self, info: Info, input: BulkEnterMarksInput
    ) -> BulkEnterMarksResponse:
        """Bulk enter marks for multiple students."""
        try:
            user = info.context.request.user
            results_data = [
                {
                    'student_id': entry.student_id,
                    'marks_obtained': entry.marks_obtained,
                    'is_absent': entry.is_absent,
                    'remarks': entry.remarks,
                }
                for entry in input.results
            ]

            results = ResultService.bulk_enter_marks(
                schedule_id=input.schedule_id,
                results_data=results_data,
                entered_by=user
            )
            return BulkEnterMarksResponse(
                success=True,
                message=f"Marks entered for {len(results)} students",
                count=len(results)
            )
        except Exception as e:
            logger.exception("Error bulk entering marks")
            return BulkEnterMarksResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def verify_results(
        self, info: Info, schedule_id: int
    ) -> ExamMutationResponse:
        """Verify all entered results for a schedule (HOD/admin)."""
        try:
            user = info.context.request.user
            count = ResultService.verify_results(schedule_id, user)
            return ExamMutationResponse(
                success=True,
                message=f"{count} results verified"
            )
        except Exception as e:
            logger.exception("Error verifying results")
            return ExamMutationResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def publish_results(
        self, info: Info, exam_id: int
    ) -> ExamMutationResponse:
        """Publish all verified results for an exam cycle."""
        try:
            user = info.context.request.user
            count = ResultService.publish_results(exam_id, user)
            return ExamMutationResponse(
                success=True,
                message=f"{count} results published"
            )
        except Exception as e:
            logger.exception("Error publishing results")
            return ExamMutationResponse(success=False, message=str(e))

    # ==================================================
    # HALL TICKETS
    # ==================================================

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def generate_hall_ticket(
        self, info: Info, input: GenerateHallTicketInput
    ) -> HallTicketResponse:
        """Generate a hall ticket for a student."""
        try:
            if not input.student_id:
                return HallTicketResponse(
                    success=False,
                    message="student_id is required"
                )

            user = info.context.request.user
            ticket = HallTicketService.generate_hall_ticket(
                student_id=input.student_id,
                exam_id=input.exam_id,
                generated_by=user
            )
            return HallTicketResponse(
                success=True,
                message="Hall ticket generated",
                hall_ticket=ticket
            )
        except Exception as e:
            logger.exception("Error generating hall ticket")
            return HallTicketResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def bulk_generate_hall_tickets(
        self, info: Info, exam_id: int, section_id: int
    ) -> BulkHallTicketResponse:
        """Generate hall tickets for all students in a section."""
        try:
            user = info.context.request.user
            tickets = HallTicketService.bulk_generate_hall_tickets(
                exam_id=exam_id,
                section_id=section_id,
                generated_by=user
            )
            return BulkHallTicketResponse(
                success=True,
                message=f"Hall tickets generated for {len(tickets)} students",
                count=len(tickets)
            )
        except Exception as e:
            logger.exception("Error bulk generating hall tickets")
            return BulkHallTicketResponse(success=False, message=str(e))

    @strawberry.mutation
    @require_role('HOD', 'ADMIN')
    def revoke_hall_ticket(
        self, info: Info, hall_ticket_id: int
    ) -> ExamMutationResponse:
        """Revoke a hall ticket (e.g., due to malpractice)."""
        try:
            from exams.models import HallTicket
            ticket = HallTicket.objects.get(id=hall_ticket_id)
            ticket.status = 'REVOKED'
            ticket.save(update_fields=['status'])
            return ExamMutationResponse(
                success=True,
                message="Hall ticket revoked"
            )
        except HallTicket.DoesNotExist:
            return ExamMutationResponse(success=False, message="Hall ticket not found")
        except Exception as e:
            logger.exception("Error revoking hall ticket")
            return ExamMutationResponse(success=False, message=str(e))
