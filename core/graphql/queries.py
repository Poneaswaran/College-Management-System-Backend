import strawberry
from typing import List, Optional

from core.models import (
    Department,
    Course,
    Section,
    Role,
    User,
    StudentProfile,
)

from .types import (
    DepartmentType,
    CourseType,
    SectionType,
    RoleType,
    UserType,
    StudentProfileType,
)


@strawberry.type
class Query:

    # ==================================================
    # DEPARTMENT
    # ==================================================
    @strawberry.field
    def departments(self) -> List[DepartmentType]:
        return Department.objects.filter(is_active=True)

    # ==================================================
    # COURSE
    # ==================================================
    @strawberry.field
    def courses(
        self,
        department_id: Optional[int] = None
    ) -> List[CourseType]:
        qs = Course.objects.select_related("department")
        if department_id:
            qs = qs.filter(department_id=department_id)
        return qs

    # ==================================================
    # SECTION
    # ==================================================
    @strawberry.field
    def sections(
        self,
        course_id: Optional[int] = None,
        year: Optional[int] = None
    ) -> List[SectionType]:
        qs = Section.objects.select_related(
            "course",
            "course__department"
        )
        if course_id:
            qs = qs.filter(course_id=course_id)
        if year:
            qs = qs.filter(year=year)
        return qs

    # ==================================================
    # ROLE
    # ==================================================
    @strawberry.field
    def roles(
        self,
        department_id: Optional[int] = None
    ) -> List[RoleType]:
        qs = Role.objects.select_related("department").filter(is_active=True)
        if department_id:
            qs = qs.filter(department_id=department_id)
        return qs

    # ==================================================
    # USER
    # ==================================================
    @strawberry.field
    def users(self) -> List[UserType]:
        return User.objects.select_related("role", "department")

    # ==================================================
    # STUDENT
    # ==================================================
    @strawberry.field
    def student_by_register_number(
        self,
        register_number: str
    ) -> Optional[StudentProfileType]:
        return (
            StudentProfile.objects
            .select_related(
                "department",
                "course",
                "section",
                "section__course",
                "section__course__department"
            )
            .filter(register_number=register_number)
            .first()
        )
