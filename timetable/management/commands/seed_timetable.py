"""
Management command to seed initial timetable data
"""
from django.core.management.base import BaseCommand
from datetime import date, time

from profile_management.models import AcademicYear, Semester
from timetable.models import TimetableConfiguration


class Command(BaseCommand):
    help = 'Seed initial data for timetable system (AcademicYear, Semester, Configuration)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting timetable data seeding...'))
        
        # Create Academic Year
        self.stdout.write('Creating Academic Year...')
        academic_year, ay_created = AcademicYear.objects.get_or_create(
            year_code="2025-26",
            defaults={
                'start_date': date(2025, 7, 1),
                'end_date': date(2026, 6, 30),
                'is_current': True
            }
        )
        
        if ay_created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created Academic Year: {academic_year.year_code}'))
        else:
            self.stdout.write(self.style.WARNING(f'✓ Academic Year already exists: {academic_year.year_code}'))
        
        # Create Semester (Odd Semester)
        self.stdout.write('Creating Semester...')
        semester, sem_created = Semester.objects.get_or_create(
            academic_year=academic_year,
            number=1,  # Odd semester
            defaults={
                'start_date': date(2025, 7, 15),
                'end_date': date(2025, 12, 15),
                'is_current': True
            }
        )
        
        if sem_created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created Semester: {semester}'))
        else:
            self.stdout.write(self.style.WARNING(f'✓ Semester already exists: {semester}'))
        
        # Create Timetable Configuration
        self.stdout.write('Creating Timetable Configuration...')
        config, config_created = TimetableConfiguration.objects.get_or_create(
            semester=semester,
            defaults={
                'periods_per_day': 8,
                'default_period_duration': 50,
                'day_start_time': time(9, 30),
                'day_end_time': time(16, 30),
                'lunch_break_after_period': 4,
                'lunch_break_duration': 30,
                'short_break_duration': 10,
                'working_days': [1, 2, 3, 4, 5]  # Monday to Friday
            }
        )
        
        if config_created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created Timetable Configuration for {semester}'))
            self.stdout.write(self.style.SUCCESS(f'  - {config.periods_per_day} periods per day'))
            self.stdout.write(self.style.SUCCESS(f'  - {config.default_period_duration} minutes per period'))
            self.stdout.write(self.style.SUCCESS(f'  - Day timing: {config.day_start_time} to {config.day_end_time}'))
            self.stdout.write(self.style.SUCCESS(f'  - Working days: Mon-Fri'))
        else:
            self.stdout.write(self.style.WARNING(f'✓ Timetable Configuration already exists for {semester}'))
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('SEEDING COMPLETED SUCCESSFULLY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'Academic Year: {academic_year.year_code}'))
        self.stdout.write(self.style.SUCCESS(f'Semester: {semester}'))
        self.stdout.write(self.style.SUCCESS(f'Configuration: {config.periods_per_day} periods/day, {config.default_period_duration} mins each'))
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Next steps:'))
        self.stdout.write('1. Run: python manage.py runserver')
        self.stdout.write('2. Access admin at: http://localhost:8000/admin/')
        self.stdout.write('3. Access GraphQL at: http://localhost:8000/graphql/')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('To generate periods, use GraphQL mutation:'))
        self.stdout.write('mutation { generatePeriods(semesterId: 1) }')
        self.stdout.write('')
