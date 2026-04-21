from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import date, time, timedelta
from core.models import Department, Course, Section
from profile_management.models import AcademicYear, Semester
from timetable.models import Period, TimetableSlot, PeriodDefinition
from configuration.models import TimetableConfiguration


class Command(BaseCommand):
    help = 'Seed timetable grid for all departments with 10 periods (9:30 AM - 4:00 PM)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting comprehensive timetable grid seeding...'))

        with transaction.atomic():
            # 1. Academic Year & Semester
            academic_year, _ = AcademicYear.objects.get_or_create(
                year_code="2025-26",
                defaults={
                    'start_date': date(2025, 7, 1),
                    'end_date': date(2026, 6, 30),
                    'is_current': True
                }
            )

            semester, _ = Semester.objects.get_or_create(
                academic_year=academic_year,
                number=1,
                defaults={
                    'start_date': date(2025, 7, 15),
                    'end_date': date(2025, 12, 15),
                    'is_current': True
                }
            )
            self.stdout.write(f"[OK] Using Semester: {semester}")

            # 1.5 Timetable Configuration
            config, _ = TimetableConfiguration.objects.get_or_create(
                semester=semester,
                defaults={
                    'periods_per_day': 10,
                    'default_period_duration': 35,
                    'day_start_time': time(9, 30),
                    'day_end_time': time(16, 0),
                    'lunch_break_after_period': 4,
                    'lunch_break_duration': 40,
                    'working_days': [1, 2, 3, 4, 5, 6]
                }
            )
            if config.periods_per_day != 10:
                config.periods_per_day = 10
                config.default_period_duration = 35
                config.day_start_time = time(9, 30)
                config.day_end_time = time(16, 0)
                config.lunch_break_after_period = 4
                config.lunch_break_duration = 40
                config.working_days = [1, 2, 3, 4, 5, 6]
                config.save()
            self.stdout.write(f"[OK] Set Timetable Configuration: 10 periods, 9:30 AM - 4:00 PM")

            # 2. Departments, Courses, and Sections
            dept_data = [
                ('Computer Science and Engineering', 'CSE'),
                ('Electronics and Communication Engineering', 'ECE'),
                ('Mechanical Engineering', 'MECH'),
                ('Information Technology', 'IT'),
                ('Civil Engineering', 'CIVIL'),
            ]

            all_sections = []
            for name, code in dept_data:
                dept, _ = Department.objects.get_or_create(code=code, defaults={'name': name})
                course, _ = Course.objects.get_or_create(
                    department=dept,
                    code=f"BTECH_{code}",
                    defaults={'name': f"B.Tech {code}", 'duration_years': 4}
                )
                
                # Create one section for each year
                for year in range(1, 5):
                    section, created = Section.objects.get_or_create(
                        course=course,
                        year=year,
                        code='A',
                        defaults={
                            'name': f"{course.name} Year {year} Section A",
                            'priority': 1 if year == 4 else (2 if year == 2 else 3)
                        }
                    )
                    all_sections.append(section)
            
            self.stdout.write(f"[OK] Created/Verified {len(all_sections)} sections across {len(dept_data)} departments.")

            # 3. Periods (9:30 AM to 4:00 PM)
            # 10 teaching periods of 35 mins + 1 lunch break of 40 mins
            # Total 390 mins
            period_times = [
                ("Period 1", time(9, 30), time(10, 5), False),
                ("Period 2", time(10, 5), time(10, 40), False),
                ("Period 3", time(10, 40), time(11, 15), False),
                ("Period 4", time(11, 15), time(11, 50), False),
                ("Lunch Break", time(11, 50), time(12, 30), True),
                ("Period 5", time(12, 30), time(13, 5), False),
                ("Period 6", time(13, 5), time(13, 40), False),
                ("Period 7", time(13, 40), time(14, 15), False),
                ("Period 8", time(14, 15), time(14, 50), False),
                ("Period 9", time(14, 50), time(15, 25), False),
                ("Period 10", time(15, 25), time(16, 0), False),
            ]

            period_objs = []
            for i, (label, start, end, is_break) in enumerate(period_times):
                period, created = Period.objects.get_or_create(
                    order=i + 1,
                    defaults={
                        'label': label,
                        'start_time': start,
                        'end_time': end,
                        'is_break': is_break
                    }
                )
                if not created:
                    # Update existing periods to match the new timing if they exist
                    period.label = label
                    period.start_time = start
                    period.end_time = end
                    period.is_break = is_break
                    period.save()
                period_objs.append(period)
            
            self.stdout.write(f"[OK] Created 11 periods (10 teaching + 1 lunch).")

            # 4. PeriodDefinitions (for TimetableEntry logic)
            # We need these for each day of the week
            days_of_week = [
                (1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), 
                (4, 'Thursday'), (5, 'Friday'), (6, 'Saturday')
            ]
            
            pdef_count = 0
            for day_num, day_name in days_of_week:
                for i, period_obj in enumerate(period_objs):
                    # PeriodDefinition uses period_number which is separate from Period.order
                    # We'll map them 1:1 for simplicity
                    pdef, _ = PeriodDefinition.objects.get_or_create(
                        semester=semester,
                        day_of_week=day_num,
                        period_number=i + 1,
                        defaults={
                            'start_time': period_obj.start_time,
                            'end_time': period_obj.end_time,
                            'duration_minutes': 35 if not period_obj.is_break else 40
                        }
                    )
                    pdef_count += 1
            
            self.stdout.write(f"[OK] Created {pdef_count} PeriodDefinition entries for the semester.")

            # 5. TimetableSlots (The Grid)
            slot_count = 0
            days_str = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            
            # Prepare bulk creation
            slots_to_create = []
            
            # Existing slots to avoid duplicates
            existing_slots = set(
                TimetableSlot.objects.values_list('class_section_id', 'day', 'period_id')
            )

            for section in all_sections:
                for day in days_str:
                    for period in period_objs:
                        if (section.id, day, period.id) not in existing_slots:
                            slots_to_create.append(TimetableSlot(
                                class_section=section,
                                day=day,
                                period=period
                            ))
            
            if slots_to_create:
                TimetableSlot.objects.bulk_create(slots_to_create)
                slot_count = len(slots_to_create)
            
            self.stdout.write(f"[OK] Created {slot_count} new TimetableSlot entries (empty grid cells).")

        self.stdout.write(self.style.SUCCESS(f'COMPLETED: Seeded timetable grid for {len(all_sections)} sections.'))
        self.stdout.write(self.style.SUCCESS('Timing: 9:30 AM to 4:00 PM (10 periods + 1 lunch)'))
