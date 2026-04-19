from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from assignment.models import Assignment, AssignmentGrade, AssignmentSubmission
from attendance.models import AttendanceSession, StudentAttendance
from configuration.services.config_service import ConfigService, FeatureFlagService
from core.models import Section
from profile_management.models import Semester, StudentProfile
from timetable.models import TimetableEntry

from .tenant_service import TenantService


class StudentProfileService:
    PROFILE_SUB_APP = "profile"

    @staticmethod
    def _get_allowed_fields(tenant_key=None):
        default_fields = [
            "first_name",
            "last_name",
            "phone",
            "date_of_birth",
            "gender",
            "address",
            "guardian_name",
            "guardian_relationship",
            "guardian_phone",
            "guardian_email",
        ]
        return ConfigService.get(
            key="student.allowed_edit_fields",
            default=default_fields,
            tenant_key=tenant_key,
            sub_app=StudentProfileService.PROFILE_SUB_APP,
        )

    @staticmethod
    def base_queryset(user=None):
        qs = StudentProfile.objects.select_related(
            "user",
            "user__role",
            "user__department",
            "department",
            "course",
            "section",
            "section__course",
        )
        return TenantService.apply_department_scope(qs, user=user, field_name="department")

    @staticmethod
    def get_profile(register_number, user=None):
        return StudentProfileService.base_queryset(user=user).filter(register_number=register_number).first()

    @staticmethod
    def list_profiles(user=None, department_id=None, course_id=None, year=None, academic_status=None):
        qs = StudentProfileService.base_queryset(user=user)

        if department_id:
            qs = qs.filter(department_id=department_id)
        if course_id:
            qs = qs.filter(course_id=course_id)
        if year:
            qs = qs.filter(year=year)
        if academic_status:
            qs = qs.filter(academic_status=academic_status)

        return qs

    @staticmethod
    def update_profile(register_number, data, actor=None):
        tenant_key = TenantService.get_tenant_key(actor)
        is_enabled = FeatureFlagService.is_enabled(
            "enable_student_profile_edit",
            default=True,
            tenant_key=tenant_key,
            sub_app=StudentProfileService.PROFILE_SUB_APP,
        )
        if not is_enabled:
            raise Exception("Student profile editing is disabled")

        profile = StudentProfileService.base_queryset(user=actor).get(register_number=register_number)
        allowed_fields = set(StudentProfileService._get_allowed_fields(tenant_key=tenant_key))

        for field_name, field_value in data.items():
            if field_name not in allowed_fields:
                continue
            if field_value is None:
                continue
            if isinstance(field_value, str) and not field_value.strip():
                continue
            setattr(profile, field_name, field_value)

        profile.save()
        return profile

    @staticmethod
    def update_profile_with_photo(register_number, data, actor=None, profile_picture=None, profile_picture_base64=None):
        tenant_key = TenantService.get_tenant_key(actor)
        photo_enabled = FeatureFlagService.is_enabled(
            "enable_student_profile_photo_upload",
            default=True,
            tenant_key=tenant_key,
            sub_app=StudentProfileService.PROFILE_SUB_APP,
        )
        if not photo_enabled and (profile_picture is not None or profile_picture_base64):
            raise Exception("Profile photo upload is disabled")

        profile = StudentProfileService.update_profile(register_number, data, actor=actor)

        if profile_picture is not None:
            if profile.profile_photo:
                old_path = profile.profile_photo.name
                if default_storage.exists(old_path):
                    default_storage.delete(old_path)

            file_name = f"student_profiles/{register_number}_{profile_picture.name}"
            profile.profile_photo.save(file_name, ContentFile(profile_picture.read()), save=False)
        elif profile_picture_base64:
            import base64

            if profile.profile_photo:
                old_path = profile.profile_photo.name
                if default_storage.exists(old_path):
                    default_storage.delete(old_path)

            image_format, image_string = profile_picture_base64.split(";base64,")
            ext = image_format.split("/")[-1]
            timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"student_profiles/{register_number}_{timestamp}.{ext}"
            image_data = base64.b64decode(image_string)
            profile.profile_photo.save(file_name, ContentFile(image_data), save=False)

        profile.save()
        return profile

    @staticmethod
    def admin_update_profile(register_number, data, actor=None):
        profile = StudentProfileService.base_queryset(user=actor).get(register_number=register_number)

        if data.get("roll_number") is not None:
            profile.roll_number = data["roll_number"]
        if data.get("year") is not None:
            profile.year = data["year"]
        if data.get("semester") is not None:
            profile.semester = data["semester"]
        if data.get("section_id") is not None:
            profile.section = Section.objects.get(id=data["section_id"])
        if data.get("admission_date") is not None:
            profile.admission_date = data["admission_date"]
        if data.get("academic_status") is not None:
            profile.academic_status = data["academic_status"]
        if data.get("aadhar_number") is not None:
            profile.aadhar_number = data["aadhar_number"]
        if data.get("id_proof_type") is not None:
            profile.id_proof_type = data["id_proof_type"]
        if data.get("id_proof_number") is not None:
            profile.id_proof_number = data["id_proof_number"]

        profile.save()
        return profile

    @staticmethod
    def get_student_dashboard(register_number, user=None):
        student_profile = StudentProfileService.base_queryset(user=user).get(register_number=register_number)
        now = timezone.now()
        week_start = now
        week_end = now + timedelta(days=7)

        assignments_this_week = Assignment.objects.filter(
            section=student_profile.section,
            status="PUBLISHED",
            due_date__gte=week_start,
            due_date__lte=week_end,
        ).select_related("subject").order_by("due_date")

        assignments_due = []
        for assignment in assignments_this_week:
            submission = AssignmentSubmission.objects.filter(
                assignment=assignment,
                student=student_profile,
            ).first()
            assignments_due.append(
                {
                    "id": assignment.id,
                    "title": assignment.title,
                    "subject_name": assignment.subject.name,
                    "subject_code": assignment.subject.code,
                    "due_date": assignment.due_date.isoformat(),
                    "max_marks": float(assignment.max_marks),
                    "status": assignment.status,
                    "is_submitted": submission is not None,
                    "submission_date": submission.submitted_at.isoformat() if submission else None,
                }
            )

        total_pending = Assignment.objects.filter(
            section=student_profile.section,
            status="PUBLISHED",
            due_date__gte=now,
        ).exclude(submissions__student=student_profile).count()

        total_overdue = Assignment.objects.filter(
            section=student_profile.section,
            status="PUBLISHED",
            due_date__lt=now,
        ).exclude(submissions__student=student_profile).count()

        recent_activities = []
        recent_submissions = AssignmentSubmission.objects.filter(
            student=student_profile
        ).select_related("assignment", "assignment__subject").order_by("-submitted_at")[:10]

        for submission in recent_submissions:
            recent_activities.append(
                {
                    "id": submission.id,
                    "activity_type": "SUBMISSION",
                    "title": f"Submitted {submission.assignment.subject.name} Assignment",
                    "description": submission.assignment.title,
                    "timestamp": StudentProfileService.get_time_ago(submission.submitted_at),
                    "icon": "document",
                }
            )

        recent_grades = AssignmentGrade.objects.filter(
            submission__student=student_profile
        ).select_related("submission__assignment", "submission__assignment__subject").order_by("-graded_at")[:10]

        for grade in recent_grades:
            recent_activities.append(
                {
                    "id": grade.id,
                    "activity_type": "GRADE",
                    "title": f"Received grade for {grade.submission.assignment.subject.name}",
                    "description": (
                        f"{float(grade.marks_obtained)}/"
                        f"{float(grade.submission.assignment.max_marks)} - {grade.grade_letter}"
                    ),
                    "timestamp": StudentProfileService.get_time_ago(grade.graded_at),
                    "icon": "star",
                }
            )

        recent_activities = recent_activities[:10]

        assignments_by_subject = Assignment.objects.filter(
            section=student_profile.section,
            status__in=["PUBLISHED", "CLOSED", "GRADED"],
        ).values("subject__code", "subject__name").annotate(
            total=Count("id"),
            completed=Count("submissions", filter=Q(submissions__student=student_profile)),
        )

        course_progress = []
        total_completed = 0
        total_assignments = 0
        for subject_data in assignments_by_subject:
            total = subject_data["total"]
            completed = subject_data["completed"]
            total_completed += completed
            total_assignments += total
            percentage = (completed / total * 100) if total > 0 else 0
            course_progress.append(
                {
                    "subject_code": subject_data["subject__code"],
                    "subject_name": subject_data["subject__name"],
                    "total_assignments": total,
                    "completed_assignments": completed,
                    "percentage": round(percentage, 1),
                }
            )

        overall_progress = (total_completed / total_assignments * 100) if total_assignments > 0 else 0

        if student_profile.current_gpa is not None:
            current_gpa = float(student_profile.current_gpa)
        else:
            grades = AssignmentGrade.objects.filter(submission__student=student_profile).select_related(
                "submission__assignment"
            )
            if grades.exists():
                total_weighted_score = 0
                total_weightage = 0
                for grade in grades:
                    percentage = float(grade.percentage)
                    weightage = float(grade.submission.assignment.weightage)
                    total_weighted_score += percentage * weightage
                    total_weightage += weightage
                current_gpa = round((total_weighted_score / total_weightage / 100) * 4.0, 2) if total_weightage > 0 else None
            else:
                current_gpa = None

        current_day = now.isoweekday()
        current_time = now.time()
        today_entries = TimetableEntry.objects.filter(
            section=student_profile.section,
            is_active=True,
            period_definition__day_of_week=current_day,
        ).select_related("subject", "faculty", "room", "period_definition").order_by("period_definition__start_time")

        day_names = {
            1: "Monday",
            2: "Tuesday",
            3: "Wednesday",
            4: "Thursday",
            5: "Friday",
            6: "Saturday",
            7: "Sunday",
        }

        today_classes = []
        next_class = None
        for entry in today_entries:
            class_info = {
                "id": entry.id,
                "subject_name": entry.subject.name,
                "subject_code": entry.subject.code,
                "faculty_name": (entry.faculty.email or entry.faculty.register_number) if entry.faculty else "TBA",
                "room_number": entry.room.room_number if entry.room else None,
                "day_of_week": entry.period_definition.day_of_week,
                "day_name": day_names.get(entry.period_definition.day_of_week, "Unknown"),
                "start_time": entry.period_definition.start_time.strftime("%I:%M %p"),
                "end_time": entry.period_definition.end_time.strftime("%I:%M %p"),
                "period_number": entry.period_definition.period_number,
            }
            today_classes.append(class_info)
            if next_class is None and entry.period_definition.start_time > current_time:
                next_class = class_info

        if next_class is None:
            tomorrow = current_day + 1 if current_day < 7 else 1
            tomorrow_entry = TimetableEntry.objects.filter(
                section=student_profile.section,
                is_active=True,
                period_definition__day_of_week=tomorrow,
            ).select_related("subject", "faculty", "room", "period_definition").order_by("period_definition__start_time").first()
            if tomorrow_entry:
                next_class = {
                    "id": tomorrow_entry.id,
                    "subject_name": tomorrow_entry.subject.name,
                    "subject_code": tomorrow_entry.subject.code,
                    "faculty_name": (
                        tomorrow_entry.faculty.email or tomorrow_entry.faculty.register_number
                    ) if tomorrow_entry.faculty else "TBA",
                    "room_number": tomorrow_entry.room.room_number if tomorrow_entry.room else None,
                    "day_of_week": tomorrow_entry.period_definition.day_of_week,
                    "day_name": day_names.get(tomorrow_entry.period_definition.day_of_week, "Unknown"),
                    "start_time": tomorrow_entry.period_definition.start_time.strftime("%I:%M %p"),
                    "end_time": tomorrow_entry.period_definition.end_time.strftime("%I:%M %p"),
                    "period_number": tomorrow_entry.period_definition.period_number,
                }

        return {
            "student_name": student_profile.full_name,
            "register_number": student_profile.register_number,
            "profile_photo_url": f"/media/{student_profile.profile_photo}" if student_profile.profile_photo else None,
            "assignments_due_this_week": assignments_due,
            "total_pending_assignments": total_pending,
            "total_overdue_assignments": total_overdue,
            "recent_activities": recent_activities,
            "course_progress": course_progress,
            "overall_progress_percentage": round(overall_progress, 1),
            "current_gpa": current_gpa,
            "next_class": next_class,
            "today_classes": today_classes,
        }

    @staticmethod
    def my_courses(register_number, user=None):
        student_profile = StudentProfileService.base_queryset(user=user).select_related("section", "course").get(
            register_number=register_number
        )
        current_semester = Semester.objects.filter(is_current=True).first()
        if not current_semester or not student_profile.section:
            return []

        timetable_entries = TimetableEntry.objects.filter(
            section=student_profile.section,
            semester=current_semester,
            is_active=True,
        ).select_related(
            "subject",
            "subject__department",
            "faculty",
            "room",
            "period_definition",
        ).order_by("subject__id")

        seen_subjects = set()
        unique_entries = []
        for entry in timetable_entries:
            if entry.subject.id not in seen_subjects:
                seen_subjects.add(entry.subject.id)
                unique_entries.append(entry)

        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}
        enrolled_courses = []
        for entry in unique_entries:
            subject = entry.subject
            schedule_entries = TimetableEntry.objects.filter(
                section=student_profile.section,
                subject=subject,
                semester=current_semester,
                is_active=True,
            ).select_related("period_definition")

            class_schedule = [
                {
                    "day_name": day_names.get(s.period_definition.day_of_week, "Unknown"),
                    "start_time": s.period_definition.start_time.strftime("%I:%M %p"),
                    "end_time": s.period_definition.end_time.strftime("%I:%M %p"),
                }
                for s in schedule_entries
            ]

            subject_assignments = Assignment.objects.filter(
                subject=subject,
                section=student_profile.section,
                status__in=["PUBLISHED", "CLOSED", "GRADED"],
            )
            total_assignments = subject_assignments.count()
            completed_assignments = AssignmentSubmission.objects.filter(
                assignment__in=subject_assignments,
                student=student_profile,
            ).count()
            course_progress = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0

            grades = AssignmentGrade.objects.filter(
                submission__assignment__subject=subject,
                submission__student=student_profile,
            )
            grade_letter = None
            if grades.exists():
                avg_percentage = grades.aggregate(avg=Avg("marks_obtained"))["avg"]
                if avg_percentage is not None:
                    if avg_percentage >= 90:
                        grade_letter = "A+"
                    elif avg_percentage >= 85:
                        grade_letter = "A"
                    elif avg_percentage >= 80:
                        grade_letter = "A-"
                    elif avg_percentage >= 75:
                        grade_letter = "B+"
                    elif avg_percentage >= 70:
                        grade_letter = "B"
                    elif avg_percentage >= 65:
                        grade_letter = "B-"
                    elif avg_percentage >= 60:
                        grade_letter = "C+"
                    elif avg_percentage >= 55:
                        grade_letter = "C"
                    elif avg_percentage >= 50:
                        grade_letter = "D"
                    else:
                        grade_letter = "F"

            attendance_sessions = AttendanceSession.objects.filter(
                timetable_entry__subject=subject,
                timetable_entry__section=student_profile.section,
                status__in=["CLOSED", "BLOCKED", "CANCELLED"],
            )
            total_sessions = attendance_sessions.count()
            attended_sessions = StudentAttendance.objects.filter(
                student=student_profile,
                session__in=attendance_sessions,
                status="PRESENT",
            ).count()
            attendance_percentage = (attended_sessions / total_sessions * 100) if total_sessions > 0 else 0

            enrolled_courses.append(
                {
                    "id": subject.id,
                    "subject_code": subject.code,
                    "subject_name": subject.name,
                    "subject_type": subject.subject_type,
                    "credits": float(subject.credits),
                    "faculty_name": (entry.faculty.email or entry.faculty.register_number) if entry.faculty else "TBA",
                    "faculty_email": entry.faculty.email if entry.faculty else None,
                    "description": subject.description or f"Advanced topics in {subject.name.lower()}",
                    "course_progress": round(course_progress, 1),
                    "grade": grade_letter,
                    "attendance_percentage": round(attendance_percentage, 1),
                    "completed_assignments": completed_assignments,
                    "total_assignments": total_assignments,
                    "class_schedule": class_schedule,
                }
            )

        return enrolled_courses

    @staticmethod
    def course_overview(register_number, user=None):
        student_profile = StudentProfileService.base_queryset(user=user).select_related("section").get(
            register_number=register_number
        )

        current_semester = Semester.objects.filter(is_current=True).first()
        if not current_semester or not student_profile.section:
            return None

        subjects = TimetableEntry.objects.filter(
            section=student_profile.section,
            semester=current_semester,
            is_active=True,
        ).values("subject").distinct().count()

        total_credits = TimetableEntry.objects.filter(
            section=student_profile.section,
            semester=current_semester,
            is_active=True,
        ).values("subject").distinct().aggregate(total=Sum("subject__credits"))["total"] or 0

        all_assignments = Assignment.objects.filter(
            section=student_profile.section,
            status__in=["PUBLISHED", "CLOSED", "GRADED"],
        )
        total_assignments_count = all_assignments.count()
        completed_count = AssignmentSubmission.objects.filter(
            assignment__in=all_assignments,
            student=student_profile,
        ).count()
        avg_progress = (completed_count / total_assignments_count * 100) if total_assignments_count > 0 else 0

        all_sessions = AttendanceSession.objects.filter(
            timetable_entry__section=student_profile.section,
            timetable_entry__semester=current_semester,
            status__in=["CLOSED", "BLOCKED", "CANCELLED"],
        )
        total_sessions_count = all_sessions.count()
        attended_count = StudentAttendance.objects.filter(
            student=student_profile,
            session__in=all_sessions,
            status="PRESENT",
        ).count()
        avg_attendance = (attended_count / total_sessions_count * 100) if total_sessions_count > 0 else 0

        return {
            "total_courses": subjects,
            "total_credits": float(total_credits),
            "avg_progress": round(avg_progress, 1),
            "avg_attendance": round(avg_attendance, 1),
        }

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
