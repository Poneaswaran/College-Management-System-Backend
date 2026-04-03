from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from assignment.models import Assignment, AssignmentGrade, AssignmentSubmission
from attendance.models import AttendanceSession, StudentAttendance
from configuration.services.config_service import FeatureFlagService
from profile_management.models import FacultyProfile, Semester, StudentProfile
from timetable.models import Subject, TimetableEntry

from .tenant_service import TenantService


class FacultyProfileService:
    PROFILE_SUB_APP = "profile"

    @staticmethod
    def get_my_profile(user):
        try:
            return FacultyProfile.objects.select_related("user", "department").get(user=user)
        except FacultyProfile.DoesNotExist:
            return None

    @staticmethod
    def list_faculties(user=None, department_id=None, designation=None):
        qs = FacultyProfile.objects.filter(is_active=True).select_related("user", "department")
        qs = TenantService.apply_department_scope(qs, user=user, field_name="department")
        if department_id:
            qs = qs.filter(department_id=department_id)
        if designation:
            qs = qs.filter(designation__icontains=designation)
        return qs

    @staticmethod
    def update_profile(data, request_user, user_id=None):
        is_admin = getattr(request_user, "role", None) and request_user.role.code in ["HOD", "ADMIN"]

        enabled = FeatureFlagService.is_enabled(
            "enable_faculty_profile_edit",
            default=True,
            tenant_key=TenantService.get_tenant_key(request_user),
            sub_app=FacultyProfileService.PROFILE_SUB_APP,
        )
        if not enabled:
            raise Exception("Faculty profile editing is disabled")

        target_user = request_user
        if user_id and is_admin:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            target_user = User.objects.get(id=user_id)
        elif user_id and user_id != request_user.id:
            raise Exception("Not authorized to edit this profile")

        profile = FacultyProfile.objects.get(user=target_user)

        editable_fields = ["designation", "qualifications", "specialization", "office_hours"]
        admin_only_fields = ["teaching_load", "department_id", "is_active"]

        for field_name in editable_fields:
            if data.get(field_name) is not None:
                setattr(profile, field_name, data[field_name])

        if is_admin:
            for field_name in admin_only_fields:
                if data.get(field_name) is not None:
                    setattr(profile, field_name, data[field_name])

        profile.save()
        return profile

    @staticmethod
    def get_dashboard(user):
        if user.role.code not in ("FACULTY", "HOD", "ADMIN"):
            return None

        try:
            faculty_profile = FacultyProfile.objects.select_related("user", "department").get(user=user)
            faculty_name = faculty_profile.full_name or user.email or "Faculty"
            department_name = faculty_profile.department.name if faculty_profile.department else None
        except FacultyProfile.DoesNotExist:
            faculty_name = user.email or "Faculty"
            department_name = user.department.name if user.department else None

        now = timezone.now()
        today = now.date()
        current_day = now.isoweekday()
        current_semester = Semester.objects.filter(is_current=True).first()

        faculty_entries_qs = TimetableEntry.objects.filter(faculty=user, is_active=True)
        if current_semester:
            faculty_entries_qs = faculty_entries_qs.filter(semester=current_semester)

        faculty_entries = faculty_entries_qs.select_related(
            "subject", "section", "section__course", "room", "period_definition", "semester"
        )

        section_ids = faculty_entries.values_list("section_id", flat=True).distinct()
        total_students = StudentProfile.objects.filter(section_id__in=section_ids, academic_status="ACTIVE").count()
        active_courses = faculty_entries.values("subject_id").distinct().count()

        faculty_assignments = Assignment.objects.filter(created_by=user)
        if current_semester:
            faculty_assignments = faculty_assignments.filter(semester=current_semester)
        pending_reviews = AssignmentSubmission.objects.filter(
            assignment__in=faculty_assignments,
            status__in=["SUBMITTED", "RESUBMITTED"],
        ).count()

        today_entries = faculty_entries.filter(period_definition__day_of_week=current_day).order_by(
            "period_definition__start_time"
        )
        today_classes = [
            {
                "id": entry.id,
                "subject_name": entry.subject.name,
                "subject_code": entry.subject.code,
                "section_name": str(entry.section),
                "room_number": entry.room.room_number if entry.room else None,
                "start_time": entry.period_definition.start_time.strftime("%I:%M %p"),
                "end_time": entry.period_definition.end_time.strftime("%I:%M %p"),
                "period_number": entry.period_definition.period_number,
            }
            for entry in today_entries
        ]

        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        taught_subject_ids = faculty_entries.values_list("subject_id", flat=True).distinct()
        taught_subjects = Subject.objects.filter(id__in=taught_subject_ids)

        attendance_overview = []
        for subject in taught_subjects:
            sessions = AttendanceSession.objects.filter(
                timetable_entry__faculty=user,
                timetable_entry__subject=subject,
                date__gte=week_start,
                date__lte=week_end,
                status__in=["CLOSED", "BLOCKED"],
            )
            total_records = StudentAttendance.objects.filter(session__in=sessions).count()
            present_records = StudentAttendance.objects.filter(
                session__in=sessions,
                status__in=["PRESENT", "LATE"],
            ).count()
            pct = (present_records / total_records * 100) if total_records > 0 else 0.0
            attendance_overview.append(
                {
                    "subject_name": subject.name,
                    "subject_code": subject.code,
                    "attendance_percentage": round(pct, 1),
                }
            )

        recent_activities = []
        recent_grades = AssignmentGrade.objects.filter(graded_by=user).select_related(
            "submission__assignment", "submission__assignment__subject", "submission__student"
        ).order_by("-graded_at")[:10]

        for grade in recent_grades:
            sub_count = AssignmentSubmission.objects.filter(
                assignment=grade.submission.assignment,
                grade__graded_by=user,
            ).count()
            recent_activities.append(
                {
                    "id": grade.id,
                    "activity_type": "GRADED_ASSIGNMENT",
                    "title": f"Graded Assignment - {grade.submission.assignment.subject.name}",
                    "description": f"Graded {sub_count} submissions",
                    "timestamp": StudentProfileServiceTime.get_time_ago(grade.graded_at),
                }
            )

        recent_sessions = AttendanceSession.objects.filter(
            timetable_entry__faculty=user,
            status__in=["CLOSED", "BLOCKED"],
            closed_at__isnull=False,
        ).select_related("timetable_entry__subject").order_by("-closed_at")[:10]

        for session in recent_sessions:
            recent_activities.append(
                {
                    "id": session.id,
                    "activity_type": "MARKED_ATTENDANCE",
                    "title": f"Marked Attendance - {session.timetable_entry.subject.name}",
                    "description": f"{session.present_count}/{session.total_students} present",
                    "timestamp": StudentProfileServiceTime.get_time_ago(session.closed_at),
                }
            )

        return {
            "faculty_name": faculty_name,
            "department_name": department_name,
            "total_students": total_students,
            "active_courses": active_courses,
            "pending_reviews": pending_reviews,
            "today_classes": today_classes,
            "today_class_count": len(today_classes),
            "attendance_overview": attendance_overview,
            "recent_activities": recent_activities[:10],
        }

    @staticmethod
    def faculty_courses(user, semester_id=None):
        if user.role.code not in ("FACULTY", "HOD", "ADMIN"):
            return None

        faculty_entries_qs = TimetableEntry.objects.filter(faculty=user, is_active=True).select_related(
            "subject", "section", "semester", "room", "period_definition"
        )

        if semester_id:
            faculty_entries_qs = faculty_entries_qs.filter(semester_id=semester_id)
        else:
            current_semester = Semester.objects.filter(is_current=True).first()
            if current_semester:
                faculty_entries_qs = faculty_entries_qs.filter(semester=current_semester)

        course_map = {}
        for entry in faculty_entries_qs:
            key = (entry.subject.id, entry.section.id)
            if key not in course_map:
                course_map[key] = {
                    "subject": entry.subject,
                    "section": entry.section,
                    "semester": entry.semester,
                    "entries": [],
                }
            course_map[key]["entries"].append(entry)

        total_students_set = set()
        total_assignments = 0
        courses_list = []
        global_attendance_present = 0
        global_attendance_total = 0
        day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

        for _, data in course_map.items():
            subject = data["subject"]
            section = data["section"]
            semester = data["semester"]
            entries = data["entries"]

            students_qs = StudentProfile.objects.filter(section=section, academic_status="ACTIVE")
            students_count = students_qs.count()
            total_students_set.update(students_qs.values_list("id", flat=True))

            course_assignments = Assignment.objects.filter(
                subject=subject,
                section=section,
                created_by=user,
                semester=semester,
            ).count()
            total_assignments += course_assignments

            sessions = AttendanceSession.objects.filter(
                timetable_entry__faculty=user,
                timetable_entry__subject=subject,
                timetable_entry__section=section,
                timetable_entry__semester=semester,
                status__in=["CLOSED", "BLOCKED"],
            )
            classes_completed = sessions.filter(status="CLOSED").count()
            classes_total = len(entries) * 16

            attendance_total = StudentAttendance.objects.filter(session__in=sessions).count()
            attendance_present = StudentAttendance.objects.filter(
                session__in=sessions,
                status__in=["PRESENT", "LATE"],
            ).count()
            avg_attendance = (attendance_present / attendance_total) * 100 if attendance_total > 0 else 0.0

            global_attendance_present += attendance_present
            global_attendance_total += attendance_total

            time_groups = {}
            for e in entries:
                t = e.period_definition.start_time.strftime("%I:%M %p")
                day = day_names.get(e.period_definition.day_of_week, "")
                time_groups.setdefault(t, [])
                if day not in time_groups[t]:
                    time_groups[t].append(day)

            schedule_summary = " | ".join([f"{', '.join(days)} - {t}" for t, days in time_groups.items()])

            room_number = None
            for e in entries:
                if e.room:
                    room_number = e.room.room_number
                    break

            courses_list.append(
                {
                    "id": subject.id,
                    "subject_code": subject.code,
                    "subject_name": subject.name,
                    "section_name": f"Section {section.name}",
                    "semester_name": f"{semester.academic_year.year_code} Sem {semester.get_number_display()}",
                    "students_count": students_count,
                    "assignments_count": course_assignments,
                    "classes_completed": classes_completed,
                    "classes_total": max(classes_total, classes_completed),
                    "avg_attendance": round(avg_attendance, 1),
                    "schedule_summary": schedule_summary,
                    "room_number": room_number,
                }
            )

        global_avg_attendance = round((global_attendance_present / global_attendance_total) * 100, 1) if global_attendance_total > 0 else 0.0

        return {
            "total_courses": len(courses_list),
            "total_students": len(total_students_set),
            "avg_attendance": global_avg_attendance,
            "total_assignments": total_assignments,
            "courses": courses_list,
        }

    @staticmethod
    def faculty_students(user, search=None, department_id=None, page=1, page_size=10):
        if user.role.code not in ("FACULTY", "HOD", "ADMIN"):
            return None

        current_semester = Semester.objects.filter(is_current=True).first()
        if not current_semester:
            return {"students": [], "total_count": 0}

        faculty_sections = TimetableEntry.objects.filter(
            faculty=user,
            is_active=True,
            semester=current_semester,
        ).values_list("section_id", flat=True).distinct()

        qs = StudentProfile.objects.filter(section_id__in=faculty_sections).select_related(
            "user", "department", "section", "course"
        ).distinct()

        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(register_number__icontains=search)
                | Q(user__email__icontains=search)
            )
        if department_id:
            qs = qs.filter(department_id=department_id)

        total_count = qs.count()
        qs = qs.order_by("first_name", "last_name")
        offset = (page - 1) * page_size
        students_page = qs[offset : offset + page_size]

        students_list = []
        for student in students_page:
            sessions = AttendanceSession.objects.filter(
                timetable_entry__section=student.section,
                timetable_entry__semester=current_semester,
                status__in=["CLOSED", "BLOCKED"],
            )
            total_classes = sessions.filter(status="CLOSED").count()
            attendance_present = StudentAttendance.objects.filter(
                student=student,
                session__in=sessions,
                status__in=["PRESENT", "LATE"],
            ).count()
            att_pct = round((attendance_present / total_classes) * 100, 1) if total_classes > 0 else 0.0
            section_name = student.section.name if student.section else "?"

            students_list.append(
                {
                    "id": student.id,
                    "full_name": student.full_name,
                    "email": student.user.email if student.user else None,
                    "register_number": student.register_number,
                    "department_name": student.department.name if student.department else "Unknown",
                    "semester_section": f"Sem {student.semester} - {section_name}",
                    "attendance_percentage": att_pct,
                    "gpa": float(student.current_gpa) if student.current_gpa is not None else 0.0,
                    "status": student.academic_status,
                }
            )

        return {"students": students_list, "total_count": total_count}


class StudentProfileServiceTime:
    @staticmethod
    def get_time_ago(dt):
        now = timezone.now()
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        if seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        if seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
