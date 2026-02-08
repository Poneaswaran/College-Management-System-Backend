"""
Utility functions for timetable management
"""
from datetime import datetime, timedelta, time
from typing import List, Optional

from profile_management.models import Semester
from .models import TimetableConfiguration, PeriodDefinition


def generate_periods_for_config(config: TimetableConfiguration) -> List[PeriodDefinition]:
    """
    Auto-generate period definitions based on configuration
    
    Args:
        config: TimetableConfiguration instance
    
    Returns:
        List of created PeriodDefinition objects
    """
    created_periods = []
    
    # Loop through each working day
    for day_num in config.working_days:
        # Start from day_start_time
        current_time = datetime.combine(datetime.today(), config.day_start_time)
        
        # Generate periods for this day
        for period_num in range(1, config.periods_per_day + 1):
            # Calculate start and end time
            start_time = current_time.time()
            
            # Add period duration
            end_datetime = current_time + timedelta(minutes=config.default_period_duration)
            end_time = end_datetime.time()
            
            # Create or get period definition
            period, created = PeriodDefinition.objects.get_or_create(
                semester=config.semester,
                period_number=period_num,
                day_of_week=day_num,
                defaults={
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_minutes': config.default_period_duration
                }
            )
            
            if created:
                created_periods.append(period)
            
            # Move to next period
            current_time = end_datetime
            
            # Add short break after each period (except last)
            if period_num < config.periods_per_day:
                current_time += timedelta(minutes=config.short_break_duration)
            
            # Add lunch break after specified period
            if period_num == config.lunch_break_after_period:
                current_time += timedelta(minutes=config.lunch_break_duration)
    
    return created_periods


def get_current_period(section, datetime_obj: datetime) -> Optional[PeriodDefinition]:
    """
    Get which period is currently active for a section
    
    Args:
        section: Section instance
        datetime_obj: datetime object to check
    
    Returns:
        PeriodDefinition if a period is active, None otherwise
    """
    # Get current semester
    current_semester = Semester.objects.filter(is_current=True).first()
    if not current_semester:
        return None
    
    # Extract day of week (1=Monday, 7=Sunday)
    day_of_week = datetime_obj.isoweekday()
    
    # Extract current time
    current_time = datetime_obj.time()
    
    # Find matching period
    period = PeriodDefinition.objects.filter(
        semester=current_semester,
        day_of_week=day_of_week,
        start_time__lte=current_time,
        end_time__gte=current_time
    ).first()
    
    return period


def get_section_timetable_grid(section, semester):
    """
    Get timetable organized as a grid (day x period)
    
    Args:
        section: Section instance
        semester: Semester instance
    
    Returns:
        Dictionary with structure:
        {
            'Monday': {1: entry, 2: entry, ...},
            'Tuesday': {...},
            ...
        }
    """
    from .models import TimetableEntry
    
    # Get all entries for this section
    entries = TimetableEntry.objects.filter(
        section=section,
        semester=semester,
        is_active=True
    ).select_related(
        'subject',
        'faculty',
        'room',
        'period_definition'
    ).order_by(
        'period_definition__day_of_week',
        'period_definition__period_number'
    )
    
    # Organize into grid
    grid = {}
    for entry in entries:
        day_name = entry.period_definition.day_name
        period_num = entry.period_definition.period_number
        
        if day_name not in grid:
            grid[day_name] = {}
        
        grid[day_name][period_num] = entry
    
    return grid


def check_faculty_availability(faculty_id: int, period_definition_id: int, semester_id: int, exclude_entry_id: Optional[int] = None) -> bool:
    """
    Check if faculty is available at a given period
    
    Args:
        faculty_id: User ID of faculty
        period_definition_id: PeriodDefinition ID
        semester_id: Semester ID
        exclude_entry_id: Optional entry ID to exclude (for updates)
    
    Returns:
        True if available, False if already booked
    """
    from .models import TimetableEntry
    
    query = TimetableEntry.objects.filter(
        faculty_id=faculty_id,
        period_definition_id=period_definition_id,
        semester_id=semester_id,
        is_active=True
    )
    
    if exclude_entry_id:
        query = query.exclude(id=exclude_entry_id)
    
    return not query.exists()


def check_room_availability(room_id: int, period_definition_id: int, semester_id: int, exclude_entry_id: Optional[int] = None) -> bool:
    """
    Check if room is available at a given period
    
    Args:
        room_id: Room ID
        period_definition_id: PeriodDefinition ID
        semester_id: Semester ID
        exclude_entry_id: Optional entry ID to exclude (for updates)
    
    Returns:
        True if available, False if already booked
    """
    from .models import TimetableEntry
    
    query = TimetableEntry.objects.filter(
        room_id=room_id,
        period_definition_id=period_definition_id,
        semester_id=semester_id,
        is_active=True
    )
    
    if exclude_entry_id:
        query = query.exclude(id=exclude_entry_id)
    
    return not query.exists()
