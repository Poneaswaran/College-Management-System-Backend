"""
Management command: generate_timetable

Wraps the full scheduling pipeline from Item 3 so it can be run from
the terminal:

    python manage.py generate_timetable --semester_id <int> [--department-id <int>]

Pipeline order:
  1. LabRotationGenerator.generate()
  2. SubjectDistributionService.distribute() + commit_distribution()
     for every active Section
  3. RoomAllocatorService.allocate_period() for every PeriodDefinition
     in the semester
  4. TimetableViolationNotifier.notify() if any violations were found

Also supports dry-run mode (--dry-run) to preview step 3 without
committing any room allocations.
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError


class Command(BaseCommand):
    help = (
        "Run the full timetable generation pipeline for a semester: "
        "lab rotation → subject distribution → room allocation."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--semester_id',
            type=int,
            required=True,
            dest='semester_id',
            metavar='SEMESTER_ID',
            help='ID of the Semester to generate the timetable for',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help=(
                'Preview room allocation without saving. '
                'Lab rotation and subject distribution are still shown but '
                'NOT committed when this flag is set.'
            ),
        )
        parser.add_argument(
            '--skip-distribution',
            action='store_true',
            dest='skip_distribution',
            help='Skip subject distribution (step 2) — useful if entries already exist.',
        )
        parser.add_argument(
            '--department-id',
            type=int,
            dest='department_id',
            default=None,
            metavar='DEPARTMENT_ID',
            help=(
                'Optional. Restrict subject distribution (step 2) to sections '
                'belonging to this Department ID. Avoids flooding violations '
                'with "no requirements" errors from other departments.'
            ),
        )

    # -----------------------------------------------------------------------

    def handle(self, *args, **options):
        semester_id       = options['semester_id']
        dry_run           = options['dry_run']
        skip_distribution = options['skip_distribution']
        department_id     = options.get('department_id')

        from timetable.scheduler import LabRotationGenerator, RoomAllocatorService
        from timetable.services import (
            SubjectDistributionService,
            TimetableViolationNotifier,
        )
        from timetable.models import PeriodDefinition
        from core.models import Section

        dept_label = f" | Dept {department_id}" if department_id else ""
        self.stdout.write(
            self.style.NOTICE(
                f"\n{'='*65}\n"
                f"  Timetable Generation — Semester {semester_id}{dept_label}"
                + (" [DRY RUN]" if dry_run else "")
                + f"\n{'='*65}\n"
            )
        )

        all_violations: list[str] = []
        total_entries  = 0
        total_overflow = 0

        # == Step 1: Lab Rotation ===========================================
        self.stdout.write(self.style.NOTICE("Step 1: Generating lab rotation…"))
        try:
            if not dry_run:
                rotation_result = LabRotationGenerator.generate(semester_id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅  {rotation_result['created']} lab rotation(s) created "
                        f"({rotation_result['non_room_created']} NonRoomPeriods). "
                        f"Previous: {rotation_result['deleted_previous']} deleted."
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("  [dry-run] Skipping lab rotation commit."))
        except ValidationError as exc:
            raise CommandError(f"Lab rotation failed: {exc}")

        # == Step 2: Subject Distribution ===================================
        if not skip_distribution and not dry_run:
            self.stdout.write(self.style.NOTICE("\nStep 2: Distributing subjects for all sections…"))
            section_qs = Section.objects.select_related('course__department')
            if department_id:
                section_qs = section_qs.filter(course__department_id=department_id)
            sections = list(section_qs)
            for section in sections:
                try:
                    planned = SubjectDistributionService.distribute(
                        section_id=section.pk,
                        semester_id=semester_id,
                    )
                    saved = SubjectDistributionService.commit_distribution(planned)
                    total_entries += len(saved)
                    self.stdout.write(
                        f"   {section.name:<40} → {len(saved)} entries created"
                    )
                except ValidationError as exc:
                    msg = f"Section '{section.name}' distribution error: {exc}"
                    all_violations.append(msg)
                    self.stdout.write(self.style.ERROR(f"   ⚠  {msg}"))
        else:
            reason = "[dry-run] " if dry_run else "[--skip-distribution] "
            self.stdout.write(self.style.WARNING(f"\nStep 2: {reason}Skipping subject distribution."))

        # == Step 3: Room Allocation for every period =======================
        self.stdout.write(self.style.NOTICE("\nStep 3: Allocating rooms per period…"))
        periods = list(
            PeriodDefinition.objects.filter(semester_id=semester_id)
            .order_by('day_of_week', 'period_number')
        )

        if not periods:
            self.stdout.write(
                self.style.WARNING(
                    "  No PeriodDefinitions found for this semester. "
                    "Run generate-periods first."
                )
            )
        else:
            today = date.today()
            for period in periods:
                result = RoomAllocatorService.allocate_period(
                    semester_id=semester_id,
                    period_definition_id=period.pk,
                    overflow_date=today,
                    dry_run=dry_run,
                )
                all_violations.extend(result['violations'])
                period_overflow = len(result['overflow'])
                total_overflow  += period_overflow

                status_icon = "⚠ " if period_overflow else "✅"
                self.stdout.write(
                    f"   {status_icon} {period}: "
                    f"{len(result['assigned'])} assigned, "
                    f"{period_overflow} overflow"
                )
                for v in result['violations']:
                    self.stdout.write(self.style.ERROR(f"      🚨 {v}"))

        # == Step 4: Violation notifications ================================
        if all_violations and not dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f"\nStep 4: Pushing {len(all_violations)} violation notification(s)…"
                )
            )
            sent = TimetableViolationNotifier.notify(all_violations, semester_id)
            self.stdout.write(self.style.SUCCESS(f"  {sent} notification(s) dispatched."))

        # == Summary ========================================================
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*65}\n"
                f"  Summary for Semester {semester_id}\n"
                f"{'='*65}\n"
                f"  Entries created   : {total_entries}\n"
                f"  Total overflow    : {total_overflow}\n"
                f"  Total violations  : {len(all_violations)}\n"
                + ("  [DRY RUN — no DB changes committed for room allocation]\n" if dry_run else "")
                + f"{'='*65}\n"
            )
        )
