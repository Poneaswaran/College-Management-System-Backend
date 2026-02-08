"""
Management command to seed attendance data for testing
Creates sample attendance sessions and records
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from attendance.models import AttendanceSession, StudentAttendance
from timetable.models import TimetableEntry
from profile_management.models import Semester


class Command(BaseCommand):
    help = 'Seed attendance data for testing'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Seeding Attendance Data...'))
        self.stdout.write('')
        
        # Get current semester
        semester = Semester.objects.filter(is_current=True).first()
        if not semester:
            self.stdout.write(self.style.ERROR('✗ No current semester found! Please create a semester first.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'✓ Using semester: {semester.academic_year.year_code} - Semester {semester.number}'))
        self.stdout.write('')
        
        # Get timetable entries
        timetable_entries = TimetableEntry.objects.filter(
            semester=semester,
            is_active=True
        ).select_related('subject', 'section', 'faculty', 'period_definition')[:5]
        
        if not timetable_entries.exists():
            self.stdout.write(self.style.ERROR('✗ No timetable entries found! Please create timetable entries first.'))
            return
        
        self.stdout.write(f'Found {timetable_entries.count()} timetable entries')
        self.stdout.write('')
        
        # Create attendance sessions for the past week
        today = timezone.now().date()
        sessions_created = 0
        attendances_created = 0
        
        for days_ago in range(7, 0, -1):
            date = today - timedelta(days=days_ago)
            day_of_week = date.isoweekday()
            
            self.stdout.write(f'Creating sessions for {date.strftime("%A, %B %d, %Y")}...')
            
            for entry in timetable_entries:
                # Only create if day matches
                if entry.period_definition.day_of_week != day_of_week:
                    continue
                
                # Create session
                session, created = AttendanceSession.objects.get_or_create(
                    timetable_entry=entry,
                    date=date,
                    defaults={
                        'status': 'CLOSED',
                        'opened_by': entry.faculty.user,
                        'opened_at': timezone.datetime.combine(
                            date,
                            entry.period_definition.start_time
                        ),
                        'closed_at': timezone.datetime.combine(
                            date,
                            entry.period_definition.end_time
                        ),
                        'attendance_window_minutes': 10
                    }
                )
                
                if created:
                    sessions_created += 1
                    
                    # Create attendance records for students
                    students = entry.section.students.all()
                    for student in students:
                        # Randomly mark 80% as present, 15% absent, 5% late
                        import random
                        rand = random.random()
                        
                        if rand < 0.80:
                            status = 'PRESENT'
                        elif rand < 0.95:
                            status = 'ABSENT'
                        else:
                            status = 'LATE'
                        
                        StudentAttendance.objects.create(
                            session=session,
                            student=student,
                            status=status,
                            marked_at=timezone.datetime.combine(
                                date,
                                entry.period_definition.start_time
                            ) + timedelta(minutes=random.randint(1, 10)),
                            is_manually_marked=True,
                            marked_by=entry.faculty.user,
                            notes='Seeded attendance data'
                        )
                        attendances_created += 1
                    
                    self.stdout.write(
                        f'  ✓ Created session: {entry.subject.name} - {entry.section.name} '
                        f'({students.count()} students)'
                    )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('═' * 60))
        self.stdout.write(self.style.SUCCESS(f'✓ Created {sessions_created} attendance sessions'))
        self.stdout.write(self.style.SUCCESS(f'✓ Created {attendances_created} attendance records'))
        self.stdout.write(self.style.SUCCESS('═' * 60))
        self.stdout.write('')
        
        # Calculate attendance reports
        self.stdout.write('Calculating attendance reports...')
        from attendance.models import AttendanceReport
        from profile_management.models import StudentProfile
        from timetable.models import Subject
        
        students = StudentProfile.objects.all()
        subjects = Subject.objects.filter(
            timetable_entries__semester=semester,
            timetable_entries__is_active=True
        ).distinct()
        
        reports_created = 0
        for student in students:
            for subject in subjects:
                # Check if student has any attendance in this subject
                has_attendance = StudentAttendance.objects.filter(
                    student=student,
                    session__timetable_entry__subject=subject,
                    session__timetable_entry__semester=semester
                ).exists()
                
                if has_attendance:
                    AttendanceReport.update_for_student_subject(student, subject, semester)
                    reports_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created/Updated {reports_created} attendance reports'))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🎉 Attendance data seeding complete!'))
        self.stdout.write('')
