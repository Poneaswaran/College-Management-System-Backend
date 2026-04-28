import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django_tenants.utils import tenant_context

from attendance.models import AttendanceSession, StudentAttendance, FacultyAttendance, AttendanceReport
from timetable.models import TimetableEntry, Subject
from profile_management.models import Semester, StudentProfile
from tenants.models import Client
from core.models import User

class Command(BaseCommand):
    help = 'Seed attendance data for students and faculty for testing'

    def add_arguments(self, parser):
        parser.add_argument('--schema', type=str, default='vels', help='Tenant schema name')
        parser.add_argument('--days', type=int, default=14, help='Number of days to seed')

    def handle(self, *args, **options):
        schema_name = options['schema']
        days_to_seed = options['days']
        
        try:
            tenant = Client.objects.get(schema_name=schema_name)
        except Client.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"[ERROR] Tenant '{schema_name}' does not exist."))
            return

        with tenant_context(tenant):
            self.stdout.write(f"--- Seeding Attendance System for {schema_name} ---")
            
            semester = Semester.objects.filter(is_current=True).first()
            if not semester:
                self.stdout.write(self.style.ERROR('[ERROR] No current semester found!'))
                return

            today = timezone.now().date()
            sessions_total = 0
            attendances_total = 0
            faculty_attendances_total = 0

            faculties = User.objects.filter(role__code__in=['FACULTY', 'HOD'])
            
            for days_ago in range(days_to_seed, -1, -1):
                date = today - timedelta(days=days_ago)
                if date.isoweekday() == 7: continue
                
                self.stdout.write(f'  -> Date: {date.strftime("%Y-%m-%d")}')

                with transaction.atomic():
                    # 1. Faculty Attendance
                    for faculty in faculties:
                        if random.random() < 0.10: continue
                        punch_in = timezone.datetime.combine(date, timezone.datetime.min.time().replace(hour=8, minute=random.randint(45, 59)))
                        punch_out = timezone.datetime.combine(date, timezone.datetime.min.time().replace(hour=16, minute=random.randint(0, 59)))
                        _, created = FacultyAttendance.objects.get_or_create(
                            faculty=faculty, date=date,
                            defaults={
                                'punch_in_time': timezone.make_aware(punch_in),
                                'punch_out_time': timezone.make_aware(punch_out),
                                'is_late': punch_in.hour >= 9 and punch_in.minute > 15
                            }
                        )
                        if created: faculty_attendances_total += 1

                    # 2. Student Attendance
                    day_of_week = date.isoweekday()
                    entries = TimetableEntry.objects.filter(
                        semester=semester, is_active=True,
                        period_definition__day_of_week=day_of_week
                    ).select_related('subject', 'section', 'faculty', 'period_definition')

                    for entry in entries:
                        session, created = AttendanceSession.objects.get_or_create(
                            timetable_entry=entry, date=date,
                            defaults={
                                'status': 'CLOSED',
                                'opened_by': entry.faculty,
                                'opened_at': timezone.make_aware(timezone.datetime.combine(date, entry.period_definition.start_time)),
                                'closed_at': timezone.make_aware(timezone.datetime.combine(date, entry.period_definition.end_time)),
                                'attendance_window_minutes': 15
                            }
                        )
                        
                        if created:
                            sessions_total += 1
                            students = entry.section.student_profiles.all()
                            
                            batch = []
                            for student in students:
                                rand = random.random()
                                status = 'PRESENT' if rand < 0.88 else ('ABSENT' if rand < 0.96 else 'LATE')
                                batch.append(StudentAttendance(
                                    session=session, student=student, status=status,
                                    marked_at=timezone.make_aware(timezone.datetime.combine(date, entry.period_definition.start_time)) + timedelta(minutes=random.randint(1, 10)),
                                    is_manually_marked=True, marked_by=entry.faculty, notes='Seeded'
                                ))
                            StudentAttendance.objects.bulk_create(batch)
                            attendances_total += len(batch)

            self.stdout.write(self.style.SUCCESS(f'[OK] Created {sessions_total} sessions, {attendances_total} student records, {faculty_attendances_total} faculty records'))

            # 3. Optimized Report Calculation
            self.stdout.write('Calculating attendance reports (optimized)...')
            
            AttendanceReport.objects.filter(semester=semester).delete()
            
            # Aggregate stats
            # We must handle both timetable_entry and combined_session subjects
            # For simplicity, we assume most are timetable_entry
            base_qs = StudentAttendance.objects.filter(
                Q(session__timetable_entry__semester=semester) | Q(session__combined_session__semester=semester),
                session__status='CLOSED'
            ).values('student', 'session__timetable_entry__subject', 'session__combined_session__subject')
            
            stats = base_qs.annotate(
                total=Count('id'),
                presents=Count('id', filter=Q(status='PRESENT')),
                absents=Count('id', filter=Q(status='ABSENT')),
                lates=Count('id', filter=Q(status='LATE'))
            )
            
            reports_map = {}
            for item in stats:
                subject_id = item['session__timetable_entry__subject'] or item['session__combined_session__subject']
                if not subject_id: continue
                
                key = (item['student'], subject_id)
                if key not in reports_map:
                    reports_map[key] = {
                        'total': 0, 'presents': 0, 'absents': 0, 'lates': 0
                    }
                
                reports_map[key]['total'] += item['total']
                reports_map[key]['presents'] += item['presents']
                reports_map[key]['absents'] += item['absents']
                reports_map[key]['lates'] += item['lates']

            final_reports = []
            for (student_id, subject_id), data in reports_map.items():
                total = data['total']
                effective_present = data['presents'] + data['lates']
                percentage = round((effective_present / total) * 100, 2) if total > 0 else 0.0
                
                final_reports.append(AttendanceReport(
                    student_id=student_id,
                    subject_id=subject_id,
                    semester=semester,
                    total_classes=total,
                    present_count=data['presents'],
                    absent_count=data['absents'],
                    late_count=data['lates'],
                    attendance_percentage=percentage,
                    is_below_threshold=percentage < 75.0
                ))

            # Bulk create in chunks
            for i in range(0, len(final_reports), 1000):
                AttendanceReport.objects.bulk_create(final_reports[i:i+1000])
            
            self.stdout.write(self.style.SUCCESS(f'[DONE] Seeding complete! Total reports: {len(final_reports)}'))
