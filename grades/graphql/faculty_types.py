"""
GraphQL types for Faculty Grade Submission
Faculty-facing grade entry and submission workflow
"""
import strawberry
from typing import Optional
from enum import Enum


@strawberry.enum
class GradeStatus(Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@strawberry.enum
class GradeExamType(Enum):
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"
    QUIZ = "QUIZ"
    LAB = "LAB"
    ASSIGNMENT = "ASSIGNMENT"


@strawberry.enum
class LetterGrade(Enum):
    O = strawberry.enum_value("O", description="Outstanding (91-100%)")
    A_PLUS = strawberry.enum_value("A+", description="81-90%")
    A = strawberry.enum_value("A", description="71-80%")
    B_PLUS = strawberry.enum_value("B+", description="61-70%")
    B = strawberry.enum_value("B", description="51-60%")
    C = strawberry.enum_value("C", description="41-50%")
    F = strawberry.enum_value("F", description="Fail < 41%")
    ABSENT = strawberry.enum_value("ABSENT", description="Student was absent")
    WITHHELD = strawberry.enum_value("WITHHELD", description="Result withheld")


# ==================================================
# FACULTY GRADES OVERVIEW TYPES
# ==================================================

@strawberry.type
class FacultyGradeSummary:
    total_courses: int
    total_submitted: int
    total_draft: int
    total_pending_approval: int
    total_approved: int
    total_rejected: int
    current_semester_label: str


@strawberry.type
class GradeCourseSection:
    id: int
    subject_code: str
    subject_name: str
    section_name: str
    semester: int
    semester_label: str
    department: str
    exam_type: GradeExamType
    exam_date: str
    internal_max_mark: int
    external_max_mark: int
    total_max_mark: int
    pass_mark: int
    student_count: int
    submitted_count: int
    status: GradeStatus
    last_modified_at: Optional[str] = None
    submitted_at: Optional[str] = None


@strawberry.type
class FacultyGradesData:
    summary: FacultyGradeSummary
    course_sections: list[GradeCourseSection]


# ==================================================
# FACULTY GRADE DETAIL TYPES
# ==================================================

@strawberry.type
class GradeDistributionItem:
    grade: LetterGrade
    count: int
    percentage: float


@strawberry.type
class CourseSectionGradeStats:
    total_students: int
    pass_count: int
    fail_count: int
    absent_count: int
    pass_percentage: float
    avg_mark: float
    highest_mark: float
    lowest_mark: float
    grade_distribution: list[GradeDistributionItem]


@strawberry.type
class StudentGradeRecord:
    student_id: str
    register_number: str
    roll_number: str
    student_name: str
    profile_photo: Optional[str] = None
    internal_mark: Optional[float] = None
    external_mark: Optional[float] = None
    total_mark: Optional[float] = None
    percentage: Optional[float] = None
    letter_grade: Optional[LetterGrade] = None
    grade_point: Optional[float] = None
    is_pass: Optional[bool] = None
    is_absent: bool


@strawberry.type
class FacultyGradeDetailData:
    course_section: GradeCourseSection
    stats: CourseSectionGradeStats
    students: list[StudentGradeRecord]


# ==================================================
# MUTATION INPUT TYPES
# ==================================================

@strawberry.input
class StudentGradeInput:
    student_id: str
    internal_mark: Optional[float] = None
    external_mark: Optional[float] = None
    is_absent: bool


@strawberry.input
class SaveGradesDraftInput:
    course_section_id: int
    grades: list[StudentGradeInput]


@strawberry.input
class SubmitGradesInput:
    course_section_id: int
    grades: list[StudentGradeInput]


# ==================================================
# MUTATION RESULT TYPES
# ==================================================

@strawberry.type
class SaveGradesDraftResult:
    success: bool
    message: str
    updated_at: str


@strawberry.type
class SubmitGradesResult:
    success: bool
    message: str
    submitted_at: str
    status: GradeStatus
