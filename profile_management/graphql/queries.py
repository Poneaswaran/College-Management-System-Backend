"""GraphQL queries for profile management"""
import strawberry
from typing import List, Optional

from profile_management.models import StudentProfile, ParentProfile
from .types import StudentProfileType, ParentProfileType


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
