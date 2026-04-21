"""
timetable/services.py

Service layer for the timetable application.

Classes
-------
TimetableService            — CRUD helpers (existing, preserved)
SubjectDistributionService  — Item 2: fills the grid with subjects before room allocation
RescheduleService           — Item 4: handles mid-semester room maintenance changes
TimetableExportService      — Item 6: renders a section timetable as a PDF
TimetableViolationNotifier  — Item 8: pushes violation alerts to HOD/ADMIN users
"""

import logging
from datetime import date, timedelta, datetime
from typing import Optional

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from campus_management.services import ResourceAllocationService
from campus_management.models import Resource
from timetable.models import (
    TimetableEntry,
    PeriodDefinition,
    CombinedClassSession,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# EXISTING SERVICE (preserved)
# ===========================================================================

class TimetableService:
    @staticmethod
    @transaction.atomic
    def create_timetable_entry(
        section_id: int,
        subject_id: int,
        faculty_id: int,
        period_definition_id: int,
        semester_id: int,
        room_id: int = None,
        notes: str = ""
    ) -> TimetableEntry:
        """
        Business logic to create a new timetable entry.
        Integrates with campus_management for room allocation.
        """
        allocation_id = None
        if room_id:
            try:
                resource = Resource.objects.get(resource_type='ROOM', reference_id=room_id)
            except Resource.DoesNotExist:
                resource = Resource.objects.create(resource_type='ROOM', reference_id=room_id)

            # Fetch period to get timings for allocation
            try:
                period = PeriodDefinition.objects.get(id=period_definition_id)
            except PeriodDefinition.DoesNotExist:
                raise ValidationError("Invalid period definition ID.")

            # Create a representative dummy datetime for weekly recurring class
            dummy_date = datetime(1900, 1, period.day_of_week)
            start_time = datetime.combine(dummy_date, period.start_time)
            end_time = datetime.combine(dummy_date, period.end_time)

            allocation_result = ResourceAllocationService.allocate(
                resource=resource,
                start_time=start_time,
                end_time=end_time,
                allocation_type='CLASS',
                source_app='timetable',
                source_id=0  # Temporary, will update after save
            )

            if not allocation_result['success']:
                raise ValidationError(f"Room allocation failed: {allocation_result['error']}")

            allocation_id = allocation_result['allocation'].id

        # Create entry instance
        entry = TimetableEntry(
            section_id=section_id,
            subject_id=subject_id,
            faculty_id=faculty_id,
            period_definition_id=period_definition_id,
            semester_id=semester_id,
            room_id=room_id,
            allocation_id=allocation_id,
            notes=notes or "",
            is_active=True
        )

        # Validation (triggers custom model clean logic)
        entry.full_clean()
        entry.save()

        if allocation_id:
            allocation = allocation_result['allocation']
            allocation.source_id = entry.id
            allocation.save()

        return entry

    @staticmethod
    @transaction.atomic
    def bulk_create_timetable_entries(section_id: int, semester_id: int, entries_data: list):
        """
        Creates multiple timetable entries for a section in one transaction.
        """
        created_entries = []
        errors = []

        for idx, item in enumerate(entries_data):
            try:
                entry = TimetableService.create_timetable_entry(
                    section_id=section_id,
                    semester_id=semester_id,
                    subject_id=item.get('subject_id'),
                    faculty_id=item.get('faculty_id'),
                    period_definition_id=item.get('period_definition_id'),
                    room_id=item.get('room_id'),
                    notes=item.get('notes', "")
                )
                created_entries.append(entry)
            except ValidationError as e:
                errors.append(f"Entry {idx + 1}: {str(e)}")
            except Exception as e:
                errors.append(f"Entry {idx + 1}: Generic error - {str(e)}")

        if errors:
            # If any entry fails, rollback occurs due to @transaction.atomic
            raise ValidationError(errors)

        return created_entries

    @staticmethod
    def get_section_timetable(section_id: int, semester_id: int):
        """
        Fetch the full timetable for a section, organized chronologically.
        """
        return TimetableEntry.objects.filter(
            section_id=section_id,
            semester_id=semester_id,
            is_active=True
        ).select_related(
            'subject', 'faculty', 'room', 'period_definition'
        ).order_by('period_definition__day_of_week', 'period_definition__start_time')

    @staticmethod
    def get_faculty_timetable(faculty_id: int, semester_id: int):
        """
        Fetch the teaching schedule for a faculty member.
        """
        return TimetableEntry.objects.filter(
            faculty_id=faculty_id,
            semester_id=semester_id,
            is_active=True
        ).select_related(
            'section', 'section__course', 'subject', 'room', 'period_definition'
        ).order_by('period_definition__day_of_week', 'period_definition__start_time')

    @staticmethod
    def get_section_combined_sessions(section_id: int, semester_id: int):
        return CombinedClassSession.objects.filter(
            semester_id=semester_id,
            sections__id=section_id,
            is_active=True,
        ).select_related(
            'subject', 'faculty', 'room', 'period_definition', 'semester'
        ).prefetch_related('sections').order_by(
            'period_definition__day_of_week', 'period_definition__start_time'
        )

    @staticmethod
    def get_faculty_combined_sessions(faculty_id: int, semester_id: int):
        return CombinedClassSession.objects.filter(
            semester_id=semester_id,
            faculty_id=faculty_id,
            is_active=True,
        ).select_related(
            'subject', 'faculty', 'room', 'period_definition', 'semester'
        ).prefetch_related('sections').order_by(
            'period_definition__day_of_week', 'period_definition__start_time'
        )

    @staticmethod
    @transaction.atomic
    def assign_room_to_entry(entry: TimetableEntry, room_id: Optional[int]) -> TimetableEntry:
        """Assign or clear a room for an existing entry.

        This is the canonical path to keep `allocation_id` consistent with
        `campus_management`.

        - If `room_id` is None: clears room + releases allocation if present.
        - If `room_id` is set: releases any previous allocation, allocates the
          new room via `ResourceAllocationService`, then saves.
        """
        from campus_management.services import ResourceAllocationService

        # Release any previous allocation
        if entry.allocation_id:
            ResourceAllocationService.release(entry.allocation_id)
            entry.allocation_id = None

        if room_id is None:
            entry.room_id = None
            entry.full_clean()
            entry.save(update_fields=['room', 'allocation_id', 'updated_at'])
            return entry

        # Ensure the resource exists for this room
        try:
            resource = Resource.objects.get(resource_type='ROOM', reference_id=room_id)
        except Resource.DoesNotExist:
            resource = Resource.objects.create(resource_type='ROOM', reference_id=room_id)

        # Use the same dummy-datetime approach as manual creation
        period = entry.period_definition
        dummy_date = datetime(1900, 1, period.day_of_week)
        start_time = datetime.combine(dummy_date, period.start_time)
        end_time = datetime.combine(dummy_date, period.end_time)

        allocation_result = ResourceAllocationService.allocate(
            resource=resource,
            start_time=start_time,
            end_time=end_time,
            allocation_type='CLASS',
            source_app='timetable',
            source_id=entry.id,
        )
        if not allocation_result['success']:
            raise ValidationError(f"Room allocation failed: {allocation_result['error']}")

        entry.room_id = room_id
        entry.allocation_id = allocation_result['allocation'].id
        entry.full_clean()
        entry.save(update_fields=['room', 'allocation_id', 'updated_at'])
        return entry

    @staticmethod
    @transaction.atomic
    def assign_room_to_combined_session(session: CombinedClassSession, room_id: Optional[int]) -> CombinedClassSession:
        """Assign or clear a room for an existing combined class session.

        Mirrors `assign_room_to_entry` so `allocation_id` stays consistent.
        """

        # Release any previous allocation
        if session.allocation_id:
            ResourceAllocationService.release(session.allocation_id)
            session.allocation_id = None

        if room_id is None:
            session.room_id = None
            session.full_clean()
            session.save(update_fields=['room', 'allocation_id', 'updated_at'])
            return session

        try:
            resource = Resource.objects.get(resource_type='ROOM', reference_id=room_id)
        except Resource.DoesNotExist:
            resource = Resource.objects.create(resource_type='ROOM', reference_id=room_id)

        period = session.period_definition
        dummy_date = datetime(1900, 1, period.day_of_week)
        start_time = datetime.combine(dummy_date, period.start_time)
        end_time = datetime.combine(dummy_date, period.end_time)

        allocation_result = ResourceAllocationService.allocate(
            resource=resource,
            start_time=start_time,
            end_time=end_time,
            allocation_type='CLASS',
            source_app='timetable',
            source_id=session.id,
        )
        if not allocation_result['success']:
            raise ValidationError(f"Room allocation failed: {allocation_result['error']}")

        session.room_id = room_id
        session.allocation_id = allocation_result['allocation'].id
        session.full_clean()
        session.save(update_fields=['room', 'allocation_id', 'updated_at'])
        return session

    @staticmethod
    @transaction.atomic
    def create_combined_class_session(
        *,
        semester_id: int,
        period_definition_id: int,
        subject_id: int,
        faculty_id: Optional[int],
        room_id: Optional[int],
        section_ids: list[int],
        notes: str = "",
        created_by_id: Optional[int] = None,
        supersede_timetable_entries: bool = True,
    ) -> CombinedClassSession:
        if len(section_ids) != 2:
            raise ValidationError("Exactly 2 sections are required.")

        session = CombinedClassSession.objects.create(
            semester_id=semester_id,
            period_definition_id=period_definition_id,
            subject_id=subject_id,
            faculty_id=faculty_id,
            room_id=None,
            allocation_id=None,
            notes=notes or "",
            is_active=True,
            created_by_id=created_by_id,
        )
        session.sections.set(section_ids)

        if room_id is not None:
            TimetableService.assign_room_to_combined_session(session, room_id)

        if supersede_timetable_entries:
            # Deactivate matching entries and release their allocations.
            entries = TimetableEntry.objects.filter(
                section_id__in=section_ids,
                semester_id=semester_id,
                period_definition_id=period_definition_id,
                subject_id=subject_id,
                is_active=True,
            ).select_related('period_definition')

            for entry in entries:
                if entry.room_id or entry.allocation_id:
                    TimetableService.assign_room_to_entry(entry, None)
                entry.is_active = False
                entry.notes = (entry.notes or "").strip()
                suffix = f"Superseded by combined session #{session.id}."
                entry.notes = (entry.notes + ("\n" if entry.notes else "") + suffix)
                entry.save(update_fields=['is_active', 'notes', 'updated_at'])

        return session


# ===========================================================================
# Item 2 — Subject Distribution Service
# ===========================================================================

class SubjectDistributionService:
    """
    Fills the timetable grid with subjects and faculty assignments for a
    section, respecting:
      • Lab subjects → only into the section's assigned LabRotationSchedule slot
      • Theory subjects → remaining available PeriodDefinition slots
      • Faculty availability checked via FacultyConflictChecker

    The produced TimetableEntry objects are NOT saved until
    commit_distribution() is called so callers can inspect them first.
    """

    @staticmethod
    def distribute(section_id: int, semester_id: int) -> list:
        """
        Build unsaved TimetableEntry objects for the section.

        Returns
        -------
        List of unsaved TimetableEntry instances ready for review.
        Raises ValidationError if requirements cannot be satisfied.
        """
        from timetable.models import (
            SectionSubjectRequirement,
            LabRotationSchedule,
            NonRoomPeriod,
        )
        from timetable.validators import FacultyConflictChecker
        from core.models import Section

        section = Section.objects.get(pk=section_id)

        # All requirements for this section/semester, sorted so LABs come first
        requirements = list(
            SectionSubjectRequirement.objects.filter(
                section_id=section_id,
                semester_id=semester_id,
            ).select_related('subject', 'faculty')
            .order_by('subject__subject_type')  # 'LAB' < 'THEORY' alphabetically
        )

        if not requirements:
            raise ValidationError(
                f"No SectionSubjectRequirement rows found for "
                f"section {section_id} in semester {semester_id}."
            )

        # Find the section's lab slot (if any)
        lab_rotation = (
            LabRotationSchedule.objects.filter(
                section_id=section_id,
                semester_id=semester_id,
                is_active=True,
            )
            .select_related('period_definition')
            .first()
        )

        # All periods for the semester, ordered
        all_periods = list(
            PeriodDefinition.objects.filter(semester_id=semester_id)
            .order_by('day_of_week', 'period_number')
        )

        # Period IDs already blocked for this section (lab/PT/library/free)
        blocked_period_ids: set[int] = set(
            NonRoomPeriod.objects.filter(
                section_id=section_id,
                semester_id=semester_id,
            ).values_list('period_definition_id', flat=True)
        )

        # Period IDs already used by existing TimetableEntry rows for this section
        used_period_ids: set[int] = set(
            TimetableEntry.objects.filter(
                section_id=section_id,
                semester_id=semester_id,
                is_active=True,
            ).values_list('period_definition_id', flat=True)
        )

        # Available theory slots = all_periods minus blocked minus already scheduled
        theory_slots = [
            p for p in all_periods
            if p.id not in blocked_period_ids and p.id not in used_period_ids
        ]

        planned_entries: list[TimetableEntry] = []
        # Track faculty bookings within this planning pass to detect intra-run conflicts
        faculty_period_used: set[tuple[int, int]] = set()  # (faculty_id, period_id)

        for req in requirements:
            is_lab = (req.subject.subject_type == 'LAB')
            periods_needed = req.periods_per_week

            if is_lab:
                # Lab subjects go into the LabRotationSchedule slot only
                if lab_rotation is None:
                    raise ValidationError(
                        f"No LabRotationSchedule found for section {section_id}. "
                        "Run LabRotationGenerator first."
                    )
                lab_period = lab_rotation.period_definition
                # Check faculty availability (DB + in-run)
                if req.faculty_id:
                    if FacultyConflictChecker.is_booked(
                        faculty_id=req.faculty_id,
                        period_definition_id=lab_period.id,
                        semester_id=semester_id,
                    ) or (req.faculty_id, lab_period.id) in faculty_period_used:
                        raise ValidationError(
                            f"Faculty conflict: {req.faculty} is already booked "
                            f"at lab slot {lab_period} for section {section_id}."
                        )
                    faculty_period_used.add((req.faculty_id, lab_period.id))

                entry = TimetableEntry(
                    section_id=section_id,
                    subject=req.subject,
                    faculty=req.faculty,
                    period_definition=lab_period,
                    semester_id=semester_id,
                    room=lab_rotation.lab,   # lab room pre-assigned
                    is_active=True,
                )
                planned_entries.append(entry)

            else:
                # Theory/tutorial/elective — fill from available theory slots
                slots_assigned = 0
                remaining_theory = [s for s in theory_slots if s.id not in used_period_ids]

                for slot in remaining_theory:
                    if slots_assigned >= periods_needed:
                        break

                    # Faculty conflict check
                    if req.faculty_id:
                        if FacultyConflictChecker.is_booked(
                            faculty_id=req.faculty_id,
                            period_definition_id=slot.id,
                            semester_id=semester_id,
                        ) or (req.faculty_id, slot.id) in faculty_period_used:
                            continue  # try next slot
                        faculty_period_used.add((req.faculty_id, slot.id))

                    entry = TimetableEntry(
                        section_id=section_id,
                        subject=req.subject,
                        faculty=req.faculty,
                        period_definition=slot,
                        semester_id=semester_id,
                        # Room will be filled later by RoomAllocatorService
                        is_active=True,
                    )
                    planned_entries.append(entry)
                    used_period_ids.add(slot.id)
                    slots_assigned += 1

                if slots_assigned < periods_needed:
                    raise ValidationError(
                        f"Could not find {periods_needed} available slots for "
                        f"subject {req.subject.code} in section {section_id}. "
                        f"Only {slots_assigned} slots assigned."
                    )

        return planned_entries

    @staticmethod
    @transaction.atomic
    def commit_distribution(entries: list) -> list:
        """
        Bulk-save the TimetableEntry objects produced by distribute().

        All entries are saved inside a single transaction; any failure
        rolls back the entire batch.

        Returns saved entry instances.
        """
        saved = []
        for entry in entries:
            # Validate before save (triggers TimetableEntry.clean())
            # Only skip the allocation_id check for room-less entries
            if entry.room_id is None:
                entry.allocation_id = None  # explicitly None, no bypass needed
            entry.save()
            saved.append(entry)
        return saved


# ===========================================================================
# Item 4 — Reschedule Service
# ===========================================================================

class RescheduleService:
    """
    Handles partial mid-semester changes triggered by room maintenance blocks.

    reschedule_affected_periods(room_id, start_date, end_date):
      1. Identifies the days-of-week covered by [start_date, end_date].
      2. Finds TimetableEntry rows where the room is booked on those days.
      3. Nullifies the room assignment on those entries.
      4. Re-runs RoomAllocatorService.allocate_period() for the affected slots.
      5. Logs new overflows; returns a summary dict.
    """

    @staticmethod
    @transaction.atomic
    def reschedule_affected_periods(
        room_id: int,
        start_date: date,
        end_date: date,
    ) -> dict:
        """
        Parameters
        ----------
        room_id     : PK of the Room going under maintenance
        start_date  : inclusive start of maintenance window
        end_date    : inclusive end of maintenance window

        Returns
        -------
        {
            'entries_nullified': int,
            'periods_reallocated': int,
            'new_overflow_count': int,
            'violations': [str, ...],
        }
        """
        from timetable.models import Room
        from timetable.scheduler import RoomAllocatorService

        # Collect days-of-week covered by the maintenance window
        affected_days: set[int] = set()
        current = start_date
        while current <= end_date:
            affected_days.add(current.isoweekday())  # 1=Mon…7=Sun
            current += timedelta(days=1)

        # Find TimetableEntry rows that use this room during those days
        affected_entries = list(
            TimetableEntry.objects.filter(
                room_id=room_id,
                is_active=True,
                period_definition__day_of_week__in=affected_days,
            ).select_related('period_definition', 'semester')
        )

        if not affected_entries:
            return {
                'entries_nullified': 0,
                'periods_reallocated': 0,
                'new_overflow_count': 0,
                'violations': [],
            }

        # Collect unique (semester_id, period_definition_id) pairs to reallocate
        slots_to_reallocate: set[tuple[int, int]] = set()
        for entry in affected_entries:
            slots_to_reallocate.add(
                (entry.semester_id, entry.period_definition_id)
            )

        # Nullify room assignments
        entry_ids = [e.pk for e in affected_entries]
        TimetableEntry.objects.filter(pk__in=entry_ids).update(
            room=None,
            allocation_id=None,
        )

        # Re-run room allocator for affected slots
        all_violations: list[str] = []
        new_overflow_count = 0

        for semester_id, period_definition_id in slots_to_reallocate:
            result = RoomAllocatorService.allocate_period(
                semester_id=semester_id,
                period_definition_id=period_definition_id,
                overflow_date=start_date,  # use maintenance start as the overflow date
            )
            all_violations.extend(result['violations'])
            new_overflow_count += len(result['overflow'])

        # Push violation notifications (Item 8)
        if all_violations:
            # Use the semester from the first affected entry
            first_semester_id = affected_entries[0].semester_id
            TimetableViolationNotifier.notify(all_violations, first_semester_id)

        return {
            'entries_nullified': len(entry_ids),
            'periods_reallocated': len(slots_to_reallocate),
            'new_overflow_count': new_overflow_count,
            'violations': all_violations,
        }


# ===========================================================================
# Item 6 — Timetable Export Service (PDF via ReportLab)
# ===========================================================================

class TimetableExportService:
    """
    Generates a high-fidelity PDF version of a section's weekly timetable grid
    matching the institution's official format.
    """

    DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    @staticmethod
    def generate_pdf(section_id: int, semester_id: int) -> bytes:
        """
        Build the high-fidelity PDF and return the raw bytes.
        """
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Frame, PageTemplate,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        except ImportError as exc:
            raise ImportError(
                "ReportLab is required for PDF export. "
                "Install it with: pip install reportlab"
            ) from exc

        import io
        from timetable.utils import get_section_timetable_grid
        from core.models import Section
        from profile_management.models import Semester, SectionIncharge, FacultyProfile

        section = Section.objects.select_related('course', 'course__department').get(pk=section_id)
        semester = Semester.objects.select_related('academic_year').get(pk=semester_id)
        grid = get_section_timetable_grid(section, semester)
        
        # -- Fetch Tenant / Institution Info (from django-tenants) ----------
        from django.db import connection as db_connection
        tenant = db_connection.tenant  # Client instance for the current request
        dept = section.course.department

        university_name = tenant.name.upper()
        school_name = (dept.school_name or tenant.name).upper()
        dept_name = f"DEPARTMENT OF {dept.name.upper()}"
        
        # ── Fetch Meta Info (In-Charge, Room) ──────────────────────────────
        in_charge_obj = SectionIncharge.objects.filter(section=section, semester=semester).select_related('faculty').first()
        in_charge_name = in_charge_obj.faculty.get_full_name() if in_charge_obj else "Not Assigned"
        
        # Determine rooms used (show primary room or list if multiple)
        rooms_used = set()
        for day_data in grid.values():
            for entry in day_data.values():
                if entry.room:
                    rooms_used.add(entry.room.room_number)
        room_display = ", ".join(sorted(list(rooms_used))) if rooms_used else "N/A"
        
        # ── Prepare Grid Data ──────────────────────────────────────────────
        days_present = [d for d in TimetableExportService.DAY_ORDER if d in grid or (d != 'Sunday' and d != 'Saturday')]
        if len(days_present) > 6: days_present = days_present[:6] # Mon-Sat max

        # Get all periods for this semester to build headers
        period_defs = PeriodDefinition.objects.filter(semester=semester).order_by('period_number')
        period_map = {} # period_number -> PeriodDefinition (first one found to get times)
        max_p = 0
        for p in period_defs:
            if p.period_number not in period_map:
                period_map[p.period_number] = p
            if p.period_number > max_p:
                max_p = p.period_number
        
        period_numbers = sorted(list(period_map.keys()))
        
        # ── Setup Styles ──────────────────────────────────────────────────
        styles = getSampleStyleSheet()
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Normal'],
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Normal'],
            fontSize=12,
            leading=14,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=5
        )
        sub_title_style = ParagraphStyle(
            'SubTitleStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        meta_style = ParagraphStyle(
            'MetaStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        meta_style_right = ParagraphStyle(
            'MetaStyleRight',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            alignment=TA_RIGHT,
            fontName='Helvetica-Bold'
        )
        grid_cell_style = ParagraphStyle(
            'GridCell',
            parent=styles['Normal'],
            fontSize=8,
            leading=9,
            alignment=TA_CENTER,
        )

        # ── Build Grid Table ───────────────────────────────────────────────
        # Header Row 1: Period/Day | P1 | P2 | P3 | Lunch | P4 | P5 ...
        # Header Row 2:            | Time | Time | Time | Time  | Time | Time ...
        
        col_headers1 = ['Period/ Day']
        col_headers2 = ['']
        
        lunch_pos = 0
        # For simplicity, detect lunch after P3 or based on time gap
        # Most common: Lunch after P3
        for p_num in period_numbers:
            p_def = period_map[p_num]
            col_headers1.append(str(p_num))
            col_headers2.append(f"{p_def.start_time.strftime('%H.%M')} to {p_def.end_time.strftime('%H.%M')}")
            
            # Insert lunch break after P3 (common in sample) or if gap > 20 mins
            if p_num == 3:
                col_headers1.append('Lunch Break')
                # Derive lunch time dynamically from period gap
                if 4 in period_map:
                    p3_end = p_def.end_time.strftime('%H.%M')
                    p4_start = period_map[4].start_time.strftime('%H.%M')
                    lunch_time_display = f"{p3_end} - {p4_start}"
                else:
                    lunch_time_display = '12.00 - 12.30'
                col_headers2.append(lunch_time_display)
                lunch_pos = len(col_headers1) - 1

        table_data = [col_headers1, col_headers2]
        
        for day in days_present:
            row = [day]
            for i, p_num in enumerate(period_numbers):
                # Handle Lunch break column insertion
                if i + 1 == 4 and lunch_pos:
                    row.append('') # Lunch break is usually a span, handled in TableStyle
                
                entry = grid.get(day, {}).get(p_num)
                if entry:
                    subj_code = entry.subject.code
                    fac_initials = ""
                    if entry.faculty:
                        # Try to get initials from name
                        parts = entry.faculty.get_full_name().split()
                        fac_initials = "".join([p[0].upper() for p in parts if p])
                    
                    cell_text = f"{subj_code}-{fac_initials}" if fac_initials else subj_code
                    row.append(cell_text)
                else:
                    row.append('')
            table_data.append(row)

        # ── Subject/Faculty Mapping Table ──────────────────────────────────
        mapping_data = [['Subject Code', 'Subject Name', 'Faculty Name']]
        seen_subj_faculty = set()
        
        # Collect all unique subject-faculty pairs from the grid
        for day_data in grid.values():
            for entry in day_data.values():
                key = (entry.subject.code, entry.faculty.id if entry.faculty else None)
                if key not in seen_subj_faculty:
                    seen_subj_faculty.add(key)
                    mapping_data.append([
                        entry.subject.code,
                        entry.subject.name,
                        entry.faculty.get_full_name() if entry.faculty else 'TBA'
                    ])

        # ── PDF Assembly ───────────────────────────────────────────────────
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=1*cm, rightMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm
        )
        
        elements = []
        
        # Header Section
        elements.append(Paragraph(university_name, header_style))
        elements.append(Paragraph(school_name, header_style))
        elements.append(Paragraph(dept_name, header_style))
        elements.append(Paragraph('CLASS TIME TABLE', title_style))
        elements.append(Paragraph(f"{semester.academic_year.year_code} ({str(semester.get_number_display()).upper()})", sub_title_style))
        elements.append(Paragraph(f"CLASS & SECTION: {str(section.name).upper()}", sub_title_style))
        elements.append(Spacer(1, 0.3*cm))
        
        # Meta Info (In-Charge, Room)
        meta_table = Table([
            [Paragraph(f"Class In-Charge Name: {in_charge_name}", meta_style), 
             Paragraph(f"Room No: {room_display}", meta_style_right)]
        ], colWidths=[15*cm, 10*cm])
        meta_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM')]))
        elements.append(meta_table)
        elements.append(Spacer(1, 0.2*cm))
        
        # Grid Table
        usable_width = 25*cm
        day_col_width = 3*cm
        lunch_col_width = 2*cm
        other_cols_count = len(period_numbers)
        remaining_width = usable_width - day_col_width - (lunch_col_width if lunch_pos else 0)
        p_col_width = remaining_width / max(other_cols_count, 1)
        
        col_widths = [day_col_width]
        current_idx = 1
        for p_num in period_numbers:
            col_widths.append(p_col_width)
            if p_num == 3 and lunch_pos:
                col_widths.append(lunch_col_width)
        
        grid_table = Table(table_data, colWidths=col_widths)
        grid_style = [
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('FONTNAME', (0,0), (-1,1), 'Helvetica-Bold'), # Headers
            ('FONTNAME', (0,2), (0,-1), 'Helvetica-Bold'), # Day names
        ]
        
        # Handle Lunch Break vertical span
        if lunch_pos:
            grid_style.append(('SPAN', (lunch_pos, 2), (lunch_pos, -1)))
        
        grid_table.setStyle(TableStyle(grid_style))
        elements.append(grid_table)
        elements.append(Spacer(1, 0.5*cm))
        
        # Mapping Table
        mapping_table = Table(mapping_data, colWidths=[4*cm, 8*cm, 8*cm], hAlign='LEFT')
        mapping_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(mapping_table)
        elements.append(Spacer(1, 0.5*cm))
        
        # Signatures
        sig_table = Table([
            [Paragraph('SIGNATURE OF THE FACULTY', meta_style), 
             Paragraph('SIGNATURE OF THE HOD', meta_style_right)]
        ], colWidths=[12.5*cm, 12.5*cm])
        sig_table.setStyle(TableStyle([('TOPPADDING', (0,0), (-1,-1), 20)]))
        elements.append(sig_table)
        
        doc.build(elements)
        return buffer.getvalue()



# ===========================================================================
# Item 8 — Timetable Violation Notifier
# ===========================================================================

class TimetableViolationNotifier:
    """
    Pushes timetable violation strings to all HOD and ADMIN users via the
    existing notifications app.

    Does NOT build any new notification infrastructure — uses
    notifications.services.notification_service.bulk_create_notifications()
    directly.
    """

    @staticmethod
    def notify(violations: list, semester_id: int) -> int:
        """
        Send one system notification per violation to every HOD / ADMIN user.

        Parameters
        ----------
        violations  : list of violation strings returned by the scheduler
        semester_id : used to enrich the notification metadata

        Returns
        -------
        Total number of Notification rows created.
        """
        if not violations:
            return 0

        try:
            from notifications.services.notification_service import bulk_create_notifications
            from notifications.constants import NotificationType, NotificationPriority
            from core.models import User
            from django.utils import timezone as tz
            from django.db import connection as db_connection

            # Tenant-branded notification title
            tenant = db_connection.tenant
            notification_title = f"Timetable Violation - {tenant.short_name}"

            # Fetch all active HOD and ADMIN users
            recipients = list(
                User.objects.filter(
                    role__code__in=['HOD', 'ADMIN'],
                    is_active=True,
                ).distinct()
            )
            if not recipients:
                logger.warning(
                    "TimetableViolationNotifier: no HOD/ADMIN users found; "
                    "violations not delivered."
                )
                return 0

            total_created = 0
            timestamp_str = tz.now().strftime('%Y-%m-%d %H:%M UTC')

            for violation in violations:
                created = bulk_create_notifications(
                    recipients=recipients,
                    notification_type=NotificationType.SYSTEM_ALERT,
                    title=notification_title,
                    message=(
                        f"[Semester {semester_id}] {violation}\n"
                        f"Detected at: {timestamp_str}"
                    ),
                    action_url="/timetable/",
                    metadata={
                        'semester_id': semester_id,
                        'violation_text': violation,
                        'detected_at': timestamp_str,
                    },
                    priority=NotificationPriority.URGENT,
                )
                total_created += len(created)

            return total_created

        except Exception as exc:
            logger.error(
                "TimetableViolationNotifier.notify() failed: %s", exc, exc_info=True
            )
            # Do not re-raise — violation delivery failure must not crash the caller
            return 0
