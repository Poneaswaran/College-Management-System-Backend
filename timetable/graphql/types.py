"""
GraphQL types for timetable management
"""
import strawberry
import strawberry_django
from typing import Optional
from datetime import date, time

from profile_management.models import AcademicYear, Semester
from timetable.models import (
    TimetableConfiguration,
    Subject,
    PeriodDefinition,
    Room,
    TimetableEntry
)
from core.graphql.types import DepartmentType, SectionType, UserType


# ==================================================
# ACADEMIC YEAR & SEMESTER TYPES
# ==================================================

@strawberry_django.type(AcademicYear)
class AcademicYearType:
    id: int
    year_code: str
    start_date: date
    end_date: date
    is_current: bool


@strawberry_django.type(Semester)
class SemesterType:
    id: int
    academic_year: AcademicYearType
    number: int
    start_date: date
    end_date: date
    is_current: bool
    
    @strawberry_django.field
    def display_name(self) -> str:
        return self.get_number_display()


# ==================================================
# TIMETABLE CONFIGURATION TYPE
# ==================================================

@strawberry_django.type(TimetableConfiguration)
class TimetableConfigurationType:
    id: int
    semester: SemesterType
    periods_per_day: int
    default_period_duration: int
    day_start_time: time
    day_end_time: time
    lunch_break_after_period: int
    lunch_break_duration: int
    short_break_duration: int
    working_days: strawberry.scalars.JSON


# ==================================================
# SUBJECT TYPE
# ==================================================

@strawberry_django.type(Subject)
class SubjectType:
    id: int
    code: str
    name: str
    department: DepartmentType
    semester_number: int
    credits: float
    subject_type: str
    is_active: bool


# ==================================================
# PERIOD DEFINITION TYPE
# ==================================================

@strawberry_django.type(PeriodDefinition)
class PeriodDefinitionType:
    id: int
    semester: SemesterType
    period_number: int
    day_of_week: int
    start_time: time
    end_time: time
    duration_minutes: int
    
    @strawberry_django.field
    def day_name(self) -> str:
        return self.get_day_of_week_display()


# ==================================================
# ROOM TYPE
# ==================================================

@strawberry_django.type(Room)
class RoomType:
    id: int
    room_number: str
    building: str
    capacity: int
    room_type: str
    department: Optional[DepartmentType]
    facilities: strawberry.scalars.JSON
    is_active: bool


# ==================================================
# TIMETABLE ENTRY TYPE
# ==================================================

@strawberry_django.type(TimetableEntry)
class TimetableEntryType:
    id: int
    section: SectionType
    subject: SubjectType
    faculty: Optional[UserType]
    period_definition: PeriodDefinitionType
    room: Optional[RoomType]
    semester: SemesterType
    is_active: bool
    notes: str
