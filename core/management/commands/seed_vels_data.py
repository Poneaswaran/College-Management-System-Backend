
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context, tenant_context
from django.utils import timezone
from datetime import date, timedelta

from tenants.models import Client, Domain
from core.models import School, Department, Course, Section, Role, User
from profile_management.models import AcademicYear, Semester
from timetable.models import Subject

class Command(BaseCommand):
    help = "Seeds the 'vels' tenant with Indian standard academic data, roles, and an admin account."

    def handle(self, *args, **options):
        # 1. Create or Get the Vels Tenant (Public Schema Context)
        tenant_name = "VELS Institute of Science, Technology & Advanced Studies"
        tenant_short_name = "VELS"
        schema_name = "vels"
        domain_url = "vels.localhost"

        self.stdout.write(self.style.MIGRATE_HEADING(f"--- Initializing Tenant: {schema_name} ---"))

        tenant, created = Client.objects.get_or_create(
            schema_name=schema_name,
            defaults={
                'name': tenant_name,
                'short_name': tenant_short_name,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created tenant: {tenant_name}"))
        else:
            self.stdout.write(f"Tenant '{schema_name}' already exists.")

        domain, created = Domain.objects.get_or_create(
            domain=domain_url,
            tenant=tenant,
            defaults={'is_primary': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created domain: {domain_url}"))

        # 2. Seed Data within the Vels Tenant Context
        with tenant_context(tenant):
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n--- Seeding Data for {tenant_short_name} ---"))
            
            with transaction.atomic():
                # A. Roles
                self.stdout.write("Seeding Roles...")
                roles_data = [
                    ("System Administrator", "ADMIN", True),
                    ("Head of Department", "HOD", True),
                    ("Faculty", "FACULTY", True),
                    ("Student", "STUDENT", True),
                    ("Academic Scheduler", "ACADEMIC_SCHEDULER", True),
                ]
                for name, code, is_global in roles_data:
                    Role.objects.update_or_create(
                        code=code,
                        defaults={'name': name, 'is_global': is_global, 'is_active': True}
                    )

                # B. Academic Year & Semester
                self.stdout.write("Seeding Academic Year & Semesters...")
                ay_code = "2024-25"
                ay, _ = AcademicYear.objects.update_or_create(
                    year_code=ay_code,
                    defaults={
                        'start_date': date(2024, 6, 1),
                        'end_date': date(2025, 5, 31),
                        'is_current': True
                    }
                )

                sem1, _ = Semester.objects.update_or_create(
                    academic_year=ay,
                    number=1,
                    defaults={
                        'start_date': date(2024, 6, 1),
                        'end_date': date(2024, 11, 30),
                        'is_current': True
                    }
                )
                sem2, _ = Semester.objects.update_or_create(
                    academic_year=ay,
                    number=2,
                    defaults={
                        'start_date': date(2024, 12, 1),
                        'end_date': date(2025, 5, 31),
                        'is_current': False
                    }
                )

                # C. Schools
                self.stdout.write("Seeding Schools...")
                schools_data = [
                    ("School of Engineering", "SOE"),
                    ("School of Management", "SOM"),
                ]
                schools = {}
                for name, code in schools_data:
                    school, _ = School.objects.update_or_create(
                        code=code,
                        defaults={'name': name, 'is_active': True}
                    )
                    schools[code] = school

                # D. Departments
                self.stdout.write("Seeding Departments...")
                depts_data = [
                    ("Computer Science and Engineering", "CSE", "SOE"),
                    ("Electronics and Communication Engineering", "ECE", "SOE"),
                    ("Mechanical Engineering", "MECH", "SOE"),
                    ("Information Technology", "IT", "SOE"),
                    ("Civil Engineering", "CIVIL", "SOE"),
                    ("Business Administration", "MBA", "SOM"),
                ]
                depts = {}
                for name, code, school_code in depts_data:
                    dept, _ = Department.objects.update_or_create(
                        code=code,
                        defaults={
                            'name': name, 
                            'school': schools[school_code], 
                            'is_active': True
                        }
                    )
                    depts[code] = dept

                # E. Courses
                self.stdout.write("Seeding Courses...")
                courses_data = [
                    ("B.E. Computer Science", "BE-CSE", "CSE", 4),
                    ("B.Tech Information Technology", "BTECH-IT", "IT", 4),
                    ("B.E. Electronics", "BE-ECE", "ECE", 4),
                    ("MBA General", "MBA-GEN", "MBA", 2),
                ]
                courses = {}
                for name, code, dept_code, duration in courses_data:
                    course, _ = Course.objects.update_or_create(
                        code=code,
                        department=depts[dept_code],
                        defaults={'name': name, 'duration_years': duration}
                    )
                    courses[code] = course

                # F. Sections
                self.stdout.write("Seeding Sections...")
                for course_code, course in courses.items():
                    for year in range(1, course.duration_years + 1):
                        for sec_code in ['A', 'B']:
                            Section.objects.update_or_create(
                                course=course,
                                code=sec_code,
                                year=year,
                                defaults={
                                    'name': f"{course.name} Year {year} Section {sec_code}",
                                    'priority': 1 if year == course.duration_years else 2 if year > 1 else 3
                                }
                            )

                # G. Subjects (Indian Standard)
                self.stdout.write("Seeding Subjects...")
                subjects_data = [
                    # CSE Subjects
                    ("CS101", "Programming in C", "CSE", 1, 4.0, "THEORY"),
                    ("CS102", "Data Structures", "CSE", 3, 4.0, "THEORY"),
                    ("CS103", "Database Management Systems", "CSE", 5, 4.0, "THEORY"),
                    ("CS104", "Operating Systems", "CSE", 4, 4.0, "THEORY"),
                    ("CS105", "Artificial Intelligence", "CSE", 7, 3.0, "THEORY"),
                    ("CSL101", "Data Structures Lab", "CSE", 3, 2.0, "LAB"),
                    # ECE Subjects
                    ("EC101", "Digital Electronics", "ECE", 3, 4.0, "THEORY"),
                    ("EC102", "Microprocessors", "ECE", 5, 4.0, "THEORY"),
                    ("ECL101", "Digital Lab", "ECE", 3, 2.0, "LAB"),
                    # General
                    ("MA101", "Engineering Mathematics I", "CSE", 1, 4.0, "THEORY"),
                    ("PH101", "Engineering Physics", "CSE", 1, 3.0, "THEORY"),
                ]
                for code, name, dept_code, sem_num, credits, sub_type in subjects_data:
                    Subject.objects.update_or_create(
                        code=code,
                        defaults={
                            'name': name,
                            'department': depts[dept_code],
                            'semester_number': sem_num,
                            'credits': credits,
                            'subject_type': sub_type
                        }
                    )

                # H. Admin User
                self.stdout.write("Creating Admin User...")
                admin_role = Role.objects.get(code="ADMIN")
                admin_email = "admin@vels.edu"
                admin_password = "adminpassword123"
                
                user, created = User.objects.get_or_create(
                    email=admin_email,
                    defaults={
                        'role': admin_role,
                        'is_staff': True,
                        'is_superuser': True,
                        'is_active': True,
                    }
                )
                if created:
                    user.set_password(admin_password)
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"Created Admin: {admin_email} / {admin_password}"))
                else:
                    self.stdout.write(f"Admin '{admin_email}' already exists.")

        self.stdout.write(self.style.SUCCESS("\nDone! Vels tenant is seeded with Indian standard data."))
