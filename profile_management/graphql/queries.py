"""GraphQL queries for profile management"""
import strawberry
from typing import List, Optional
from strawberry.types import Info

from profile_management.models import StudentProfile, ParentProfile
from .types import StudentProfileType, ParentProfileType
from core.graphql.auth import require_auth


@strawberry.type
class ProfileQuery:

    # ==================================================
    # STUDENT PROFILE QUERIES
    # ==================================================
    
    @strawberry.field
    @require_auth
    def my_profile(self, info: Info, register_number: str) -> Optional[StudentProfileType]:
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
    @require_auth
    def student_profile(self, info: Info, register_number: str) -> Optional[StudentProfileType]:
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
    @require_auth
    def student_profiles(
        self,
        info: Info,
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
