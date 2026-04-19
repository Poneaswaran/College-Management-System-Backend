"""GraphQL queries for profile management"""
import strawberry
from typing import List, Optional
from strawberry.types import Info
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Count, Q

from profile_management.models import StudentProfile, ParentProfile, AcademicYear, Semester
from .types import StudentProfileType, ParentProfileType, FacultyProfileType
from core.graphql.auth import require_auth
from timetable.graphql.types import AcademicYearType, SemesterType
from assignment.models import Assignment, AssignmentSubmission, AssignmentGrade
from timetable.models import TimetableEntry, Subject
from attendance.models import AttendanceSession, StudentAttendance
from profile_management.services import AcademicService, FacultyProfileService, StudentProfileService
from grades.models import CourseSectionAssignment, GradeBatch


# ==================================================
# DASHBOARD TYPES
# ==================================================

@strawberry.type
class AssignmentDueType:
    """Assignment due this week"""
    id: int
    title: str
    subject_name: str
    subject_code: str
    due_date: str
    max_marks: float
    status: str
    is_submitted: bool
    submission_date: Optional[str]


@strawberry.type
class RecentActivityType:
    """Recent activity item"""
    id: int
    activity_type: str  # SUBMISSION, GRADE
    title: str
    description: str
    timestamp: str
    icon: Optional[str]


@strawberry.type
class CourseProgressType:
    """Course progress information"""
    subject_code: str
    subject_name: str
    total_assignments: int
    completed_assignments: int
    percentage: float


@strawberry.type
class NextClassType:
    """Next class in timetable"""
    id: int
    subject_name: str
    subject_code: str
    faculty_name: str
    room_number: Optional[str]
    day_of_week: int
    day_name: str
    start_time: str
    end_time: str
    period_number: int


@strawberry.type
class StudentDashboardType:
    """Complete student dashboard data"""
    student_name: str
    register_number: str
    profile_photo_url: Optional[str]
    assignments_due_this_week: List[AssignmentDueType]
    total_pending_assignments: int
    total_overdue_assignments: int
    recent_activities: List[RecentActivityType]
    course_progress: List[CourseProgressType]
    overall_progress_percentage: float
    current_gpa: Optional[float]
    next_class: Optional[NextClassType]
    today_classes: List[NextClassType]


# ==================================================
# FACULTY DASHBOARD TYPES
# ==================================================

@strawberry.type
class FacultyTodayClassType:
    """A class scheduled for today for the faculty"""
    id: int
    subject_name: str
    subject_code: str
    section_name: str
    room_number: Optional[str]
    start_time: str
    end_time: str
    period_number: int


@strawberry.type
class FacultyAttendanceOverviewType:
    """Attendance overview for a subject taught by the faculty (this week)"""
    subject_name: str
    subject_code: str
    attendance_percentage: float


@strawberry.type
class FacultyRecentActivityType:
    """Recent activity item for faculty dashboard"""
    id: int
    activity_type: str  # GRADED_ASSIGNMENT, MARKED_ATTENDANCE
    title: str
    description: str
    timestamp: str


@strawberry.type
class FacultyDashboardType:
    """Complete faculty dashboard data"""
    faculty_name: str
    department_name: Optional[str]
    # Summary cards
    total_students: int
    active_courses: int
    pending_reviews: int
    # Today's classes
    today_classes: List[FacultyTodayClassType]
    today_class_count: int
    # Attendance overview (this week)
    attendance_overview: List[FacultyAttendanceOverviewType]
    # Recent activity
    recent_activities: List[FacultyRecentActivityType]

@strawberry.type
class FacultyCourseType:
    id: int
    subject_code: str
    subject_name: str
    section_name: str
    semester_name: str
    students_count: int
    assignments_count: int
    classes_completed: int
    classes_total: int
    avg_attendance: float
    schedule_summary: str
    room_number: Optional[str]

@strawberry.type
class FacultyCourseOverviewType:
    total_courses: int
    total_students: int
    avg_attendance: float
    total_assignments: int
    courses: List[FacultyCourseType]

@strawberry.type
class FacultyStudentType:
    id: int
    full_name: str
    email: Optional[str]
    register_number: str
    department_name: str
    semester_section: str
    attendance_percentage: float
    gpa: Optional[float]
    status: str

@strawberry.type
class FacultyStudentListType:
    students: List[FacultyStudentType]
    total_count: int


@strawberry.type
class FacultyWorkloadCourseAssignmentType:
    id: int
    subject_name: str
    subject_code: str
    section_name: str
    semester: int
    hours_per_week: float
    student_count: int
    department: str


@strawberry.type
class FacultyWorkloadItemType:
    id: int
    faculty_name: str
    employee_id: str
    designation: str
    department: str
    profile_photo: Optional[str]
    total_hours_per_week: float
    max_hours_per_week: float
    status: str
    attendance_avg: float
    pending_grading_count: int
    course_assignments: List[FacultyWorkloadCourseAssignmentType]


@strawberry.type
class FacultyWorkloadSummaryStatsType:
    total_faculty: int
    overloaded_count: int
    optimal_count: int
    underloaded_count: int
    avg_hours_per_week: float
    total_course_sections: int


@strawberry.type
class FacultyWorkloadDataType:
    department_name: str
    semester_label: str
    summary_stats: FacultyWorkloadSummaryStatsType
    faculty_workloads: List[FacultyWorkloadItemType]

# ==================================================
# COURSE ENROLLMENT TYPES
# ==================================================

@strawberry.type
class CourseScheduleType:
    """Class schedule for a course"""
    day_name: str
    start_time: str
    end_time: str


@strawberry.type
class EnrolledCourseType:
    """Detailed information about a student's enrolled course"""
    id: int
    subject_code: str
    subject_name: str
    subject_type: str
    credits: float
    faculty_name: str
    faculty_email: Optional[str]
    description: str
    course_progress: float
    grade: Optional[str]
    attendance_percentage: float
    completed_assignments: int
    total_assignments: int
    class_schedule: List[CourseScheduleType]


@strawberry.type
class CourseOverviewType:
    """Overview statistics for student's courses"""
    total_courses: int
    total_credits: float
    avg_progress: float
    avg_attendance: float


@strawberry.type
class ProfileQuery:

    # ==================================================
    # STUDENT PROFILE QUERIES
    # ==================================================
    
    @strawberry.field
    @require_auth
    def my_profile(self, info: Info, register_number: str) -> Optional[StudentProfileType]:
        """Get student's own profile"""
        return StudentProfileService.get_profile(register_number=register_number, user=info.context.request.user)
    
    @strawberry.field
    @require_auth
    def student_profile(self, info: Info, register_number: str) -> Optional[StudentProfileType]:
        """Get student profile by register number"""
        return StudentProfileService.get_profile(register_number=register_number, user=info.context.request.user)
    
    @strawberry.field
    @require_auth
    def student_profiles(
        self,
        info: Info,
        department_id: Optional[int] = None,
        course_id: Optional[int] = None,
        year: Optional[int] = None,
        academic_status: Optional[str] = None
    ) -> List[StudentProfileType]:
        """Get list of student profiles with filters"""
        return StudentProfileService.list_profiles(
            user=info.context.request.user,
            department_id=department_id,
            course_id=course_id,
            year=year,
            academic_status=academic_status,
        )
    
    # ==================================================
    # FACULTY PROFILE QUERIES
    # ==================================================

    @strawberry.field
    @require_auth
    def my_faculty_profile(self, info: Info) -> Optional[FacultyProfileType]:
        """Get current user's faculty profile"""
        return FacultyProfileService.get_my_profile(info.context.request.user)

    @strawberry.field
    @require_auth
    def faculty_workload(self, info: Info, semester_id: Optional[int] = None) -> Optional[FacultyWorkloadDataType]:
        """
        Faculty workload report for HOD/Admin screens.
        Returns one department scope with per-faculty workload and summary stats.
        """
        user = info.context.request.user

        if user.role.code not in ('HOD', 'ADMIN', 'PRINCIPAL', 'FACULTY'):
            raise ValueError("Access denied. Only faculty leadership roles can view workload.")

        # Resolve semester
        if semester_id:
            semester = Semester.objects.filter(id=semester_id).select_related('academic_year').first()
            if not semester:
                raise ValueError(f"Semester with id {semester_id} not found.")
        else:
            semester = Semester.objects.filter(is_current=True).select_related('academic_year').first()
            if not semester:
                raise ValueError("No current semester found.")

        # Resolve department scope
        department = None
        if user.role.code in ('HOD', 'FACULTY'):
            from profile_management.models import FacultyProfile
            fp = FacultyProfile.objects.select_related('department').filter(user=user).first()
            department = fp.department if fp and fp.department else user.department
        else:
            department = user.department

        if not department:
            from core.models import Department
            department = Department.objects.filter(faculties__is_active=True).distinct().first() or Department.objects.first()

        if not department:
            raise ValueError("No department found to compute workload.")

        from profile_management.models import FacultyProfile
        faculty_profiles = FacultyProfile.objects.filter(
            department=department,
            is_active=True
        ).select_related('user', 'department').order_by('first_name', 'id')

        total_hours_sum = 0.0
        total_course_sections = 0
        overloaded_count = 0
        optimal_count = 0
        underloaded_count = 0
        workload_items: List[FacultyWorkloadItemType] = []

        for faculty in faculty_profiles:
            assignments = CourseSectionAssignment.objects.filter(
                faculty=faculty,
                semester=semester,
                is_active=True,
                section__course__department=department,
            ).select_related('subject', 'section', 'semester', 'subject__department')

            course_items: List[FacultyWorkloadCourseAssignmentType] = []
            total_hours = 0.0

            for assignment in assignments:
                hours_per_week = float(TimetableEntry.objects.filter(
                    faculty=faculty.user,
                    subject=assignment.subject,
                    section=assignment.section,
                    semester=semester,
                    is_active=True,
                ).count())

                total_hours += hours_per_week
                course_items.append(FacultyWorkloadCourseAssignmentType(
                    id=assignment.id,
                    subject_name=assignment.subject.name,
                    subject_code=assignment.subject.code,
                    section_name=assignment.section.name,
                    semester=semester.number,
                    hours_per_week=round(hours_per_week, 1),
                    student_count=assignment.section.student_profiles.filter(is_active=True).count(),
                    department=assignment.subject.department.name if assignment.subject.department else department.name,
                ))

            max_hours = float(faculty.teaching_load or 0)
            if max_hours <= 0:
                max_hours = 18.0

            if total_hours > max_hours:
                workload_status = 'OVERLOADED'
                overloaded_count += 1
            elif total_hours < (0.7 * max_hours):
                workload_status = 'UNDERLOADED'
                underloaded_count += 1
            else:
                workload_status = 'OPTIMAL'
                optimal_count += 1

            sessions = AttendanceSession.objects.filter(
                timetable_entry__faculty=faculty.user,
                timetable_entry__semester=semester,
                timetable_entry__section__course__department=department,
                status='CLOSED',
            )
            total_records = StudentAttendance.objects.filter(session__in=sessions).count()
            present_records = StudentAttendance.objects.filter(
                session__in=sessions,
                status__in=['PRESENT', 'LATE'],
            ).count()
            attendance_avg = round((present_records / total_records * 100), 1) if total_records > 0 else 0.0

            pending_grading_count = 0
            for assignment in assignments:
                grade_batch = GradeBatch.objects.filter(course_section_assignment=assignment).first()
                if not grade_batch or grade_batch.status in ('DRAFT', 'REJECTED'):
                    pending_grading_count += 1

            workload_items.append(FacultyWorkloadItemType(
                id=faculty.id,
                faculty_name=faculty.full_name,
                employee_id=faculty.user.register_number or f"FAC{faculty.user.id:04d}",
                designation=faculty.designation,
                department=faculty.department.name if faculty.department else department.name,
                profile_photo=None,
                total_hours_per_week=round(total_hours, 1),
                max_hours_per_week=round(max_hours, 1),
                status=workload_status,
                attendance_avg=attendance_avg,
                pending_grading_count=pending_grading_count,
                course_assignments=course_items,
            ))

            total_hours_sum += total_hours
            total_course_sections += len(course_items)

        total_faculty = len(workload_items)
        avg_hours = round((total_hours_sum / total_faculty), 1) if total_faculty > 0 else 0.0

        summary = FacultyWorkloadSummaryStatsType(
            total_faculty=total_faculty,
            overloaded_count=overloaded_count,
            optimal_count=optimal_count,
            underloaded_count=underloaded_count,
            avg_hours_per_week=avg_hours,
            total_course_sections=total_course_sections,
        )

        semester_label = f"Semester {semester.number} — {semester.academic_year.year_code}"

        return FacultyWorkloadDataType(
            department_name=department.name,
            semester_label=semester_label,
            summary_stats=summary,
            faculty_workloads=workload_items,
        )

    @strawberry.field
    @require_auth
    def faculties(
        self,
        info: Info,
        department_id: Optional[int] = None,
        designation: Optional[str] = None
    ) -> List[FacultyProfileType]:
        """List faculty profiles with optional filters"""
        return FacultyProfileService.list_faculties(
            user=info.context.request.user,
            department_id=department_id,
            designation=designation,
        )

    # ==================================================
    # ACADEMIC YEAR QUERIES
    # ==================================================
    
    @strawberry.field
    def academic_years(self) -> List[AcademicYearType]:
        """Get all academic years"""
        return AcademicService.academic_years()
    
    @strawberry.field
    def current_academic_year(self) -> Optional[AcademicYearType]:
        """Get the current academic year"""
        return AcademicService.current_academic_year()
    
    @strawberry.field
    def academic_year(self, id: int) -> Optional[AcademicYearType]:
        """Get academic year by ID"""
        return AcademicService.academic_year_by_id(id)
    
    # ==================================================
    # SEMESTER QUERIES
    # ==================================================
    
    @strawberry.field
    def semesters(self, academic_year_id: Optional[int] = None) -> List[SemesterType]:
        """Get all semesters, optionally filtered by academic year"""
        return AcademicService.semesters(academic_year_id=academic_year_id)
    
    @strawberry.field
    def current_semester(self) -> Optional[SemesterType]:
        """Get the current semester"""
        return AcademicService.current_semester()
    
    @strawberry.field
    def semester(self, id: int) -> Optional[SemesterType]:
        """Get semester by ID"""
        return AcademicService.semester_by_id(id)

    # ==================================================
    # STUDENT DASHBOARD
    # ==================================================
    
    @strawberry.field
    @require_auth
    def student_dashboard(self, info: Info, register_number: str) -> Optional[StudentDashboardType]:
        """
        Get comprehensive dashboard data for a student
        Shows: profile info, assignments due, recent activity, course progress, GPA, next class
        """
        try:
            dashboard_data = StudentProfileService.get_student_dashboard(
                register_number=register_number,
                user=info.context.request.user,
            )
            return StudentDashboardType(
                student_name=dashboard_data["student_name"],
                register_number=dashboard_data["register_number"],
                profile_photo_url=dashboard_data["profile_photo_url"],
                assignments_due_this_week=[AssignmentDueType(**item) for item in dashboard_data["assignments_due_this_week"]],
                total_pending_assignments=dashboard_data["total_pending_assignments"],
                total_overdue_assignments=dashboard_data["total_overdue_assignments"],
                recent_activities=[RecentActivityType(**item) for item in dashboard_data["recent_activities"]],
                course_progress=[CourseProgressType(**item) for item in dashboard_data["course_progress"]],
                overall_progress_percentage=dashboard_data["overall_progress_percentage"],
                current_gpa=dashboard_data["current_gpa"],
                next_class=NextClassType(**dashboard_data["next_class"]) if dashboard_data["next_class"] else None,
                today_classes=[NextClassType(**item) for item in dashboard_data["today_classes"]],
            )
        except StudentProfile.DoesNotExist:
            return None
    
    @staticmethod
    def _get_time_ago(dt: datetime) -> str:
        """Convert datetime to human-readable time ago string"""
        now = timezone.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"

    # ==================================================
    # ENROLLED COURSES
    # ==================================================
    
    @strawberry.field
    @require_auth
    def my_courses(self, info: Info, register_number: str) -> List[EnrolledCourseType]:
        """
        Get all courses enrolled by a student with detailed information
        Includes progress, grades, attendance, and schedule
        """
        try:
            courses = StudentProfileService.my_courses(register_number=register_number, user=info.context.request.user)
            return [
                EnrolledCourseType(
                    id=item["id"],
                    subject_code=item["subject_code"],
                    subject_name=item["subject_name"],
                    subject_type=item["subject_type"],
                    credits=item["credits"],
                    faculty_name=item["faculty_name"],
                    faculty_email=item["faculty_email"],
                    description=item["description"],
                    course_progress=item["course_progress"],
                    grade=item["grade"],
                    attendance_percentage=item["attendance_percentage"],
                    completed_assignments=item["completed_assignments"],
                    total_assignments=item["total_assignments"],
                    class_schedule=[CourseScheduleType(**sched) for sched in item["class_schedule"]],
                )
                for item in courses
            ]
            
        except StudentProfile.DoesNotExist:
            return []
    
    @strawberry.field
    @require_auth
    def course_overview(self, info: Info, register_number: str) -> Optional[CourseOverviewType]:
        """
        Get overview statistics for student's enrolled courses
        Shows total courses, credits, average progress, and average attendance
        """
        try:
            overview = StudentProfileService.course_overview(register_number=register_number, user=info.context.request.user)
            if not overview:
                return None
            return CourseOverviewType(**overview)
            
        except StudentProfile.DoesNotExist:
            return None

    # ==================================================
    # FACULTY DASHBOARD
    # ==================================================

    @strawberry.field
    @require_auth
    def faculty_dashboard(self, info: Info) -> Optional[FacultyDashboardType]:
        """
        Get comprehensive dashboard data for a faculty member.
        Shows: summary cards, today's classes, attendance overview, recent activity.
        Uses the currently authenticated user.
        """
        try:
            payload = FacultyProfileService.get_dashboard(info.context.request.user)
            if not payload:
                return None
            return FacultyDashboardType(
                faculty_name=payload["faculty_name"],
                department_name=payload["department_name"],
                total_students=payload["total_students"],
                active_courses=payload["active_courses"],
                pending_reviews=payload["pending_reviews"],
                today_classes=[FacultyTodayClassType(**item) for item in payload["today_classes"]],
                today_class_count=payload["today_class_count"],
                attendance_overview=[FacultyAttendanceOverviewType(**item) for item in payload["attendance_overview"]],
                recent_activities=[FacultyRecentActivityType(**item) for item in payload["recent_activities"]],
            )
        except Exception:
            return None

    @strawberry.field
    @require_auth
    def faculty_courses(self, info: Info, semester_id: Optional[int] = None) -> Optional[FacultyCourseOverviewType]:
        """
        Get courses taught by faculty along with high-level statistics
        """
        payload = FacultyProfileService.faculty_courses(info.context.request.user, semester_id=semester_id)
        if not payload:
            return None
        return FacultyCourseOverviewType(
            total_courses=payload["total_courses"],
            total_students=payload["total_students"],
            avg_attendance=payload["avg_attendance"],
            total_assignments=payload["total_assignments"],
            courses=[FacultyCourseType(**course) for course in payload["courses"]],
        )

    @strawberry.field
    @require_auth
    def faculty_students(
        self,
        info: Info,
        search: Optional[str] = None,
        department_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Optional[FacultyStudentListType]:
        """
        Get list of students taught by the faculty, with optional filtering and pagination
        """
        payload = FacultyProfileService.faculty_students(
            info.context.request.user,
            search=search,
            department_id=department_id,
            page=page,
            page_size=page_size,
        )
        if not payload:
            return None
        return FacultyStudentListType(
            students=[FacultyStudentType(**item) for item in payload["students"]],
            total_count=payload["total_count"],
        )
