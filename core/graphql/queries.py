import strawberry
from typing import List, Optional

from core.models import (
    Department,
    Course,
    Section,
    Role,
    User,
)

from .types import (
    DepartmentType,
    CourseType,
    SectionType,
    RoleType,
    UserType,
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
        course_id: Optional[strawberry.ID] = None,
        year: Optional[int] = None,
        subject_id: Optional[strawberry.ID] = None
    ) -> List[SectionType]:
        qs = Section.objects.select_related(
            "course",
            "course__department"
        )
        if course_id:
            qs = qs.filter(course_id=int(course_id))
        if year:
            qs = qs.filter(year=year)
        if subject_id:
            # Filter sections that have timetable entries for this subject
            qs = qs.filter(timetable_entries__subject_id=int(subject_id)).distinct()
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
