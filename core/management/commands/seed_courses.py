from django.core.management.base import BaseCommand
from django.db import connection
from tenants.models import Client
from core.models import Department, Course

class Command(BaseCommand):
    help = 'Seed courses for all departments'

    def handle(self, *args, **options):
        try:
            tenant = Client.objects.get(schema_name='vels')
            connection.set_tenant(tenant)
        except Client.DoesNotExist:
            self.stdout.write(self.style.ERROR("Tenant 'vels' not found."))
            return

        courses_data = {
            'CSE': [
                {'name': 'B.E. Computer Science and Engineering', 'code': 'BE-CSE', 'duration': 4},
                {'name': 'M.E. Computer Science and Engineering', 'code': 'ME-CSE', 'duration': 2},
                {'name': 'B.Tech Artificial Intelligence and Data Science', 'code': 'BT-AIDS', 'duration': 4},
            ],
            'ECE': [
                {'name': 'B.E. Electronics and Communication Engineering', 'code': 'BE-ECE', 'duration': 4},
                {'name': 'M.E. VLSI Design', 'code': 'ME-VLSI', 'duration': 2},
            ],
            'MECH': [
                {'name': 'B.E. Mechanical Engineering', 'code': 'BE-MECH', 'duration': 4},
                {'name': 'M.E. Thermal Engineering', 'code': 'ME-THERM', 'duration': 2},
            ],
            'IT': [
                {'name': 'B.Tech Information Technology', 'code': 'BT-IT', 'duration': 4},
            ],
            'CIVIL': [
                {'name': 'B.E. Civil Engineering', 'code': 'BE-CIVIL', 'duration': 4},
                {'name': 'M.E. Structural Engineering', 'code': 'ME-STRUCT', 'duration': 2},
            ]
        }

        for dept_code, courses in courses_data.items():
            try:
                dept = Department.objects.get(code=dept_code)
                for c_data in courses:
                    course, created = Course.objects.update_or_create(
                        department=dept,
                        code=c_data['code'],
                        defaults={
                            'name': c_data['name'],
                            'duration_years': c_data['duration']
                        }
                    )
                    status = "Created" if created else "Updated"
                    self.stdout.write(f"{status} course: {course.name} ({course.code}) for {dept.code}")
            except Department.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Department with code {dept_code} not found. Skipping."))

        self.stdout.write(self.style.SUCCESS("Successfully seeded courses."))
