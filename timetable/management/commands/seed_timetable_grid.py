import datetime
from django.core.management.base import BaseCommand
from django.db import connection
from tenants.models import Client
from core.models import Department
from timetable.models import TimetableGrid, PeriodSlot, Period

class Command(BaseCommand):
    help = 'Seed timetable grid for all departments with 8 periods from 9:30 AM to 3:00 PM'

    def handle(self, *args, **options):
        # We assume the tenant is 'vels' based on previous context
        try:
            tenant = Client.objects.get(schema_name='vels')
            connection.set_tenant(tenant)
        except Client.DoesNotExist:
            self.stdout.write(self.style.ERROR("Tenant 'vels' not found. Please ensure the tenant exists."))
            return

        self.stdout.write(f"Seeding timetable grid for tenant: {tenant.schema_name}")

        # Period times (35 min periods, 50 min lunch)
        # P1: 09:30 - 10:05
        # P2: 10:05 - 10:40
        # P3: 10:40 - 11:15
        # P4: 11:15 - 11:50
        # Lunch: 11:50 - 12:40
        # P5: 12:40 - 13:15
        # P6: 13:15 - 13:50
        # P7: 13:50 - 14:25
        # P8: 14:25 - 15:00

        slots_data = [
            {"num": 1, "label": "Period 1", "start": "09:30", "end": "10:05", "type": "class"},
            {"num": 2, "label": "Period 2", "start": "10:05", "end": "10:40", "type": "class"},
            {"num": 3, "label": "Period 3", "start": "10:40", "end": "11:15", "type": "class"},
            {"num": 4, "label": "Period 4", "start": "11:15", "end": "11:50", "type": "class"},
            {"num": None, "label": "Lunch Break", "start": "11:50", "end": "12:40", "type": "lunch"},
            {"num": 5, "label": "Period 5", "start": "12:40", "end": "13:15", "type": "class"},
            {"num": 6, "label": "Period 6", "start": "13:15", "end": "13:50", "type": "class"},
            {"num": 7, "label": "Period 7", "start": "13:50", "end": "14:25", "type": "class"},
            {"num": 8, "label": "Period 8", "start": "14:25", "end": "15:00", "type": "class"},
        ]

        # 1. Seed global Periods (for HOD assignment)
        for i, data in enumerate(slots_data):
            Period.objects.update_or_create(
                order=i + 1,
                defaults={
                    "label": data["label"],
                    "start_time": data["start"],
                    "end_time": data["end"],
                    "is_break": data["type"] != "class",
                }
            )
        self.stdout.write(self.style.SUCCESS("Seeded global Periods."))

        # 2. Seed PeriodDefinitions (for TimetableEntry)
        from profile_management.models import Semester
        from timetable.models import PeriodDefinition
        
        current_semester = Semester.objects.filter(is_current=True).first()
        if current_semester:
            self.stdout.write(f"Seeding PeriodDefinitions for semester: {current_semester}")
            # Days 1-6 (Monday to Saturday)
            for day in range(1, 7):
                for data in slots_data:
                    if data["num"] is not None:
                        # Calculate duration
                        start = datetime.datetime.strptime(data["start"], "%H:%M")
                        end = datetime.datetime.strptime(data["end"], "%H:%M")
                        duration = int((end - start).total_seconds() / 60)
                        
                        PeriodDefinition.objects.update_or_create(
                            semester=current_semester,
                            period_number=data["num"],
                            day_of_week=day,
                            defaults={
                                "start_time": data["start"],
                                "end_time": data["end"],
                                "duration_minutes": duration,
                            }
                        )
            self.stdout.write(self.style.SUCCESS("Seeded PeriodDefinitions."))
        else:
            self.stdout.write(self.style.WARNING("No current semester found. Skipping PeriodDefinitions."))

        # 3. Seed TimetableGrid and PeriodSlot for each department
        departments = Department.objects.all()
        academic_year = "2025-26"
        effective_from = datetime.date(2025, 6, 1)

        for dept in departments:
            # Create or update grid
            grid, created = TimetableGrid.objects.update_or_create(
                department=dept,
                academic_year=academic_year,
                defaults={
                    "effective_from": effective_from,
                    "is_active": True,
                }
            )
            
            # Create slots for this grid
            PeriodSlot.objects.filter(grid=grid).delete()
            
            for i, data in enumerate(slots_data):
                PeriodSlot.objects.create(
                    grid=grid,
                    slot_number=i + 1,
                    slot_type=data["type"],
                    start_time=data["start"],
                    end_time=data["end"],
                    label=data["label"],
                )
            
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} grid for department: {dept.name}")

        self.stdout.write(self.style.SUCCESS("Successfully seeded all timetable grids."))
