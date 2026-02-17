"""
GraphQL types for grades management
"""
import strawberry
import strawberry_django
from typing import Optional
from datetime import date

from grades.models import CourseGrade, SemesterGPA, StudentCGPA
from timetable.graphql.types import SubjectType, SemesterType


@strawberry_django.type(CourseGrade)
class CourseGradeType:
    id: int
    subject: SubjectType
    semester: SemesterType
    internal_marks: float
    internal_max_marks: float
    exam_marks: float
    exam_max_marks: float
    exam_type: str
    exam_date: Optional[date]
    total_marks: float
    total_max_marks: float
    percentage: float
    grade: str
    grade_points: float
    credits: float
    remarks: str
    is_published: bool
    created_at: str
    
    @strawberry_django.field
    def course_code(self) -> str:
        return self.subject.code
    
    @strawberry_django.field
    def course_name(self) -> str:
        return self.subject.name


@strawberry_django.type(SemesterGPA)
class SemesterGPAType:
    id: int
    semester: SemesterType
    gpa: float
    total_credits: float
    credits_earned: float
    
    @strawberry_django.field
    def semester_name(self) -> str:
        return f"{self.semester.get_number_display()} {self.semester.academic_year.year_code}"


@strawberry_django.type(StudentCGPA)
class StudentCGPAType:
    id: int
    cgpa: float
    total_credits: float
    credits_earned: float
    performance_trend: str
