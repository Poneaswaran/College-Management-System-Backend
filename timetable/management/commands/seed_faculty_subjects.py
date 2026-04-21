from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from datetime import date
import random

from core.models import Department, Role, Section
from profile_management.models import FacultyProfile, Semester
from timetable.models import Subject, SectionSubjectRequirement

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed faculty and subjects across all departments and link them to sections'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting faculty and subject seeding...'))

        with transaction.atomic():
            # 1. Get current semester
            semester = Semester.objects.filter(is_current=True).first()
            if not semester:
                self.stdout.write(self.style.ERROR('No current semester found! Run seed_timetable_grid first.'))
                return

            # 2. Get Faculty Role
            faculty_role = Role.objects.get(code='FACULTY')

            # 3. Define subjects for each department
            dept_subjects = {
                'CSE': [
                    ('CS101', 'Intro to Computing', 1),
                    ('CS102', 'Programming in C', 1),
                    ('CS103', 'Digital Logic', 1),
                    ('CS301', 'Data Structures', 3),
                    ('CS302', 'Discrete Mathematics', 3),
                    ('CS303', 'Computer Architecture', 3),
                    ('CS501', 'Operating Systems', 5),
                    ('CS502', 'Computer Networks', 5),
                    ('CS503', 'Database Management Systems', 5),
                    ('CS504', 'Theory of Computation', 5),
                    ('CS505', 'Software Engineering', 5),
                    ('CS506', 'System Programming', 5),
                    ('CS701', 'Artificial Intelligence', 7),
                    ('CS702', 'Cloud Computing', 7),
                    ('CS703', 'Network Security', 7),
                ],
                'ECE': [
                    ('EC101', 'Basic Electronics', 1),
                    ('EC301', 'Digital Electronics', 3),
                    ('EC501', 'Microprocessors', 5),
                    ('EC701', 'Wireless Communication', 7),
                    ('EC102', 'Electric Circuits', 1),
                    ('EC302', 'Signals and Systems', 3),
                ],
                'MECH': [
                    ('ME101', 'Engineering Graphics', 1),
                    ('ME301', 'Thermodynamics', 3),
                    ('ME501', 'Fluid Mechanics', 5),
                    ('ME701', 'Finite Element Analysis', 7),
                    ('ME102', 'Workshop Practice', 1),
                    ('ME302', 'Solid Mechanics', 3),
                ],
                'IT': [
                    ('IT101', 'IT Essentials', 1),
                    ('IT301', 'Web Technologies', 3),
                    ('IT501', 'Software Engineering', 5),
                    ('IT701', 'Cloud Computing', 7),
                    ('IT102', 'Digital Logic', 1),
                    ('IT302', 'Computer Networks', 3),
                ],
                'CIVIL': [
                    ('CE101', 'Mechanics of Solids', 1),
                    ('CE301', 'Surveying', 3),
                    ('CE501', 'Structural Analysis', 5),
                    ('CE701', 'Foundation Engineering', 7),
                    ('CE102', 'Basic Surveying', 1),
                    ('CE302', 'Construction Materials', 3),
                ],
            }

            # 4. Process Departments
            departments = Department.objects.all()
            for dept in departments:
                self.stdout.write(f"Processing Department: {dept.code}")
                
                # Create Subjects
                subject_objs = []
                for code, name, sem_num in dept_subjects.get(dept.code, []):
                    sub, _ = Subject.objects.get_or_create(
                        code=code,
                        defaults={
                            'name': name,
                            'department': dept,
                            'semester_number': sem_num,
                            'credits': 4.0,
                            'subject_type': 'THEORY' if 'Lab' not in name else 'LAB'
                        }
                    )
                    subject_objs.append(sub)
                
                # Create Faculty
                faculty_names = [
                    ("Alice", "Johnson"), ("Bob", "Smith"), ("Charlie", "Davis"), 
                    ("Diana", "Prince"), ("Edward", "Norton"), ("Fiona", "Gallagher"),
                    ("George", "Clooney"), ("Hannah", "Baker"), ("Ian", "Somerhalder"),
                    ("Julia", "Roberts"), ("Kevin", "Hart"), ("Laura", "Palmer")
                ]
                faculty_objs = []
                for i, (first, last) in enumerate(faculty_names, 1):
                    email = f"{first.lower()}.{last.lower()}.{dept.code.lower()}@college.edu"
                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            'role': faculty_role,
                            'department': dept,
                        }
                    )
                    if created:
                        user.set_password('password123')
                        user.save()
                    
                    profile, _ = FacultyProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'first_name': first,
                            'last_name': last,
                            'department': dept,
                            'designation': 'Assistant Professor',
                            'qualifications': 'Ph.D.',
                            'specialization': dept.name,
                            'joining_date': date(2020, 1, 1),
                            'teaching_load': 20,
                        }
                    )
                    faculty_objs.append(user)

                # 5. Link Subjects to Sections via Requirements
                # Odd Semesters (1, 3, 5, 7) correspond to Years 1, 2, 3, 4
                year_sem_map = {1: 1, 2: 3, 3: 5, 4: 7}
                sections = Section.objects.filter(course__department=dept)
                
                for section in sections:
                    target_sem = year_sem_map.get(section.year)
                    if not target_sem:
                        continue
                    
                    section_subjects = [s for s in subject_objs if s.semester_number == target_sem]
                    
                    for sub in section_subjects:
                        # Assign a random faculty member from the department to this subject for this section
                        faculty = random.choice(faculty_objs)
                        
                        SectionSubjectRequirement.objects.update_or_create(
                            section=section,
                            semester=semester,
                            subject=sub,
                            defaults={
                                'faculty': faculty,
                                'periods_per_week': 4 if sub.subject_type == 'THEORY' else 3
                            }
                        )

            self.stdout.write(self.style.SUCCESS('Successfully seeded faculty and assigned subjects to sections.'))
