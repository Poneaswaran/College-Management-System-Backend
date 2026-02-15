"""
pipenv run python manage.py seed_profiles
Management command to seed dummy user profiles for testing
Creates sample students, faculty, HOD, and admin users
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import date, timedelta

from core.models import User, Role, Department, Course, Section
from profile_management.models import StudentProfile, AcademicYear, Semester


class Command(BaseCommand):
    help = 'Seed dummy user profiles (students, faculty, HOD, admin)'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('Seeding User Profiles...'))
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write('')
        
        with transaction.atomic():
            # Get or create roles
            admin_role = self.get_or_create_role('ADMIN', 'System Administrator', is_global=True)
            student_role = self.get_or_create_role('STUDENT', 'Student', is_global=True)
            faculty_role = self.get_or_create_role('FACULTY', 'Faculty', is_global=True)
            hod_role = self.get_or_create_role('HOD', 'Head of Department', is_global=True)
            
            # Get or create departments
            cse_dept = self.get_or_create_department('Computer Science Engineering', 'CSE')
            ece_dept = self.get_or_create_department('Electronics & Communication', 'ECE')
            mech_dept = self.get_or_create_department('Mechanical Engineering', 'MECH')
            
            # Get or create courses
            btech_cse = self.get_or_create_course(cse_dept, 'B.Tech Computer Science', 'BTECH_CSE', 4)
            btech_ece = self.get_or_create_course(ece_dept, 'B.Tech ECE', 'BTECH_ECE', 4)
            btech_mech = self.get_or_create_course(mech_dept, 'B.Tech Mechanical', 'BTECH_MECH', 4)
            
            # Get or create sections
            cse_year1_a = self.get_or_create_section(btech_cse, 'A', 1)
            cse_year2_a = self.get_or_create_section(btech_cse, 'A', 2)
            ece_year1_a = self.get_or_create_section(btech_ece, 'A', 1)
            
            # Get or create academic year and semester
            academic_year = self.get_or_create_academic_year()
            semester = self.get_or_create_semester(academic_year)
            
            self.stdout.write('')
            
            # Create admin user
            self.stdout.write(self.style.WARNING('Creating Admin User...'))
            admin_user = self.create_admin_user(admin_role)
            
            # Create HOD users
            self.stdout.write(self.style.WARNING('\nCreating HOD Users...'))
            hod1 = self.create_hod_user(1, hod_role, cse_dept)
            hod2 = self.create_hod_user(2, hod_role, ece_dept)
            hod3 = self.create_hod_user(3, hod_role, mech_dept)
            
            # Create faculty users
            self.stdout.write(self.style.WARNING('\nCreating Faculty Users...'))
            faculty_users = []
            for i in range(1, 11):
                dept = cse_dept if i <= 4 else (ece_dept if i <= 7 else mech_dept)
                faculty = self.create_faculty_user(i, faculty_role, dept)
                faculty_users.append(faculty)
            
            # Create student users with profiles
            self.stdout.write(self.style.WARNING('\nCreating Student Users and Profiles...'))
            for i in range(1, 11):
                if i <= 4:
                    dept, course, section = cse_dept, btech_cse, cse_year1_a
                    year, semester_num = 1, 1
                elif i <= 7:
                    dept, course, section = cse_dept, btech_cse, cse_year2_a
                    year, semester_num = 2, 3
                else:
                    dept, course, section = ece_dept, btech_ece, ece_year1_a
                    year, semester_num = 1, 1
                
                self.create_student_user_with_profile(
                    i, student_role, dept, course, section, year, semester_num
                )
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('✓ ALL PROFILES CREATED SUCCESSFULLY!'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write('')
            
            # Print summary
            self.print_summary(admin_user, [hod1, hod2, hod3], faculty_users)
    
    def get_or_create_role(self, code, name, is_global=True):
        """Get or create a role"""
        role, created = Role.objects.get_or_create(
            code=code,
            is_global=is_global,
            department=None,
            defaults={
                'name': name,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  ✓ Created role: {name}')
        return role
    
    def get_or_create_department(self, name, code):
        """Get or create a department"""
        dept, created = Department.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  ✓ Created department: {name}')
        return dept
    
    def get_or_create_course(self, department, name, code, duration_years):
        """Get or create a course"""
        course, created = Course.objects.get_or_create(
            department=department,
            code=code,
            defaults={
                'name': name,
                'duration_years': duration_years
            }
        )
        if created:
            self.stdout.write(f'  ✓ Created course: {name}')
        return course
    
    def get_or_create_section(self, course, name, year):
        """Get or create a section"""
        section, created = Section.objects.get_or_create(
            course=course,
            name=name,
            year=year
        )
        if created:
            self.stdout.write(f'  ✓ Created section: {course.code} Year-{year} Section-{name}')
        return section
    
    def get_or_create_academic_year(self):
        """Get or create academic year"""
        academic_year, created = AcademicYear.objects.get_or_create(
            year_code='2025-26',
            defaults={
                'start_date': date(2025, 7, 1),
                'end_date': date(2026, 6, 30),
                'is_current': True
            }
        )
        if created:
            self.stdout.write(f'  ✓ Created academic year: 2025-26')
        return academic_year
    
    def get_or_create_semester(self, academic_year):
        """Get or create semester"""
        semester, created = Semester.objects.get_or_create(
            academic_year=academic_year,
            number=1,
            defaults={
                'start_date': date(2025, 7, 1),
                'end_date': date(2025, 12, 31),
                'is_current': True
            }
        )
        if created:
            self.stdout.write(f'  ✓ Created semester: Odd Semester 2025-26')
        return semester
    
    def create_admin_user(self, admin_role):
        """Create admin user"""
        email = 'bala@gmail.com'
        
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'  ⚠ Admin user {email} already exists, skipping...'))
            return User.objects.get(email=email)
        
        user = User.objects.create_user(
            email=email,
            password='Test@123',
            role=admin_role,
            is_staff=True,
            is_superuser=True
        )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created admin user: {email}'))
        return user
    
    def create_hod_user(self, index, hod_role, department):
        """Create HOD user"""
        email = f'hod{index}@college.edu'
        
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'  ⚠ HOD {email} already exists, skipping...'))
            return User.objects.get(email=email)
        
        user = User.objects.create_user(
            email=email,
            password='Test@123',
            role=hod_role,
            department=department,
            is_staff=True
        )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created HOD: {email} ({department.name})'))
        return user
    
    def create_faculty_user(self, index, faculty_role, department):
        """Create faculty user"""
        email = f'faculty{index}@college.edu'
        
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'  ⚠ Faculty {email} already exists, skipping...'))
            return User.objects.get(email=email)
        
        user = User.objects.create_user(
            email=email,
            password='Test@123',
            role=faculty_role,
            department=department,
            is_staff=False
        )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created faculty: {email} ({department.code})'))
        return user
    
    def create_student_user_with_profile(self, index, student_role, department, 
                                        course, section, year, semester_num):
        """Create student user with complete profile"""
        register_number = f'REG{2025}{department.code}{str(index).zfill(4)}'
        email = f'student{index}@college.edu'
        
        if User.objects.filter(register_number=register_number).exists():
            self.stdout.write(self.style.WARNING(
                f'  ⚠ Student {register_number} already exists, skipping...'
            ))
            return
        
        # Create user
        user = User.objects.create_user(
            email=email,
            register_number=register_number,
            password='Test@123',
            role=student_role,
            department=department,
            is_staff=False
        )
        
        # Student names for variety
        first_names = [
            'Rajesh', 'Priya', 'Amit', 'Sneha', 'Vijay',
            'Ananya', 'Karthik', 'Divya', 'Arun', 'Meera'
        ]
        last_names = [
            'Kumar', 'Sharma', 'Patel', 'Reddy', 'Singh',
            'Krishnan', 'Iyer', 'Nair', 'Gupta', 'Rao'
        ]
        
        # Create student profile with complete information
        profile = StudentProfile.objects.create(
            user=user,
            first_name=first_names[index - 1],
            last_name=last_names[index - 1],
            phone=f'+91{9000000000 + index}',
            date_of_birth=date(2005, 1, 1) + timedelta(days=index * 30),
            gender='MALE' if index % 2 == 1 else 'FEMALE',
            address=f'{index * 10} Main Street, Block {chr(64 + index)}, City, State - 560001',
            
            # Academic information
            register_number=register_number,
            roll_number=f'ROLL{year}{section.name}{str(index).zfill(3)}',
            department=department,
            course=course,
            section=section,
            year=year,
            semester=semester_num,
            admission_date=date(2025, 7, 1) - timedelta(days=(year - 1) * 365),
            academic_status='ACTIVE',
            
            # Guardian details
            guardian_name=f'{first_names[index - 1]} {last_names[index - 1]} Sr.',
            guardian_relationship='Father' if index % 2 == 1 else 'Mother',
            guardian_phone=f'+91{8000000000 + index}',
            guardian_email=f'guardian{index}@email.com',
            
            # Identification
            aadhar_number=f'{100000000000 + index}',
            id_proof_type='AADHAR',
            id_proof_number=f'{100000000000 + index}',
            
            # Meta fields
            is_active=True,
            profile_completed=True
        )
        
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ Created student: {register_number} - {profile.full_name} '
            f'({department.code}, Year-{year})'
        ))
        
        return user, profile
    
    def print_summary(self, admin_user, hod_users, faculty_users):
        """Print summary of created profiles"""
        self.stdout.write(self.style.SUCCESS('\nSUMMARY:'))
        self.stdout.write(self.style.SUCCESS('-' * 60))
        
        self.stdout.write('\n📌 ADMIN ACCOUNT:')
        self.stdout.write(f'   Email: {admin_user.email}')
        self.stdout.write(f'   Password: Test@123')
        
        self.stdout.write('\n📌 HOD ACCOUNTS (3):')
        for hod in hod_users:
            self.stdout.write(f'   {hod.email} - {hod.department.name}')
        self.stdout.write('   Password: Test@123')
        
        self.stdout.write('\n📌 FACULTY ACCOUNTS (10):')
        self.stdout.write('   faculty1@college.edu to faculty10@college.edu')
        self.stdout.write('   Password: Test@123')
        
        self.stdout.write('\n📌 STUDENT ACCOUNTS (10):')
        student_profiles = StudentProfile.objects.all()[:10]
        for profile in student_profiles:
            self.stdout.write(
                f'   {profile.register_number} - {profile.full_name} '
                f'({profile.user.email})'
            )
        self.stdout.write('   Password: Test@123')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('All users have password: Test@123'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
