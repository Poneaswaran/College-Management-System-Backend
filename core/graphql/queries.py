import strawberry
from typing import List, Optional
from strawberry.types import Info

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
from .auth import require_auth


@strawberry.type
class Query:

    # ==================================================
    # DEPARTMENT
    # ==================================================
    @strawberry.field
    @require_auth
    def departments(self, info: Info) -> List[DepartmentType]:
        return Department.objects.filter(is_active=True)

    # ==================================================
    # COURSE
    # ==================================================
    @strawberry.field
    @require_auth
    def courses(
        self,
        info: Info,
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
    @require_auth
    def sections(
        self,
        info: Info,
        course_id: Optional[int] = None,
        year: Optional[int] = None,
        subject_id: Optional[int] = None
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
    @require_auth
    def roles(
        self,
        info: Info,
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
    @require_auth
    def users(self, info: Info) -> List[UserType]:
        return User.objects.select_related("role", "department")
    
    @strawberry.field
    @require_auth
    def me(self, info: Info) -> Optional[UserType]:
        """
        Get current authenticated user info
        Used for page refresh to restore auth state
        Requires valid JWT token in Authorization header
        """
        return info.context.request.user
