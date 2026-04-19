"""
Management command to seed realistic HOD-facing attendance demo data.
Creates sections, faculty, subjects, timetable entries, students, sessions,
attendance records, and recalculated reports for the current department.
"""
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from attendance.models import AttendanceReport, AttendanceSession, StudentAttendance
from core.models import Course, Department, Role, Section, User
from profile_management.models import FacultyProfile, Semester, StudentProfile
from timetable.models import PeriodDefinition, Subject, TimetableEntry


class Command(BaseCommand):
    help = "Seed realistic dummy attendance data for HOD dashboards"

    faculty_specs = [
        ("faculty@gmail.com", "Arun", "Prakash", "Assistant Professor", "Artificial Intelligence"),
        ("faculty.ai1@college.edu", "Nivetha", "Raman", "Assistant Professor", "Machine Learning"),
        ("faculty.ai2@college.edu", "Kiran", "Mohan", "Associate Professor", "Data Engineering"),
        ("faculty.ai3@college.edu", "Swetha", "Balan", "Assistant Professor", "Statistics"),
    ]

    subject_specs = [
        ("AML301", "Foundations of Machine Learning"),
        ("AML302", "Data Structures for AI"),
        ("AML303", "Probability and Statistics"),
        ("AML304", "Database Systems"),
    ]

    period_specs = [
        (1, time(9, 0), time(9, 50)),
        (2, time(10, 0), time(10, 50)),
        (3, time(11, 5), time(11, 55)),
        (4, time(13, 30), time(14, 20)),
    ]

    student_names = [
        ("Aakash", "M"),
        ("Harini", "R"),
        ("Vishal", "K"),
        ("Keerthana", "S"),
        ("Dinesh", "P"),
        ("Pavithra", "N"),
        ("Jeevan", "T"),
        ("Nandhini", "V"),
        ("Mithun", "L"),
        ("Sanjana", "A"),
        ("Rohit", "C"),
        ("Varsha", "D"),
    ]

    performance_buckets = [
        "GOOD",
        "GOOD",
        "WARNING",
        "CRITICAL",
        "GOOD",
        "WARNING",
        "GOOD",
        "CRITICAL",
        "GOOD",
        "WARNING",
        "CRITICAL",
        "GOOD",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--weeks",
            type=int,
            default=4,
            help="Number of recent weeks of sessions to generate",
        )

    def handle(self, *args, **options):
        weeks = max(2, options["weeks"])
        semester = Semester.objects.filter(is_current=True).order_by("-start_date").first()

        if not semester:
            self.stdout.write(self.style.ERROR("No current semester found."))
            return

        department = self._get_target_department()
        if not department:
            self.stdout.write(self.style.ERROR("No department available to seed HOD demo data."))
            return

        course = Course.objects.filter(department=department).order_by("id").first()
        if not course:
            course = Course.objects.create(
                department=department,
                name=f"{department.name} Program",
                code=self._slugify_code(f"{department.code}_PROGRAM"),
                duration_years=4,
            )

        self.stdout.write(self.style.WARNING("Seeding realistic HOD dashboard demo data..."))
        self.stdout.write(f"Department: {department.name} ({department.code})")
        self.stdout.write(f"Semester: {semester}")

        with transaction.atomic():
            faculty_role = Role.objects.get(code="FACULTY", is_global=True)
            student_role = Role.objects.get(code="STUDENT", is_global=True)

            faculties = self._ensure_faculties(department, faculty_role)
            sections = self._ensure_sections(course)
            subjects = self._ensure_subjects(department)
            periods = self._ensure_periods(semester)
            timetable_entries = self._ensure_timetable_entries(semester, sections, periods, subjects, faculties)
            students = self._ensure_students(department, course, sections, student_role)
            session_count, attendance_count = self._ensure_sessions_and_attendance(semester, timetable_entries, students, weeks)
            report_count = self._recalculate_reports(semester, students, subjects)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("HOD demo data ready."))
        self.stdout.write(self.style.SUCCESS(f"Sections active: {len(sections)}"))
        self.stdout.write(self.style.SUCCESS(f"Subjects active: {len(subjects)}"))
        self.stdout.write(self.style.SUCCESS(f"Students covered: {len(students)}"))
        self.stdout.write(self.style.SUCCESS(f"Sessions created/updated: {session_count}"))
        self.stdout.write(self.style.SUCCESS(f"Attendance records created/updated: {attendance_count}"))
        self.stdout.write(self.style.SUCCESS(f"Reports recalculated: {report_count}"))

    def _get_target_department(self):
        faculty_profile = FacultyProfile.objects.select_related("department").filter(department__isnull=False).order_by("id").first()
        if faculty_profile:
            return faculty_profile.department

        hod_user = User.objects.select_related("department").filter(role__code="HOD", department__isnull=False).order_by("id").first()
        if hod_user:
            return hod_user.department

        return Department.objects.order_by("id").first()

    def _ensure_faculties(self, department, faculty_role):
        faculties = []
        for email, first_name, last_name, designation, specialization in self.faculty_specs:
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "password": "",
                    "role": faculty_role,
                    "department": department,
                    "is_staff": False,
                },
            )

            updated = False
            if user.role_id != faculty_role.id:
                user.role = faculty_role
                updated = True
            if user.department_id != department.id:
                user.department = department
                updated = True
            if not user.password or not user.has_usable_password():
                user.set_password("Test@123")
                updated = True
            if updated:
                user.save()

            profile, created = FacultyProfile.objects.get_or_create(
                user=user,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "department": department,
                    "designation": designation,
                    "qualifications": "M.E., Ph.D.",
                    "specialization": specialization,
                    "joining_date": date(2022, 6, 1),
                    "office_hours": "Mon-Fri 14:30-16:00",
                    "teaching_load": 16,
                    "is_active": True,
                },
            )

            if not created:
                profile.department = department
                profile.first_name = profile.first_name or first_name
                profile.last_name = profile.last_name or last_name
                profile.designation = profile.designation or designation
                profile.qualifications = profile.qualifications or "M.E., Ph.D."
                profile.specialization = profile.specialization or specialization
                profile.office_hours = profile.office_hours or "Mon-Fri 14:30-16:00"
                profile.teaching_load = profile.teaching_load or 16
                if not profile.joining_date:
                    profile.joining_date = date(2022, 6, 1)
                profile.save()

            faculties.append(user)

        return faculties

    def _ensure_sections(self, course):
        sections = [
            Section.objects.get_or_create(course=course, name="A", year=3)[0],
            Section.objects.get_or_create(course=course, name="B", year=3)[0],
        ]
        return sections

    def _ensure_subjects(self, department):
        subjects = []
        semester_number = 1
        for code, name in self.subject_specs:
            subject, _ = Subject.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "department": department,
                    "semester_number": semester_number,
                    "credits": 4.0,
                    "subject_type": "THEORY",
                    "is_active": True,
                },
            )
            if subject.department_id != department.id:
                subject.department = department
                subject.save(update_fields=["department"])
            subjects.append(subject)
        return subjects

    def _ensure_periods(self, semester):
        periods = {}
        for day_of_week in range(1, 6):
            for period_number, start_time, end_time in self.period_specs:
                period, _ = PeriodDefinition.objects.get_or_create(
                    semester=semester,
                    day_of_week=day_of_week,
                    period_number=period_number,
                    defaults={
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration_minutes": 50,
                    },
                )
                periods[(day_of_week, period_number)] = period
        return periods

    def _ensure_timetable_entries(self, semester, sections, periods, subjects, faculties):
        schedule = {
            "A": {
                1: [0, 1, 2, 3],
                2: [1, 0, 3, 2],
                3: [2, 3, 0, 1],
                4: [0, 2, 1, 3],
                5: [3, 1, 2, 0],
            },
            "B": {
                1: [1, 2, 0, 3],
                2: [2, 1, 3, 0],
                3: [0, 3, 1, 2],
                4: [3, 0, 2, 1],
                5: [1, 3, 0, 2],
            },
        }

        entries = []
        for section in sections:
            section_schedule = schedule[section.name]
            for day_of_week in range(1, 6):
                for period_number in range(1, 5):
                    subject = subjects[section_schedule[day_of_week][period_number - 1]]
                    faculty = faculties[(period_number + day_of_week + section.id) % len(faculties)]
                    entry, _ = TimetableEntry.objects.get_or_create(
                        section=section,
                        period_definition=periods[(day_of_week, period_number)],
                        semester=semester,
                        defaults={
                            "subject": subject,
                            "faculty": faculty,
                            "is_active": True,
                        },
                    )
                    needs_save = False
                    if entry.subject_id != subject.id:
                        entry.subject = subject
                        needs_save = True
                    if entry.faculty_id != faculty.id:
                        entry.faculty = faculty
                        needs_save = True
                    if not entry.is_active:
                        entry.is_active = True
                        needs_save = True
                    if needs_save:
                        entry.save()
                    entries.append(entry)
        return entries

    def _ensure_students(self, department, course, sections, student_role):
        students = []
        for index, (first_name, last_name) in enumerate(self.student_names, start=1):
            section = sections[0] if index <= 6 else sections[1]
            register_number = f"HOD26{self._slugify_code(department.code)[:4]}{index:03d}"
            email = f"hod.student{index:02d}@college.edu"
            user, _ = User.objects.get_or_create(
                register_number=register_number,
                defaults={
                    "email": email,
                    "role": student_role,
                    "department": department,
                    "is_staff": False,
                },
            )

            user_changed = False
            if not user.email:
                user.email = email
                user_changed = True
            if user.role_id != student_role.id:
                user.role = student_role
                user_changed = True
            if user.department_id != department.id:
                user.department = department
                user_changed = True
            if not user.password or not user.has_usable_password():
                user.set_password("Test@123")
                user_changed = True
            if user_changed:
                user.save()

            semester_number = 5
            profile, _ = StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": f"+9199000{index:05d}",
                    "register_number": register_number,
                    "roll_number": f"{section.name}{index:03d}",
                    "department": department,
                    "course": course,
                    "section": section,
                    "year": section.year,
                    "semester": semester_number,
                    "academic_status": "ACTIVE",
                    "guardian_name": f"{first_name} Parent",
                    "guardian_relationship": "Parent",
                    "guardian_phone": f"+9188000{index:05d}",
                    "profile_completed": True,
                    "is_active": True,
                },
            )

            profile.first_name = profile.first_name or first_name
            profile.last_name = profile.last_name or last_name
            profile.phone = profile.phone or f"+9199000{index:05d}"
            profile.register_number = register_number
            profile.roll_number = profile.roll_number or f"{section.name}{index:03d}"
            profile.department = department
            profile.course = course
            profile.section = section
            profile.year = section.year
            profile.semester = semester_number
            profile.academic_status = "ACTIVE"
            profile.profile_completed = True
            profile.is_active = True
            profile.save()
            students.append(profile)

        return students

    def _ensure_sessions_and_attendance(self, semester, timetable_entries, students, weeks):
        del semester  # semester is already encoded in timetable entries
        students_by_section = {}
        for student in students:
            students_by_section.setdefault(student.section_id, []).append(student)

        start_date = timezone.localdate() - timedelta(days=(weeks * 7) - 1)
        end_date = timezone.localdate()
        session_count = 0
        attendance_count = 0

        for entry in timetable_entries:
            current_date = start_date
            while current_date <= end_date:
                if current_date.isoweekday() != entry.period_definition.day_of_week:
                    current_date += timedelta(days=1)
                    continue

                opened_at = self._aware_datetime(current_date, entry.period_definition.start_time)
                closed_at = self._aware_datetime(current_date, entry.period_definition.end_time)
                session, created = AttendanceSession.objects.get_or_create(
                    timetable_entry=entry,
                    date=current_date,
                    defaults={
                        "status": "CLOSED",
                        "opened_by": entry.faculty,
                        "opened_at": opened_at,
                        "closed_at": closed_at,
                        "attendance_window_minutes": 10,
                        "notes": "Seeded HOD demo session",
                    },
                )

                if not created:
                    dirty = False
                    if session.status != "CLOSED":
                        session.status = "CLOSED"
                        dirty = True
                    if session.opened_by_id != entry.faculty_id:
                        session.opened_by = entry.faculty
                        dirty = True
                    if session.opened_at != opened_at:
                        session.opened_at = opened_at
                        dirty = True
                    if session.closed_at != closed_at:
                        session.closed_at = closed_at
                        dirty = True
                    if session.notes != "Seeded HOD demo session":
                        session.notes = "Seeded HOD demo session"
                        dirty = True
                    if dirty:
                        session.save()

                session_count += 1
                for student in students_by_section.get(entry.section_id, []):
                    status = self._attendance_status(student, entry, current_date)
                    marked_at = opened_at + timedelta(minutes=(student.id + entry.period_definition.period_number) % 7)
                    StudentAttendance.objects.update_or_create(
                        session=session,
                        student=student,
                        defaults={
                            "status": status,
                            "marked_at": marked_at,
                            "is_manually_marked": True,
                            "marked_by": entry.faculty,
                            "notes": "Seeded HOD demo attendance",
                        },
                    )
                    attendance_count += 1

                current_date += timedelta(days=1)

        return session_count, attendance_count

    def _recalculate_reports(self, semester, students, subjects):
        report_count = 0
        for student in students:
            for subject in subjects:
                has_attendance = StudentAttendance.objects.filter(
                    student=student,
                    session__timetable_entry__subject=subject,
                    session__timetable_entry__semester=semester,
                    session__status="CLOSED",
                ).exists()
                if has_attendance:
                    AttendanceReport.update_for_student_subject(student, subject, semester)
                    report_count += 1
        return report_count

    def _attendance_status(self, student, entry, session_date):
        bucket = self.performance_buckets[(student.id - 1) % len(self.performance_buckets)]
        score = self._deterministic_score(student.register_number, entry.subject.code, session_date.isoformat(), str(entry.period_definition.period_number))

        if bucket == "GOOD":
            if score < 12:
                return "ABSENT"
            if score < 17:
                return "LATE"
            return "PRESENT"

        if bucket == "WARNING":
            if score < 32:
                return "ABSENT"
            if score < 38:
                return "LATE"
            return "PRESENT"

        if score < 48:
            return "ABSENT"
        if score < 52:
            return "LATE"
        return "PRESENT"

    def _deterministic_score(self, *parts):
        combined = "|".join(parts)
        total = 0
        for index, char in enumerate(combined, start=1):
            total = (total + (index * ord(char))) % 9973
        return total % 100

    def _aware_datetime(self, value_date, value_time):
        naive = datetime.combine(value_date, value_time)
        if timezone.is_naive(naive):
            return timezone.make_aware(naive, timezone.get_current_timezone())
        return naive

    def _slugify_code(self, value):
        return "".join(char for char in value.upper() if char.isalnum()) or "DEMO"