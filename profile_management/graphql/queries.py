"""GraphQL queries for profile management"""
import strawberry
from typing import List, Optional

from profile_management.models import StudentProfile, ParentProfile, AcademicYear, Semester
from .types import StudentProfileType, ParentProfileType
from timetable.graphql.types import AcademicYearType, SemesterType


@strawberry.type
class ProfileQuery:

    # ==================================================
    # STUDENT PROFILE QUERIES
    # ==================================================
    
    @strawberry.field
    def my_profile(self, register_number: str) -> Optional[StudentProfileType]:
        """Get student's own profile"""
        return (
            StudentProfile.objects
            .select_related(
                "user",
                "user__role",
                "user__department",
                "department",
                "course",
                "section",
                "section__course"
            )
            .filter(register_number=register_number)
            .first()
        )
    
    @strawberry.field
    def student_profile(self, register_number: str) -> Optional[StudentProfileType]:
        """Get student profile by register number"""
        return (
            StudentProfile.objects
            .select_related(
                "user",
                "user__role",
                "user__department",
                "department",
                "course",
                "section",
                "section__course"
            )
            .filter(register_number=register_number)
            .first()
        )
    
    @strawberry.field
    def student_profiles(
        self,
        department_id: Optional[int] = None,
        course_id: Optional[int] = None,
        year: Optional[int] = None,
        academic_status: Optional[str] = None
    ) -> List[StudentProfileType]:
        """Get list of student profiles with filters"""
        qs = StudentProfile.objects.select_related(
            "user",
            "user__role",
            "user__department",
            "department",
            "course",
            "section"
        )
        
        if department_id:
            qs = qs.filter(department_id=department_id)
        if course_id:
            qs = qs.filter(course_id=course_id)
        if year:
            qs = qs.filter(year=year)
        if academic_status:
            qs = qs.filter(academic_status=academic_status)
            
        return qs
    
    # ==================================================
    # ACADEMIC YEAR QUERIES
    # ==================================================
    
    @strawberry.field
    def academic_years(self) -> List[AcademicYearType]:
        """Get all academic years"""
        return AcademicYear.objects.all()
    
    @strawberry.field
    def current_academic_year(self) -> Optional[AcademicYearType]:
        """Get the current academic year"""
        return AcademicYear.objects.filter(is_current=True).first()
    
    @strawberry.field
    def academic_year(self, id: int) -> Optional[AcademicYearType]:
        """Get academic year by ID"""
        return AcademicYear.objects.filter(id=id).first()
    
    # ==================================================
    # SEMESTER QUERIES
    # ==================================================
    
    @strawberry.field
    def semesters(self, academic_year_id: Optional[int] = None) -> List[SemesterType]:
        """Get all semesters, optionally filtered by academic year"""
        qs = Semester.objects.select_related('academic_year')
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        return qs
    
    @strawberry.field
    def current_semester(self) -> Optional[SemesterType]:
        """Get the current semester"""
        return Semester.objects.select_related('academic_year').filter(is_current=True).first()
    
    @strawberry.field
    def semester(self, id: int) -> Optional[SemesterType]:
        """Get semester by ID"""
        return Semester.objects.select_related('academic_year').filter(id=id).first()
