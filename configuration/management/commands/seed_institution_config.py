"""
configuration/management/commands/seed_institution_config.py

Seeds the Configuration table with institution-specific keys for each
active department, enabling tenant-scoped PDF export and branding.

Usage:
    python manage.py seed_institution_config
    python manage.py seed_institution_config --university "My University" --school "My School"
    python manage.py seed_institution_config --department CSE --university "Custom University"
"""

from django.core.management.base import BaseCommand

from configuration.models import Configuration
from core.models import Department


# Default institution values - change these to match your institution
DEFAULT_UNIVERSITY = "VELS INSTITUTE OF SCIENCE, TECHNOLOGY & ADVANCED STUDIES (VISTAS)"
DEFAULT_SCHOOL = "SCHOOL OF MANAGEMENT STUDIES AND COMMERCE"

# Additional PDF defaults
DEFAULT_PDF_TITLE = "CLASS TIME TABLE"
DEFAULT_LUNCH_TIME = "12.00 - 12.30"
DEFAULT_SIG_FACULTY = "SIGNATURE OF THE FACULTY"
DEFAULT_SIG_HOD = "SIGNATURE OF THE HOD"

SEED_KEYS = [
    ("university_name", DEFAULT_UNIVERSITY, "Institution / University name shown in PDF header"),
    ("school_name", DEFAULT_SCHOOL, "School or faculty name shown in PDF header"),
    ("pdf_title", DEFAULT_PDF_TITLE, "Title text on the timetable PDF"),
    ("pdf_lunch_time", DEFAULT_LUNCH_TIME, "Lunch break time range displayed in timetable grid"),
    ("pdf_sig_faculty", DEFAULT_SIG_FACULTY, "Faculty signature label in PDF footer"),
    ("pdf_sig_hod", DEFAULT_SIG_HOD, "HOD signature label in PDF footer"),
]


class Command(BaseCommand):
    help = (
        "Seed institution configuration rows for each department. "
        "Creates global defaults and per-department (tenant-scoped) config entries "
        "so the PDF export can resolve institution branding."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--university",
            type=str,
            default=DEFAULT_UNIVERSITY,
            help="University name to seed as the global default.",
        )
        parser.add_argument(
            "--school",
            type=str,
            default=DEFAULT_SCHOOL,
            help="School name to seed as the global default.",
        )
        parser.add_argument(
            "--department",
            type=str,
            default=None,
            help="If provided, only seed config for this department code (e.g., CSE).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing config values.",
        )

    def handle(self, *args, **options):
        university = options["university"]
        school = options["school"]
        dept_filter = options["department"]
        force = options["force"]

        # Build the seed data with CLI overrides for university/school
        seed_data = list(SEED_KEYS)
        seed_data[0] = ("university_name", university, seed_data[0][2])
        seed_data[1] = ("school_name", school, seed_data[1][2])

        # -- Step 1: Seed global defaults (tenant_key=NULL) --
        self.stdout.write(self.style.MIGRATE_HEADING("\n-- Global Defaults --"))
        global_created = 0
        for key, value, description in seed_data:
            _, created = Configuration.objects.update_or_create(
                tenant_key=None,
                sub_app="global",
                key=key,
                defaults={
                    "value": value,
                    "description": description,
                    "is_active": True,
                } if force else {},
            ) if force else (
                Configuration.objects.get_or_create(
                    tenant_key=None,
                    sub_app="global",
                    key=key,
                    defaults={
                        "value": value,
                        "description": description,
                        "is_active": True,
                    },
                )
            )
            if created:
                global_created += 1
                self.stdout.write(f"  + Created global:{key} = {repr(value)[:60]}")
            else:
                action = "Updated" if force else "Exists"
                self.stdout.write(f"  ~ {action}  global:{key}")

        # -- Step 2: Seed per-department config --
        departments = Department.objects.filter(is_active=True)
        if dept_filter:
            departments = departments.filter(code=dept_filter.upper())

        if not departments.exists():
            self.stdout.write(self.style.WARNING(
                f"No active departments found"
                + (f" with code '{dept_filter}'" if dept_filter else "")
                + "."
            ))
            return

        dept_created = 0
        for dept in departments:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n-- Department: {dept.code} ({dept.name}) --"))
            for key, value, description in seed_data:
                if force:
                    _, created = Configuration.objects.update_or_create(
                        tenant_key=dept.code,
                        sub_app="global",
                        key=key,
                        defaults={
                            "value": value,
                            "description": f"[{dept.code}] {description}",
                            "is_active": True,
                        },
                    )
                else:
                    _, created = Configuration.objects.get_or_create(
                        tenant_key=dept.code,
                        sub_app="global",
                        key=key,
                        defaults={
                            "value": value,
                            "description": f"[{dept.code}] {description}",
                            "is_active": True,
                        },
                    )
                if created:
                    dept_created += 1
                    self.stdout.write(f"  + Created {dept.code}:{key}")
                else:
                    action = "Updated" if force else "Exists"
                    self.stdout.write(f"  ~ {action}  {dept.code}:{key}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Created {global_created} global + {dept_created} dept-scoped config rows."
        ))
        self.stdout.write(self.style.NOTICE(
            "Tip: Customize per-department values in Django Admin > Configuration."
        ))
