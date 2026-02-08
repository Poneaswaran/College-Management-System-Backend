"""
Validators for timetable entries
Checks for scheduling conflicts before saving
"""
from typing import Dict, Tuple


class TimetableConflictValidator:
    """
    Validates timetable entries for conflicts
    Ensures no double-booking of faculty, rooms, or sections
    """

    @staticmethod
    def validate_entry(entry_data: Dict) -> Tuple[bool, str]:
        """
        Check for scheduling conflicts before creating/updating entry
        
        Args:
            entry_data: Dictionary containing:
                - id: Entry ID (None for new entries)
                - faculty_id: Faculty user ID
                - room_id: Room ID (optional)
                - section_id: Section ID
                - period_definition_id: Period definition ID
                - semester_id: Semester ID
        
        Returns:
            Tuple of (is_valid: bool, error_message: str)
            - (True, "No conflicts found") if valid
            - (False, "Error message") if conflicts exist
        """
        from .models import TimetableEntry, PeriodDefinition
        
        entry_id = entry_data.get('id')
        faculty_id = entry_data.get('faculty_id')
        room_id = entry_data.get('room_id')
        section_id = entry_data.get('section_id')
        period_definition_id = entry_data.get('period_definition_id')
        semester_id = entry_data.get('semester_id')

        # 1. Faculty double-booking check
        if faculty_id:
            faculty_conflict = TimetableEntry.objects.filter(
                faculty_id=faculty_id,
                period_definition_id=period_definition_id,
                semester_id=semester_id,
                is_active=True
            )
            
            # Exclude current entry if updating
            if entry_id:
                faculty_conflict = faculty_conflict.exclude(id=entry_id)
            
            if faculty_conflict.exists():
                return (False, "Faculty is already teaching another class at this time")

        # 2. Room conflict check
        if room_id:
            room_conflict = TimetableEntry.objects.filter(
                room_id=room_id,
                period_definition_id=period_definition_id,
                semester_id=semester_id,
                is_active=True
            )
            
            # Exclude current entry if updating
            if entry_id:
                room_conflict = room_conflict.exclude(id=entry_id)
            
            if room_conflict.exists():
                return (False, "Room is already occupied at this time")

        # 3. Section conflict check
        section_conflict = TimetableEntry.objects.filter(
            section_id=section_id,
            period_definition_id=period_definition_id,
            semester_id=semester_id,
            is_active=True
        )
        
        # Exclude current entry if updating
        if entry_id:
            section_conflict = section_conflict.exclude(id=entry_id)
        
        if section_conflict.exists():
            return (False, "Section already has a class scheduled at this time")

        # 4. Period definition belongs to semester
        try:
            period = PeriodDefinition.objects.get(id=period_definition_id)
            if period.semester_id != semester_id:
                return (False, "Period definition does not belong to the specified semester")
        except PeriodDefinition.DoesNotExist:
            return (False, "Invalid period definition")

        # All checks passed
        return (True, "No conflicts found")
