import strawberry
from typing import Optional

from core.models import (
    Department,
    Course,
    Section,
    Role,
    User,
    StudentProfile,
    ParentProfile,
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


@strawberry.type
class StudentProfileType:
    id: int
    register_number: str
    department: DepartmentType
    course: CourseType
    section: SectionType
    phone_number: Optional[str]


@strawberry.type
class ParentProfileType:
    id: int
    relationship: str
    phone_number: str
    student: StudentProfileType