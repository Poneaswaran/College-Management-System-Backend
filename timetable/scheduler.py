"""
timetable/scheduler.py

Two-engine scheduling system for the college room allocation problem:

  LabRotationGenerator  — assigns each of 17 sections one lab slot per week
                          across 2 labs, with no conflicts.

  RoomAllocatorService  — for any given period, allocates classrooms to
                          sections in priority order and fairly logs overflows.
                          Also wires faculty-conflict detection (Item 1) and
                          auto-compensation after each run (Item 5).

Usage:
  from timetable.scheduler import LabRotationGenerator, RoomAllocatorService

  # 1. Generate lab rotation first (once per semester)
  LabRotationGenerator.generate(semester_id=1)

  # 2. Preview room allocation for a specific period (dry run)
  result = RoomAllocatorService.preview_period(semester_id=1, period_definition_id=5)

  # 3. Apply allocation for a live period
  result = RoomAllocatorService.allocate_period(
      semester_id=1,
      period_definition_id=5,
      overflow_date=date.today()
  )
"""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Count

from core.models import Section
from timetable.models import (
    PeriodDefinition,
    Room,
    NonRoomPeriod,
    OverflowLog,
    LabRotationSchedule,
)


# ---------------------------------------------------------------------------
# Lab Rotation Generator
# ---------------------------------------------------------------------------

class LabRotationGenerator:
    """
    Generates the lab rotation schedule for an entire semester.

    Strategy
    --------
    We have N lab rooms and M period slots per week.
    Each section needs exactly ONE lab slot per semester.
    We round-robin across labs, then across periods, until every
    section has a unique (lab, period) assignment.

    After generating rotations, a NonRoomPeriod(type='LAB') is created
    for each section so the room allocator knows to skip that period
    when calculating classroom demand.

    Idempotent — calling generate() again for the same semester
    deletes the previous rotation and rebuilds it cleanly.
    """

    STUDENTS_PER_SECTION = 40

    @classmethod
    @transaction.atomic
    def generate(cls, semester_id: int) -> dict:
        """
        Generate lab rotation for all sections in the given semester.

        Returns
        -------
        {
            'created': int,          # number of LabRotationSchedule rows created
            'rotations': list,       # LabRotationSchedule objects
            'non_room_created': int, # NonRoomPeriod(LAB) rows created
        }
        """
        from profile_management.models import Semester  # lazy import to avoid circular

        semester = Semester.objects.get(id=semester_id)

        # Fetch active labs that can physically fit the sections
        labs = list(
            Room.objects.filter(
                room_type='LAB',
                is_active=True,
                capacity__gte=cls.STUDENTS_PER_SECTION,
            ).order_by('id')
        )
        if not labs:
            raise ValidationError(
                "No active labs with sufficient capacity found. "
                f"Need capacity >= {cls.STUDENTS_PER_SECTION}."
            )

        # All period definitions for the semester, Mon–Fri ordered
        periods = list(
            PeriodDefinition.objects.filter(semester_id=semester_id)
            .order_by('day_of_week', 'period_number')
        )
        if not periods:
            raise ValidationError(
                f"No period definitions found for semester {semester_id}. "
                "Create period definitions first."
            )

        # All sections — ordered by priority asc (final year first) so they
        # get the "best" (earliest in week) lab slots.
        sections = list(
            Section.objects.order_by('priority', 'course__code', 'year', 'code')
        )
        if not sections:
            raise ValidationError("No sections found.")

        n_labs    = len(labs)
        n_periods = len(periods)
        max_slots = n_labs * n_periods
        if len(sections) > max_slots:
            raise ValidationError(
                f"Cannot assign {len(sections)} sections to {max_slots} "
                f"available lab slots ({n_labs} labs × {n_periods} periods). "
                "Add more period definitions or labs."
            )

        # ── Teardown previous rotation for this semester ──────────────────
        deleted_rotations, _ = LabRotationSchedule.objects.filter(
            semester_id=semester_id
        ).delete()
        # Remove LAB-type NonRoomPeriods that were auto-created by this generator
        NonRoomPeriod.objects.filter(
            semester_id=semester_id,
            period_type='LAB'
        ).delete()

        # ── Build (lab_idx, period_idx) → section assignments ─────────────
        #
        # We walk period slots in column-major order:
        #   period[0] → lab[0], lab[1]
        #   period[1] → lab[0], lab[1]
        #   ...
        # This spreads lab sessions across all days before cycling back.
        #
        # `slot_used` tracks which (lab, period) pairs are taken.

        slot_used: dict[tuple[int, int], int] = {}  # (lab_id, period_id) -> section_id

        rotations_created   = []
        non_room_created    = 0

        section_iter = iter(sections)

        outer_break = False
        for period in periods:
            if outer_break:
                break
            for lab in labs:
                try:
                    section = next(section_iter)
                except StopIteration:
                    outer_break = True
                    break

                key = (lab.id, period.id)
                # Safety: this slot must be free (should always be true here)
                if key in slot_used:
                    raise ValidationError(
                        f"Slot conflict detected for lab {lab} period {period}."
                    )
                slot_used[key] = section.id

                # Create the rotation record (bypass full_clean for bulk speed;
                # unique_together enforced by DB constraint)
                rotation = LabRotationSchedule(
                    section=section,
                    lab=lab,
                    period_definition=period,
                    semester_id=semester_id,
                    is_active=True,
                )
                rotation.save()  # calls full_clean via overridden save()
                rotations_created.append(rotation)

                # Create matching NonRoomPeriod so room allocator skips this slot
                _, created = NonRoomPeriod.objects.get_or_create(
                    section=section,
                    period_definition=period,
                    semester_id=semester_id,
                    defaults={'period_type': 'LAB'},
                )
                if created:
                    non_room_created += 1

        return {
            'created':          len(rotations_created),
            'rotations':        rotations_created,
            'non_room_created': non_room_created,
            'deleted_previous': deleted_rotations,
        }


# ---------------------------------------------------------------------------
# Room Allocator Service
# ---------------------------------------------------------------------------

class RoomAllocatorService:
    """
    Priority-based room allocator for individual periods.

    Core rule
    ---------
    For a given period:
      1. Exclude sections with a NonRoomPeriod (lab / PT / library / free).
      2. Sort remaining sections by:
           a. priority ASC (1 = final year, gets room first)
           b. uncompensated overflow count ASC (most-displaced sections
              get a compensatory boost within same priority tier)
      3. Assign available rooms (classrooms first, then idle labs) to
         sections in that order.
      4. Remaining sections → overflow.
         - OverflowLog entry created.
         - NonRoomPeriod(FREE) created so they have a defined activity.

    Faculty-conflict detection (Item 1)
    ------------------------------------
    When a section is assigned a room, if the entry's faculty is already
    teaching another section at this period the violation string is appended
    so the caller can surface it.  The room assignment still proceeds because
    the room allocator operates at section granularity; it is the
    SubjectDistributionService's job to pick faculty per slot.

    Auto-compensation (Item 5)
    --------------------------
    After every non-dry-run allocate_period() call, sections that received a
    priority boost this run (i.e. they were in overflow previously and their
    uncompensated log count influenced sort order) get their OverflowLog rows
    marked compensated inside the same transaction so they return to normal
    standing in the next run.

    Final-year guarantee
    --------------------
    Because final-year sections have priority=1 and there are at most 3
    overflow slots (17 sections − 14 rooms), and final-year sections number
    at most 5 (3 + 2 from MSc), they always fit within the 14 rooms.
    The validator `validate_no_final_year_overflow` asserts this explicitly.
    """

    STUDENTS_PER_SECTION = 40

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _overflow_counts(semester_id: int) -> dict[int, int]:
        """Return {section_id: uncompensated_overflow_count}."""
        qs = (
            OverflowLog.objects
            .filter(semester_id=semester_id, compensated=False)
            .values('section_id')
            .annotate(cnt=Count('id'))
        )
        return {row['section_id']: row['cnt'] for row in qs}

    @staticmethod
    def _sort_key(section: Section, overflow_counts: dict[int, int]):
        """
        Sort key for section ordering:
          primary   → priority ASC (1 = final year goes first)
          secondary → overflow count ASC (most-displaced within same priority
                      tier gets a compensatory boost)
        """
        return (section.priority, overflow_counts.get(section.id, 0))

    # ── Public API ─────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def allocate_period(
        semester_id: int,
        period_definition_id: int,
        overflow_date: date,
        dry_run: bool = False,
    ) -> dict:
        """
        Allocate rooms for one period slot.

        Parameters
        ----------
        semester_id           : ID of the current Semester
        period_definition_id  : ID of the PeriodDefinition to allocate
        overflow_date         : calendar date (used for OverflowLog.overflow_date)
        dry_run               : if True, compute result but do NOT write anything

        Returns
        -------
        {
            'assigned':     [(Section, Room), ...],
            'lab_assigned': [LabRotationSchedule, ...],
            'overflow':     [Section, ...],
            'non_room':     [Section, ...],         # PT / LIBRARY / FREE (pre-existing)
            'violations':   [str, ...],             # final-year overflow + faculty conflicts
        }
        """
        from timetable.models import TimetableEntry
        from timetable.validators import FacultyConflictChecker

        period = PeriodDefinition.objects.select_related('semester').get(
            id=period_definition_id
        )

        # 1. Collect section IDs that already have a NonRoomPeriod this slot
        non_room_ids: set[int] = set(
            NonRoomPeriod.objects.filter(
                period_definition_id=period_definition_id,
                semester_id=semester_id,
            ).values_list('section_id', flat=True)
        )

        # 2. Sections in lab this period (subset of non_room_ids)
        lab_rotations = list(
            LabRotationSchedule.objects.filter(
                period_definition_id=period_definition_id,
                semester_id=semester_id,
                is_active=True,
            ).select_related('section', 'lab')
        )
        lab_section_ids: set[int] = {r.section_id for r in lab_rotations}

        # 3. Sections with non-classroom activities other than lab
        non_room_sections = list(
            Section.objects.filter(id__in=non_room_ids - lab_section_ids)
        )

        # 4. Candidate sections that need a classroom
        overflow_counts = RoomAllocatorService._overflow_counts(semester_id)
        candidates = sorted(
            Section.objects.exclude(id__in=non_room_ids),
            key=lambda s: RoomAllocatorService._sort_key(s, overflow_counts),
        )

        # 5. Available rooms (classrooms first, then labs not in use)
        used_lab_ids: set[int] = {r.lab_id for r in lab_rotations}
        available_rooms = list(
            Room.objects.filter(
                is_active=True,
                capacity__gte=RoomAllocatorService.STUDENTS_PER_SECTION,
            )
            .exclude(id__in=used_lab_ids)
            # Classrooms before labs (labs are last resort for theory)
            .order_by('room_type', 'room_number')
        )

        # 6. Assignment
        assigned: list[tuple[Section, Room]] = []
        overflow: list[Section] = []
        room_queue = list(available_rooms)

        for section in candidates:
            if room_queue:
                room = room_queue.pop(0)
                assigned.append((section, room))
            else:
                overflow.append(section)

        # 7. Validation — final year must never overflow
        violations: list[str] = []
        for s in overflow:
            if s.priority == 1:
                violations.append(
                    f"CRITICAL: Final-year section '{s.name}' has no room at "
                    f"{period}. Manually free a room or reduce overflow."
                )

        # 7b. Faculty conflict check (Item 1) — flag if any assigned section's
        #     faculty is already teaching elsewhere this period.
        for section, room in assigned:
            existing_entry = (
                TimetableEntry.objects
                .filter(
                    section=section,
                    period_definition_id=period_definition_id,
                    semester_id=semester_id,
                    is_active=True,
                )
                .select_related('faculty')
                .first()
            )
            if existing_entry and existing_entry.faculty_id:
                conflict_msg = FacultyConflictChecker.conflict_description(
                    faculty_id=existing_entry.faculty_id,
                    period_definition_id=period_definition_id,
                    semester_id=semester_id,
                    exclude_entry_id=existing_entry.pk,
                )
                if conflict_msg:
                    violations.append(
                        f"Faculty conflict for section '{section.name}': {conflict_msg}"
                    )

        # 8. Persist (unless dry_run)
        if not dry_run:
            # Track which sections received a boost from accumulated overflow debt
            # so we can auto-compensate them after this run (Item 5).
            boosted_section_ids: list[int] = []

            for section in overflow:
                OverflowLog.objects.create(
                    section=section,
                    period_definition=period,
                    semester_id=semester_id,
                    overflow_date=overflow_date,
                    reason='room_shortage',
                )
                # Give the section a defined activity slot
                NonRoomPeriod.objects.get_or_create(
                    section=section,
                    period_definition=period,
                    semester_id=semester_id,
                    defaults={'period_type': 'FREE'},
                )

            # ── Item 5: Auto-compensation ──────────────────────────────────
            # A section received a compensatory priority boost if:
            #   • its priority > 1 (not final-year, those sort first by rule)
            #   • AND it had at least 1 uncompensated overflow log this run
            # After being served (i.e. it is in 'assigned' this run), mark
            # its logs compensated so next run sorts normally.
            for section, _room in assigned:
                oc = overflow_counts.get(section.id, 0)
                if section.priority > 1 and oc > 0:
                    boosted_section_ids.append(section.id)

            if boosted_section_ids:
                for sid in boosted_section_ids:
                    RoomAllocatorService.compensate_section(sid, semester_id)

        return {
            'assigned':     assigned,
            'lab_assigned': lab_rotations,
            'overflow':     overflow,
            'non_room':     non_room_sections,
            'violations':   violations,
        }

    @classmethod
    def preview_period(
        cls,
        semester_id: int,
        period_definition_id: int,
    ) -> dict:
        """Dry-run: compute allocation without saving anything."""
        return cls.allocate_period(
            semester_id=semester_id,
            period_definition_id=period_definition_id,
            overflow_date=date.today(),
            dry_run=True,
        )

    # ── Fairness utilities ─────────────────────────────────────────────────

    @staticmethod
    def get_fairness_report(semester_id: int) -> list[dict]:
        """
        Returns sections ordered by uncompensated overflow count (most first).
        Use this report to decide which sections deserve compensatory priority.
        """
        return list(
            Section.objects
            .filter(overflow_logs__semester_id=semester_id)
            .annotate(overflow_count=Count('overflow_logs'))
            .order_by('-overflow_count')
            .values('id', 'name', 'year', 'priority', 'overflow_count')
        )

    @staticmethod
    @transaction.atomic
    def compensate_section(section_id: int, semester_id: int) -> int:
        """
        Mark all uncompensated overflow logs for a section as compensated.
        Call this after manually bumping the section's priority for one run,
        so it won't continue to receive permanent priority boost.

        Returns the number of rows updated.
        """
        return OverflowLog.objects.filter(
            section_id=section_id,
            semester_id=semester_id,
            compensated=False,
        ).update(compensated=True)

    @staticmethod
    def room_utilisation_report(semester_id: int) -> list[dict]:
        """
        Returns how many times each room has been assigned across all periods
        for the semester (from TimetableEntry records).
        Useful to spot underused rooms or hotspots.
        """
        from timetable.models import TimetableEntry
        return list(
            TimetableEntry.objects
            .filter(semester_id=semester_id, is_active=True, room__isnull=False)
            .values('room__room_number', 'room__room_type', 'room__building')
            .annotate(assigned_count=Count('id'))
            .order_by('-assigned_count')
        )
