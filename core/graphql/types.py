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