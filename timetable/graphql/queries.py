"""
GraphQL queries for timetable management
"""
import strawberry
from typing import List, Optional
from strawberry.types import Info

from profile_management.models import Semester
from timetable.models import (
    Subject,
    PeriodDefinition,
    Room,
    TimetableEntry
)
from .types import (
    SemesterType,
    SubjectType,
    PeriodDefinitionType,
    RoomType,
    TimetableEntryType
)
from core.graphql.auth import require_auth


@strawberry.type
class TimetableQuery:
    """
    GraphQL queries for timetable system
    """

    @strawberry.field
    @require_auth
    def current_semester(self, info: Info) -> Optional[SemesterType]:
        """Get the current active semester"""
        return Semester.objects.filter(is_current=True).select_related('academic_year').first()

    @strawberry.field
    @require_auth
    def section_timetable(
        self,
        info: Info,
        section_id: int,
        semester_id: Optional[int] = None
    ) -> List[TimetableEntryType]:
        """
        Get timetable for a specific section
        
        Args:
            section_id: ID of the section
            semester_id: Optional semester ID (defaults to current semester)
        
        Returns:
            List of timetable entries for the section
        """
        # Get semester
        if semester_id:
            semester = Semester.objects.filter(id=semester_id).first()
        else:
            semester = Semester.objects.filter(is_current=True).first()
        
        if not semester:
            return []
        
        # Query entries
        entries = TimetableEntry.objects.filter(
            section_id=section_id,
            semester=semester,
            is_active=True
        ).select_related(
            'subject',
            'subject__department',
            'faculty',
            'faculty__role',
            'faculty__department',
            'room',
            'period_definition',
            'period_definition__semester',
            'section',
            'section__course',
            'semester',
            'semester__academic_year'
        ).order_by(
            'period_definition__day_of_week',
            'period_definition__start_time'
        )
        
        return list(entries)

    @strawberry.field
    @require_auth
    def faculty_schedule(
        self,
        info: Info,
        faculty_id: int,
        semester_id: Optional[int] = None
    ) -> List[TimetableEntryType]:
        """
        Get teaching schedule for a faculty member
        
        Args:
            faculty_id: User ID of the faculty
            semester_id: Optional semester ID (defaults to current semester)
        
        Returns:
            List of classes the faculty is teaching
        """
        # Get semester
        if semester_id:
            semester = Semester.objects.filter(id=semester_id).first()
        else:
            semester = Semester.objects.filter(is_current=True).first()
        
        if not semester:
            return []
        
        # Query entries
        entries = TimetableEntry.objects.filter(
            faculty_id=faculty_id,
            semester=semester,
            is_active=True
        ).select_related(
            'subject',
            'subject__department',
            'section',
            'section__course',
            'room',
            'period_definition',
            'period_definition__semester',
            'semester',
            'semester__academic_year'
        ).order_by(
            'period_definition__day_of_week',
            'period_definition__start_time'
        )
        
        return list(entries)

    @strawberry.field
    @require_auth
    def period_definitions(
        self,
        info: Info,
        semester_id: int,
        day_of_week: Optional[int] = None
    ) -> List[PeriodDefinitionType]:
        """
        Get period definitions for a semester
        
        Args:
            semester_id: ID of the semester
            day_of_week: Optional day filter (1=Mon, 2=Tue, etc.)
        
        Returns:
            List of period definitions
        """
        query = PeriodDefinition.objects.filter(
            semester_id=semester_id
        ).select_related('semester', 'semester__academic_year')
        
        if day_of_week is not None:
            query = query.filter(day_of_week=day_of_week)
        
        return list(query.order_by('day_of_week', 'period_number'))

    @strawberry.field
    @require_auth
    def subjects(
        self,
        info: Info,
        department_id: Optional[int] = None,
        semester_number: Optional[int] = None,
        is_active: Optional[bool] = True
    ) -> List[SubjectType]:
        """
        Get list of subjects with optional filters
        
        Args:
            department_id: Optional department filter
            semester_number: Optional semester number filter (1-8)
            is_active: Filter by active status (default True)
        
        Returns:
            List of subjects
        """
        query = Subject.objects.select_related('department')
        
        if department_id is not None:
            query = query.filter(department_id=department_id)
        
        if semester_number is not None:
            query = query.filter(semester_number=semester_number)
        
        if is_active is not None:
            query = query.filter(is_active=is_active)
        
        return list(query.order_by('code'))

    @strawberry.field
    @require_auth
    def rooms(
        self,
        info: Info,
        room_type: Optional[str] = None,
        department_id: Optional[int] = None,
        is_active: Optional[bool] = True
    ) -> List[RoomType]:
        """
        Get list of rooms with optional filters
        
        Args:
            room_type: Optional room type filter (CLASSROOM, LAB, etc.)
            department_id: Optional department filter
            is_active: Filter by active status (default True)
        
        Returns:
            List of rooms
        """
        query = Room.objects.select_related('department')
        
        if room_type is not None:
            query = query.filter(room_type=room_type)
        
        if department_id is not None:
            query = query.filter(department_id=department_id)
        
        if is_active is not None:
            query = query.filter(is_active=is_active)
        
        return list(query.order_by('building', 'room_number'))

    @strawberry.field
    @require_auth
    def room_schedule(
        self,
        info: Info,
        room_id: int,
        semester_id: Optional[int] = None,
        day_of_week: Optional[int] = None
    ) -> List[TimetableEntryType]:
        """
        Get schedule for a specific room
        
        Args:
            room_id: ID of the room
            semester_id: Optional semester ID (defaults to current)
            day_of_week: Optional day filter (1=Mon, 2=Tue, etc.)
        
        Returns:
            List of classes scheduled in this room
        """
        # Get semester
        if semester_id:
            semester = Semester.objects.filter(id=semester_id).first()
        else:
            semester = Semester.objects.filter(is_current=True).first()
        
        if not semester:
            return []
        
        # Build query
        query = TimetableEntry.objects.filter(
            room_id=room_id,
            semester=semester,
            is_active=True
        ).select_related(
            'subject',
            'subject__department',
            'faculty',
            'section',
            'section__course',
            'period_definition',
            'semester'
        )
        
        if day_of_week is not None:
            query = query.filter(period_definition__day_of_week=day_of_week)
        
        return list(query.order_by(
            'period_definition__day_of_week',
            'period_definition__start_time'
        ))
