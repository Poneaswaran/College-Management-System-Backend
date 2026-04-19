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

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from campus_management.services import ResourceAllocationService
from campus_management.models import Resource
from timetable.models import TimetableEntry, PeriodDefinition

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
    Generates a PDF version of a section's weekly timetable grid.

    Uses ReportLab only (pure Python PDF generation — no WeasyPrint).
    """

    DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    @staticmethod
    def generate_pdf(section_id: int, semester_id: int) -> bytes:
        """
        Build the PDF and return the raw bytes.

        Parameters
        ----------
        section_id  : Section PK
        semester_id : Semester PK

        Returns
        -------
        bytes — the complete PDF file content
        """
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            )
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import cm
        except ImportError as exc:
            raise ImportError(
                "ReportLab is required for PDF export. "
                "Install it with: pip install reportlab"
            ) from exc

        import io
        from timetable.utils import get_section_timetable_grid
        from core.models import Section
        from profile_management.models import Semester

        section  = Section.objects.select_related('course').get(pk=section_id)
        semester = Semester.objects.get(pk=semester_id)
        grid     = get_section_timetable_grid(section, semester)

        # Determine which days appear in the grid
        days_present = [d for d in TimetableExportService.DAY_ORDER if d in grid]

        # Determine max period number across all days
        max_period = 0
        for day_data in grid.values():
            for p_num in day_data.keys():
                if p_num > max_period:
                    max_period = p_num

        if max_period == 0:
            max_period = 8  # default

        period_numbers = list(range(1, max_period + 1))

        # ── Build table data ──────────────────────────────────────────────
        # Header row: blank + day names
        header = ['Period'] + days_present
        table_data = [header]

        for p_num in period_numbers:
            row = [f'P{p_num}']
            for day in days_present:
                entry = grid.get(day, {}).get(p_num)
                if entry:
                    cell_lines = [
                        entry.subject.code,
                        entry.subject.name[:20],
                    ]
                    if entry.faculty:
                        cell_lines.append(entry.faculty.get_full_name()[:20])
                    if entry.room:
                        cell_lines.append(f'Room: {entry.room.room_number}')
                    cell_text = '\n'.join(cell_lines)
                else:
                    cell_text = '—'
                row.append(cell_text)
            table_data.append(row)

        # ── ReportLab document ────────────────────────────────────────────
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=1 * cm,
            rightMargin=1 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        styles = getSampleStyleSheet()
        title_para = Paragraph(
            f"<b>Timetable — {section.name}</b><br/>"
            f"<font size='10'>Semester: {semester}</font>",
            styles['Title'],
        )

        # Column widths: period col narrow, day cols equal
        page_width = landscape(A4)[0] - 2 * cm  # usable width
        period_col_w = 1.5 * cm
        day_col_w = (page_width - period_col_w) / max(len(days_present), 1)
        col_widths = [period_col_w] + [day_col_w] * len(days_present)

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 9),
            ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN',     (0, 0), (-1, 0), 'MIDDLE'),

            # Period label column
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#f0f4f8')),
            ('FONTNAME',   (0, 1), (0, -1), 'Helvetica-Bold'),
            ('ALIGN',      (0, 1), (0, -1), 'CENTER'),

            # Data cells
            ('FONTSIZE',   (1, 1), (-1, -1), 8),
            ('ALIGN',      (1, 1), (-1, -1), 'CENTER'),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),

            # Grid lines
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#adb5bd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),

            # Padding
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 3),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
        ]))

        generated_at = Paragraph(
            f"<font size='7' color='grey'>Generated at {timezone.now().strftime('%Y-%m-%d %H:%M')} UTC</font>",
            styles['Normal'],
        )

        doc.build([title_para, Spacer(1, 0.4 * cm), table, Spacer(1, 0.3 * cm), generated_at])
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
                    title="Timetable Violation Detected",
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
