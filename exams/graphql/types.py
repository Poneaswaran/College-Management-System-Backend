"""
GraphQL types for Exam Management System.
"""
import strawberry
import strawberry_django
from typing import Optional, List
from datetime import datetime, date, time
from decimal import Decimal

from exams.models import (
    Exam, ExamSchedule, ExamSeatingArrangement,
    ExamResult, HallTicket
)


# ==================================================
# INPUT TYPES
# ==================================================

@strawberry.input
class CreateExamInput:
    """Input for creating an exam cycle."""
    name: str
    exam_type: str
    semester_id: int
    start_date: date
    end_date: date
    department_id: Optional[int] = None
    max_marks: Decimal = Decimal('100')
    pass_marks_percentage: Decimal = Decimal('40')
    instructions: str = ''


@strawberry.input
class UpdateExamInput:
    """Input for updating an exam."""
    exam_id: int
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    max_marks: Optional[Decimal] = None
    pass_marks_percentage: Optional[Decimal] = None
    instructions: Optional[str] = None


@strawberry.input
class CreateExamScheduleInput:
    """Input for creating an exam schedule entry."""
    exam_id: int
    subject_id: int
    section_id: int
    date: date
    start_time: time
    end_time: time
    shift: str = 'MORNING'
    duration_minutes: int = 180
    room_id: Optional[int] = None
    invigilator_id: Optional[int] = None
    max_marks: Optional[Decimal] = None
    notes: str = ''


@strawberry.input
class EnterMarksInput:
    """Input for entering marks for a single student."""
    schedule_id: int
    student_id: int
    marks_obtained: Decimal
    is_absent: bool = False
    remarks: str = ''


@strawberry.input
class BulkMarkEntry:
    """Single entry in bulk marks input."""
    student_id: int
    marks_obtained: Decimal
    is_absent: bool = False
    remarks: str = ''


@strawberry.input
class BulkEnterMarksInput:
    """Input for bulk marks entry."""
    schedule_id: int
    results: List[BulkMarkEntry]


@strawberry.input
class AssignSeatingInput:
    """Input for assigning a seat."""
    schedule_id: int
    student_id: int
    seat_number: str
    room_id: Optional[int] = None


@strawberry.input
class GenerateHallTicketInput:
    """Input for generating hall tickets."""
    exam_id: int
    student_id: Optional[int] = None
    section_id: Optional[int] = None


# ==================================================
# OUTPUT TYPES
# ==================================================

@strawberry_django.type(Exam)
class ExamType:
    """GraphQL type for Exam."""
    id: strawberry.ID
    name: str
    exam_type: str
    status: str
    start_date: date
    end_date: date
    max_marks: Decimal
    pass_marks_percentage: Decimal
    instructions: str
    created_at: datetime
    updated_at: datetime

    # Properties
    is_upcoming: bool
    is_ongoing: bool
    is_completed: bool
    total_subjects: int
    total_students: int

    # Relationships
    @strawberry_django.field
    def semester(self) -> 'SemesterType':
        return self.semester

    @strawberry_django.field
    def department(self) -> Optional['DepartmentType']:
        return self.department

    @strawberry_django.field
    def created_by(self) -> Optional['UserType']:
        return self.created_by

    @strawberry_django.field
    def schedules(self) -> List['ExamScheduleType']:
        return self.schedules.select_related('subject', 'room', 'section').all()

    # Custom fields
    @strawberry.field
    def exam_type_display(self) -> str:
        return self.get_exam_type_display()

    @strawberry.field
    def status_display(self) -> str:
        return self.get_status_display()

    @strawberry.field
    def duration_days(self) -> int:
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0


@strawberry_django.type(ExamSchedule)
class ExamScheduleType:
    """GraphQL type for ExamSchedule."""
    id: strawberry.ID
    date: date
    start_time: time
    end_time: time
    shift: str
    duration_minutes: int
    notes: str
    created_at: datetime

    # Properties
    effective_max_marks: Decimal
    student_count: int
    results_entered_count: int

    # Relationships
    @strawberry_django.field
    def exam(self) -> ExamType:
        return self.exam

    @strawberry_django.field
    def subject(self) -> 'SubjectType':
        return self.subject

    @strawberry_django.field
    def section(self) -> 'SectionType':
        return self.section

    @strawberry_django.field
    def room(self) -> Optional['RoomType']:
        return self.room

    @strawberry_django.field
    def invigilator(self) -> Optional['UserType']:
        return self.invigilator

    @strawberry_django.field
    def results(self) -> List['ExamResultType']:
        return self.results.select_related('student').all()

    @strawberry_django.field
    def seating_arrangements(self) -> List['ExamSeatingType']:
        return self.seating_arrangements.select_related('student', 'room').all()

    # Custom fields
    @strawberry.field
    def shift_display(self) -> str:
        return self.get_shift_display()

    @strawberry.field
    def subject_name(self) -> str:
        return self.subject.name

    @strawberry.field
    def subject_code(self) -> str:
        return self.subject.code


@strawberry_django.type(ExamSeatingArrangement)
class ExamSeatingType:
    """GraphQL type for ExamSeatingArrangement."""
    id: strawberry.ID
    seat_number: str
    is_present: bool
    marked_at: Optional[datetime]
    created_at: datetime

    @strawberry_django.field
    def student(self) -> 'StudentProfileType':
        return self.student

    @strawberry_django.field
    def room(self) -> Optional['RoomType']:
        return self.room

    @strawberry_django.field
    def schedule(self) -> ExamScheduleType:
        return self.schedule

    @strawberry.field
    def student_register_number(self) -> str:
        return self.student.register_number

    @strawberry.field
    def room_number(self) -> Optional[str]:
        return self.room.room_number if self.room else None


@strawberry_django.type(ExamResult)
class ExamResultType:
    """GraphQL type for ExamResult."""
    id: strawberry.ID
    marks_obtained: Optional[Decimal]
    percentage: Optional[Decimal]
    is_pass: bool
    is_absent: bool
    status: str
    remarks: str
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    # Properties
    grade_letter: str

    @strawberry_django.field
    def student(self) -> 'StudentProfileType':
        return self.student

    @strawberry_django.field
    def schedule(self) -> ExamScheduleType:
        return self.schedule

    @strawberry_django.field
    def entered_by(self) -> Optional['UserType']:
        return self.entered_by

    @strawberry_django.field
    def verified_by(self) -> Optional['UserType']:
        return self.verified_by

    @strawberry.field
    def student_register_number(self) -> str:
        return self.student.register_number

    @strawberry.field
    def max_marks(self) -> Decimal:
        return self.schedule.effective_max_marks


@strawberry_django.type(HallTicket)
class HallTicketType:
    """GraphQL type for HallTicket."""
    id: strawberry.ID
    ticket_number: str
    status: str
    is_eligible: bool
    ineligibility_reason: str
    generated_at: datetime
    downloaded_at: Optional[datetime]

    @strawberry_django.field
    def student(self) -> 'StudentProfileType':
        return self.student

    @strawberry_django.field
    def exam(self) -> ExamType:
        return self.exam

    @strawberry.field
    def student_register_number(self) -> str:
        return self.student.register_number


# ==================================================
# RESPONSE / STATISTICS TYPES
# ==================================================

@strawberry.type
class ExamResultStatisticsType:
    """Statistics for exam results."""
    total_students: int
    results_entered: int
    passed: int
    failed: int
    absent: int
    pass_percentage: float
    average_marks: float
    highest_marks: float
    lowest_marks: float


@strawberry.type
class ExamMutationResponse:
    """Standard mutation response for exam operations."""
    success: bool
    message: str


@strawberry.type
class CreateExamResponse:
    success: bool
    message: str
    exam: Optional[ExamType] = None


@strawberry.type
class CreateScheduleResponse:
    success: bool
    message: str
    schedule: Optional[ExamScheduleType] = None


@strawberry.type
class EnterMarksResponse:
    success: bool
    message: str
    result: Optional[ExamResultType] = None


@strawberry.type
class BulkEnterMarksResponse:
    success: bool
    message: str
    count: int = 0


@strawberry.type
class HallTicketResponse:
    success: bool
    message: str
    hall_ticket: Optional[HallTicketType] = None


@strawberry.type
class BulkHallTicketResponse:
    success: bool
    message: str
    count: int = 0


# Import types from other apps (bottom to avoid circular imports)
from timetable.graphql.types import SubjectType, SemesterType, RoomType
from core.graphql.types import SectionType, UserType, DepartmentType
from profile_management.graphql.types import StudentProfileType
