"""
Validators for timetable entries.
Checks for scheduling conflicts before saving.

Classes
-------
FacultyConflictChecker
    Standalone checker used by both the scheduler (bulk) and the validator (manual entry).
TimetableConflictValidator
    Full entry validator — room, section, faculty, period-semester alignment.
"""
from typing import Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Faculty Conflict Checker
# ---------------------------------------------------------------------------

class FacultyConflictChecker:
    """
    Determine whether a faculty member is already booked for a given period
    in the given semester.

    Usage (scheduler / bulk path):
        booked = FacultyConflictChecker.is_booked(
            faculty_id=3,
            period_definition_id=12,
            semester_id=1,
        )

    Returns True  → faculty IS already teaching another class → CONFLICT.
    Returns False → faculty is free.
    """

    @staticmethod
    def is_booked(
        faculty_id: int,
        period_definition_id: int,
        semester_id: int,
        exclude_entry_id: Optional[int] = None,
    ) -> bool:
        """
        Return True if the faculty already has a TimetableEntry at this slot.

        Parameters
        ----------
        faculty_id            : PK of the User (faculty)
        period_definition_id  : PK of the PeriodDefinition
        semester_id           : PK of the Semester
        exclude_entry_id      : Exclude this TimetableEntry PK (for updates)
        """
        from .models import TimetableEntry  # lazy to avoid circular import

        qs = TimetableEntry.objects.filter(
            faculty_id=faculty_id,
            period_definition_id=period_definition_id,
            semester_id=semester_id,
            is_active=True,
        )
        if exclude_entry_id is not None:
            qs = qs.exclude(pk=exclude_entry_id)
        return qs.exists()

    @staticmethod
    def conflict_description(
        faculty_id: int,
        period_definition_id: int,
        semester_id: int,
        exclude_entry_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        Return a human-readable conflict string, or None if no conflict.
        Includes the conflicting section name for actionable diagnostics.
        """
        from .models import TimetableEntry  # lazy to avoid circular import

        qs = TimetableEntry.objects.filter(
            faculty_id=faculty_id,
            period_definition_id=period_definition_id,
            semester_id=semester_id,
            is_active=True,
        ).select_related('section', 'faculty')
        if exclude_entry_id is not None:
            qs = qs.exclude(pk=exclude_entry_id)

        conflict = qs.first()
        if conflict is None:
            return None

        faculty_name = (
            conflict.faculty.get_full_name() if conflict.faculty else f"ID {faculty_id}"
        )
        return (
            f"Faculty '{faculty_name}' is already teaching "
            f"section '{conflict.section}' at this period."
        )


# ---------------------------------------------------------------------------
# Timetable Entry Conflict Validator
# ---------------------------------------------------------------------------

class TimetableConflictValidator:
    """
    Validates timetable entries for conflicts.
    Ensures no double-booking of faculty, rooms, or sections.

    Also called from TimetableEntry.clean() so every manual admin/API save
    is validated identically to bulk scheduler saves.
    """

    @staticmethod
    def validate_entry(entry_data: Dict) -> Tuple[bool, str]:
        """
        Check for scheduling conflicts before creating / updating an entry.

        Parameters
        ----------
        entry_data : dict with keys:
            id                    – Entry PK (None for new entries)
            faculty_id            – Faculty user ID (optional)
            room_id               – Room ID (optional)
            section_id            – Section ID
            period_definition_id  – PeriodDefinition ID
            semester_id           – Semester ID

        Returns
        -------
        (True,  "No conflicts found")  if valid
        (False, "<error message>")     if a conflict is detected
        """
        from .models import TimetableEntry, PeriodDefinition  # lazy imports

        entry_id             = entry_data.get('id')
        faculty_id           = entry_data.get('faculty_id')
        room_id              = entry_data.get('room_id')
        section_id           = entry_data.get('section_id')
        period_definition_id = entry_data.get('period_definition_id')
        semester_id          = entry_data.get('semester_id')

        # 1. Faculty double-booking check (uses FacultyConflictChecker)
        if faculty_id:
            conflict_msg = FacultyConflictChecker.conflict_description(
                faculty_id=faculty_id,
                period_definition_id=period_definition_id,
                semester_id=semester_id,
                exclude_entry_id=entry_id,
            )
            if conflict_msg:
                return (False, conflict_msg)

        # 2. Room conflict check
        if room_id:
            room_conflict = TimetableEntry.objects.filter(
                room_id=room_id,
                period_definition_id=period_definition_id,
                semester_id=semester_id,
                is_active=True,
            )
            if entry_id:
                room_conflict = room_conflict.exclude(pk=entry_id)
            if room_conflict.exists():
                return (False, "Room is already occupied at this time")

        # 3. Section conflict check
        section_conflict = TimetableEntry.objects.filter(
            section_id=section_id,
            period_definition_id=period_definition_id,
            semester_id=semester_id,
            is_active=True,
        )
        if entry_id:
            section_conflict = section_conflict.exclude(pk=entry_id)
        if section_conflict.exists():
            return (False, "Section already has a class scheduled at this time")

        # 4. Period definition belongs to semester
        try:
            period = PeriodDefinition.objects.get(pk=period_definition_id)
            if period.semester_id != semester_id:
                return (
                    False,
                    "Period definition does not belong to the specified semester",
                )
        except PeriodDefinition.DoesNotExist:
            return (False, "Invalid period definition")

        return (True, "No conflicts found")
