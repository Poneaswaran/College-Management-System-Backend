import strawberry
from typing import Optional

from core.models import (
    Department,
    Course,
    Section,
    Role,
    User,
)


# ==================================================
# TYPE DEFINITIONS
# ==================================================

@strawberry.type
class DepartmentType:
    id: int
    name: str
    code: str
    is_active: bool


@strawberry.type
class CourseType:
    id: int
    name: str
    code: str
    duration_years: int
    department: DepartmentType


@strawberry.type
class SectionType:
    id: int
    name: str
    year: int
    course: CourseType
    
    @strawberry.field
    def semester_id(self) -> Optional[int]:
        """Returns None - sections are not directly tied to semesters"""
        return None


@strawberry.type
class RoleType:
    id: int
    name: str
    code: str
    is_global: bool
    is_active: bool
    department: Optional[DepartmentType]


@strawberry.type
class UserType:
    id: int
    email: Optional[str]
    register_number: Optional[str]
    is_active: bool
    role: RoleType
    department: Optional[DepartmentType]

    @strawberry.field
    def full_name(self) -> str:
        # Check student profile
        if hasattr(self, 'student_profile') and self.student_profile:
            return self.student_profile.full_name
        # Check faculty profile
        if hasattr(self, 'faculty_profile') and self.faculty_profile:
            return self.faculty_profile.full_name
            
        # Fallback names
        if self.email:
            return self.email.split('@')[0]
        if self.register_number:
            return self.register_number
        return "Unknown User"

    @strawberry.field
    def first_name(self) -> str:
        if hasattr(self, 'student_profile') and self.student_profile:
            return self.student_profile.first_name or ""
        if hasattr(self, 'faculty_profile') and self.faculty_profile:
            return self.faculty_profile.first_name or ""
        return getattr(self, 'email', '').split('@')[0] if getattr(self, 'email', None) else "User"

    @strawberry.field
    def last_name(self) -> str:
        if hasattr(self, 'student_profile') and self.student_profile:
            return self.student_profile.last_name or ""
        if hasattr(self, 'faculty_profile') and self.faculty_profile:
            return self.faculty_profile.last_name or ""
        return ""

    @strawberry.field
    def user(self) -> 'UserType':
        return self
