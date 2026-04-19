"""
Management command: generate_lab_rotation

Usage examples
--------------
Generate lab rotation for semester 1:
    python manage.py generate_lab_rotation 1

Preview room allocation for period 5 (no DB writes):
    python manage.py generate_lab_rotation 1 --preview-period 5

Show overflow fairness report:
    python manage.py generate_lab_rotation 1 --fairness-report

Show room utilisation report:
    python manage.py generate_lab_rotation 1 --utilisation-report

Compensate a section (reset its overflow debt):
    python manage.py generate_lab_rotation 1 --compensate-section 7
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from timetable.scheduler import LabRotationGenerator, RoomAllocatorService


class Command(BaseCommand):
    help = (
        "Generate lab rotation schedule for a semester, "
        "preview room allocation for a period, or view fairness reports."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'semester_id',
            type=int,
            help='ID of the Semester to operate on',
        )
        parser.add_argument(
            '--preview-period',
            type=int,
            dest='preview_period_id',
            metavar='PERIOD_ID',
            help='Dry-run room allocation for the given PeriodDefinition ID',
        )
        parser.add_argument(
            '--fairness-report',
            action='store_true',
            help='Print overflow fairness report (sections sorted by displacement count)',
        )
        parser.add_argument(
            '--utilisation-report',
            action='store_true',
            help='Print room utilisation report for the semester',
        )
        parser.add_argument(
            '--compensate-section',
            type=int,
            dest='compensate_section_id',
            metavar='SECTION_ID',
            help='Mark all overflow logs for this section as compensated',
        )

    # -----------------------------------------------------------------------

    def handle(self, *args, **options):
        semester_id = options['semester_id']

        # ── Preview period ──────────────────────────────────────────────────
        if options.get('preview_period_id'):
            self._preview_period(semester_id, options['preview_period_id'])
            return

        # ── Fairness report ─────────────────────────────────────────────────
        if options.get('fairness_report'):
            self._fairness_report(semester_id)
            return

        # ── Utilisation report ──────────────────────────────────────────────
        if options.get('utilisation_report'):
            self._utilisation_report(semester_id)
            return

        # ── Compensate section ──────────────────────────────────────────────
        if options.get('compensate_section_id'):
            self._compensate_section(semester_id, options['compensate_section_id'])
            return

        # ── Default: generate lab rotation ──────────────────────────────────
        self._generate_rotation(semester_id)

    # -----------------------------------------------------------------------
    # Sub-handlers
    # -----------------------------------------------------------------------

    def _generate_rotation(self, semester_id: int):
        self.stdout.write(
            self.style.NOTICE(
                f"Generating lab rotation for semester {semester_id}…"
            )
        )
        try:
            result = LabRotationGenerator.generate(semester_id)
        except ValidationError as e:
            raise CommandError(str(e))

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅  Lab rotation generated successfully.\n"
                f"    Rotations created  : {result['created']}\n"
                f"    NonRoomPeriods (LAB): {result['non_room_created']}\n"
                f"    Previous rows deleted: {result['deleted_previous']}"
            )
        )

        self.stdout.write("\nAssigned slots:")
        for rotation in result['rotations']:
            self.stdout.write(
                f"   {rotation.section.name:<35} → "
                f"{rotation.lab.room_number:<10} @ {rotation.period_definition}"
            )

    def _preview_period(self, semester_id: int, period_id: int):
        self.stdout.write(self.style.WARNING("=== DRY RUN — no changes will be saved ===\n"))
        result = RoomAllocatorService.preview_period(
            semester_id=semester_id,
            period_definition_id=period_id,
        )

        self.stdout.write(
            self.style.SUCCESS(f"✅  Rooms assigned ({len(result['assigned'])}):")
        )
        for section, room in result['assigned']:
            tag = f"[{room.room_type}]"
            self.stdout.write(f"   {section.name:<35} → {room.room_number:<10} {tag}")

        self.stdout.write(
            self.style.NOTICE(f"\n🔬  Lab sessions ({len(result['lab_assigned'])}):")
        )
        for rotation in result['lab_assigned']:
            self.stdout.write(
                f"   {rotation.section.name:<35} → {rotation.lab.room_number}"
            )

        self.stdout.write(
            self.style.NOTICE(f"\n📚  Non-room activities ({len(result['non_room'])}):")
        )
        for section in result['non_room']:
            self.stdout.write(f"   {section.name}")

        overflow_count = len(result['overflow'])
        style = self.style.ERROR if overflow_count else self.style.SUCCESS
        self.stdout.write(style(f"\n⚠️   Overflow sections ({overflow_count}):"))
        for section in result['overflow']:
            self.stdout.write(
                f"   {section.name:<35} (priority={section.priority})"
            )

        for violation in result['violations']:
            self.stdout.write(self.style.ERROR(f"\n🚨  {violation}"))

    def _fairness_report(self, semester_id: int):
        self.stdout.write(
            self.style.NOTICE(f"\n📊  Overflow Fairness Report — Semester {semester_id}\n")
        )
        report = RoomAllocatorService.get_fairness_report(semester_id)
        if not report:
            self.stdout.write("  No overflow events recorded yet.")
            return

        self.stdout.write(
            f"{'Section':<35} {'Year':<6} {'Priority':<10} {'Overflows'}"
        )
        self.stdout.write("-" * 65)
        for row in report:
            bar = "█" * row['overflow_count']
            self.stdout.write(
                f"{row['name']:<35} {row['year']:<6} {row['priority']:<10} "
                f"{row['overflow_count']:>3}  {bar}"
            )

    def _utilisation_report(self, semester_id: int):
        self.stdout.write(
            self.style.NOTICE(f"\n🏢  Room Utilisation Report — Semester {semester_id}\n")
        )
        report = RoomAllocatorService.room_utilisation_report(semester_id)
        if not report:
            self.stdout.write("  No timetable entries found.")
            return

        self.stdout.write(
            f"{'Room':<15} {'Type':<12} {'Building':<20} {'Periods Assigned'}"
        )
        self.stdout.write("-" * 65)
        for row in report:
            self.stdout.write(
                f"{row['room__room_number']:<15} "
                f"{row['room__room_type']:<12} "
                f"{row['room__building']:<20} "
                f"{row['assigned_count']:>3}"
            )

    def _compensate_section(self, semester_id: int, section_id: int):
        updated = RoomAllocatorService.compensate_section(section_id, semester_id)
        if updated:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅  Marked {updated} overflow log(s) as compensated "
                    f"for section {section_id}."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"No uncompensated overflow logs found for section {section_id} "
                    f"in semester {semester_id}."
                )
            )
