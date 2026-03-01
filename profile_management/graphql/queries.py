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
        return (
            StudentProfile.objects
            .select_related(
                "user",
                "user__role",
                "user__department",
                "department",
                "course",
                "section",
                "section__course"
            )
            .filter(register_number=register_number)
            .first()
        )
    
    @strawberry.field
    @require_auth
    def student_profile(self, info: Info, register_number: str) -> Optional[StudentProfileType]:
        """Get student profile by register number"""
        return (
            StudentProfile.objects
            .select_related(
                "user",
                "user__role",
                "user__department",
                "department",
                "course",
                "section",
                "section__course"
            )
            .filter(register_number=register_number)
            .first()
        )
    
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
        qs = StudentProfile.objects.select_related(
            "user",
            "user__role",
            "user__department",
            "department",
            "course",
            "section"
        )
        
        if department_id:
            qs = qs.filter(department_id=department_id)
        if course_id:
            qs = qs.filter(course_id=course_id)
        if year:
            qs = qs.filter(year=year)
        if academic_status:
            qs = qs.filter(academic_status=academic_status)
            
        return qs
    
    # ==================================================
    # FACULTY PROFILE QUERIES
    # ==================================================

    @strawberry.field
    @require_auth
    def my_faculty_profile(self, info: Info) -> Optional[FacultyProfileType]:
        """Get current user's faculty profile"""
        user = info.context.request.user
        try:
            from profile_management.models import FacultyProfile
            return FacultyProfile.objects.select_related('user', 'department').get(user=user)
        except Exception:
            return None

    @strawberry.field
    @require_auth
    def faculties(
        self,
        info: Info,
        department_id: Optional[int] = None,
        designation: Optional[str] = None
    ) -> List[FacultyProfileType]:
        """List faculty profiles with optional filters"""
        from profile_management.models import FacultyProfile
        qs = FacultyProfile.objects.filter(is_active=True).select_related('user', 'department')
        if department_id:
            qs = qs.filter(department_id=department_id)
        if designation:
            qs = qs.filter(designation__icontains=designation)
        return qs

    # ==================================================
    # ACADEMIC YEAR QUERIES
    # ==================================================
    
    @strawberry.field
    def academic_years(self) -> List[AcademicYearType]:
        """Get all academic years"""
        return AcademicYear.objects.all()
    
    @strawberry.field
    def current_academic_year(self) -> Optional[AcademicYearType]:
        """Get the current academic year"""
        return AcademicYear.objects.filter(is_current=True).first()
    
    @strawberry.field
    def academic_year(self, id: int) -> Optional[AcademicYearType]:
        """Get academic year by ID"""
        return AcademicYear.objects.filter(id=id).first()
    
    # ==================================================
    # SEMESTER QUERIES
    # ==================================================
    
    @strawberry.field
    def semesters(self, academic_year_id: Optional[int] = None) -> List[SemesterType]:
        """Get all semesters, optionally filtered by academic year"""
        qs = Semester.objects.select_related('academic_year')
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        return qs
    
    @strawberry.field
    def current_semester(self) -> Optional[SemesterType]:
        """Get the current semester"""
        return Semester.objects.select_related('academic_year').filter(is_current=True).first()
    
    @strawberry.field
    def semester(self, id: int) -> Optional[SemesterType]:
        """Get semester by ID"""
        return Semester.objects.select_related('academic_year').filter(id=id).first()

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
            # Get student profile
            student_profile = StudentProfile.objects.select_related(
                'user', 'section', 'course', 'department'
            ).get(register_number=register_number)
            
            # Get current date and week range
            now = timezone.now()
            week_start = now
            week_end = now + timedelta(days=7)
            
            # ==================================================
            # ASSIGNMENTS DUE THIS WEEK
            # ==================================================
            assignments_this_week = Assignment.objects.filter(
                section=student_profile.section,
                status='PUBLISHED',
                due_date__gte=week_start,
                due_date__lte=week_end
            ).select_related('subject').order_by('due_date')
            
            assignments_due = []
            for assignment in assignments_this_week:
                # Check if student has submitted
                submission = AssignmentSubmission.objects.filter(
                    assignment=assignment,
                    student=student_profile
                ).first()
                
                assignments_due.append(AssignmentDueType(
                    id=assignment.id,
                    title=assignment.title,
                    subject_name=assignment.subject.name,
                    subject_code=assignment.subject.code,
                    due_date=assignment.due_date.isoformat(),
                    max_marks=float(assignment.max_marks),
                    status=assignment.status,
                    is_submitted=submission is not None,
                    submission_date=submission.submitted_at.isoformat() if submission else None
                ))
            
            # Count pending and overdue assignments
            total_pending = Assignment.objects.filter(
                section=student_profile.section,
                status='PUBLISHED',
                due_date__gte=now
            ).exclude(
                submissions__student=student_profile
            ).count()
            
            total_overdue = Assignment.objects.filter(
                section=student_profile.section,
                status='PUBLISHED',
                due_date__lt=now
            ).exclude(
                submissions__student=student_profile
            ).count()
            
            # ==================================================
            # RECENT ACTIVITY
            # ==================================================
            recent_activities = []
            
            # Get recent submissions (last 10)
            recent_submissions = AssignmentSubmission.objects.filter(
                student=student_profile
            ).select_related('assignment', 'assignment__subject').order_by('-submitted_at')[:10]
            
            for submission in recent_submissions:
                time_ago = ProfileQuery._get_time_ago(submission.submitted_at)
                recent_activities.append(RecentActivityType(
                    id=submission.id,
                    activity_type='SUBMISSION',
                    title=f"Submitted {submission.assignment.subject.name} Assignment",
                    description=submission.assignment.title,
                    timestamp=time_ago,
                    icon='document'
                ))
            
            # Get recent grades (last 10)
            recent_grades = AssignmentGrade.objects.filter(
                submission__student=student_profile
            ).select_related(
                'submission__assignment',
                'submission__assignment__subject'
            ).order_by('-graded_at')[:10]
            
            for grade in recent_grades:
                time_ago = ProfileQuery._get_time_ago(grade.graded_at)
                recent_activities.append(RecentActivityType(
                    id=grade.id,
                    activity_type='GRADE',
                    title=f"Received grade for {grade.submission.assignment.subject.name}",
                    description=f"{float(grade.marks_obtained)}/{float(grade.submission.assignment.max_marks)} - {grade.grade_letter}",
                    timestamp=time_ago,
                    icon='star'
                ))
            
            # Sort by timestamp (most recent first) and limit to 10
            recent_activities.sort(key=lambda x: x.timestamp)
            recent_activities = recent_activities[:10]
            
            # ==================================================
            # COURSE PROGRESS
            # ==================================================
            course_progress = []
            
            # Get all assignments for student's section grouped by subject
            assignments_by_subject = Assignment.objects.filter(
                section=student_profile.section,
                status__in=['PUBLISHED', 'CLOSED', 'GRADED']
            ).values(
                'subject__code',
                'subject__name'
            ).annotate(
                total=Count('id'),
                completed=Count(
                    'submissions',
                    filter=Q(submissions__student=student_profile)
                )
            )
            
            total_completed = 0
            total_assignments = 0
            
            for subject_data in assignments_by_subject:
                total = subject_data['total']
                completed = subject_data['completed']
                total_completed += completed
                total_assignments += total
                
                percentage = (completed / total * 100) if total > 0 else 0
                
                course_progress.append(CourseProgressType(
                    subject_code=subject_data['subject__code'],
                    subject_name=subject_data['subject__name'],
                    total_assignments=total,
                    completed_assignments=completed,
                    percentage=round(percentage, 1)
                ))
            
            # Calculate overall progress
            overall_progress = (total_completed / total_assignments * 100) if total_assignments > 0 else 0
            
            # ==================================================
            # CALCULATE GPA
            # ==================================================
            if student_profile.current_gpa is not None:
                current_gpa = float(student_profile.current_gpa)
            else:
                # Get all graded assignments for the student as fallback
                grades = AssignmentGrade.objects.filter(
                    submission__student=student_profile
                ).select_related('submission__assignment')
                
                if grades.exists():
                    # Calculate weighted average based on assignment weightage
                    total_weighted_score = 0
                    total_weightage = 0
                    
                    for grade in grades:
                        percentage = float(grade.percentage)
                        weightage = float(grade.submission.assignment.weightage)
                        total_weighted_score += (percentage * weightage)
                        total_weightage += weightage
                    
                    # Convert to GPA (assuming 100% = 4.0)
                    if total_weightage > 0:
                        avg_percentage = total_weighted_score / total_weightage
                        current_gpa = round((avg_percentage / 100) * 4.0, 2)
                    else:
                        current_gpa = None
                else:
                    current_gpa = None
            
            # ==================================================
            # NEXT CLASS & TODAY'S CLASSES
            # ==================================================
            today = now.date()
            current_day = now.isoweekday()  # 1=Monday, 7=Sunday
            current_time = now.time()
            
            # Get today's timetable entries
            today_entries = TimetableEntry.objects.filter(
                section=student_profile.section,
                is_active=True,
                period_definition__day_of_week=current_day
            ).select_related(
                'subject',
                'faculty',
                'room',
                'period_definition'
            ).order_by('period_definition__start_time')
            
            today_classes = []
            next_class = None
            
            day_names = {
                1: 'Monday',
                2: 'Tuesday',
                3: 'Wednesday',
                4: 'Thursday',
                5: 'Friday',
                6: 'Saturday',
                7: 'Sunday'
            }
            
            for entry in today_entries:
                class_info = NextClassType(
                    id=entry.id,
                    subject_name=entry.subject.name,
                    subject_code=entry.subject.code,
                    faculty_name=(entry.faculty.email or entry.faculty.register_number) if entry.faculty else 'TBA',
                    room_number=entry.room.room_number if entry.room else None,
                    day_of_week=entry.period_definition.day_of_week,
                    day_name=day_names.get(entry.period_definition.day_of_week, 'Unknown'),
                    start_time=entry.period_definition.start_time.strftime('%I:%M %p'),
                    end_time=entry.period_definition.end_time.strftime('%I:%M %p'),
                    period_number=entry.period_definition.period_number
                )
                
                today_classes.append(class_info)
                
                # Find next class (first class after current time)
                if next_class is None and entry.period_definition.start_time > current_time:
                    next_class = class_info
            
            # If no more classes today, get first class of tomorrow
            if next_class is None:
                tomorrow = current_day + 1 if current_day < 7 else 1
                tomorrow_entry = TimetableEntry.objects.filter(
                    section=student_profile.section,
                    is_active=True,
                    period_definition__day_of_week=tomorrow
                ).select_related(
                    'subject',
                    'faculty',
                    'room',
                    'period_definition'
                ).order_by('period_definition__start_time').first()
                
                if tomorrow_entry:
                    next_class = NextClassType(
                        id=tomorrow_entry.id,
                        subject_name=tomorrow_entry.subject.name,
                        subject_code=tomorrow_entry.subject.code,
                        faculty_name=(tomorrow_entry.faculty.email or tomorrow_entry.faculty.register_number) if tomorrow_entry.faculty else 'TBA',
                        room_number=tomorrow_entry.room.room_number if tomorrow_entry.room else None,
                        day_of_week=tomorrow_entry.period_definition.day_of_week,
                        day_name=day_names.get(tomorrow_entry.period_definition.day_of_week, 'Unknown'),
                        start_time=tomorrow_entry.period_definition.start_time.strftime('%I:%M %p'),
                        end_time=tomorrow_entry.period_definition.end_time.strftime('%I:%M %p'),
                        period_number=tomorrow_entry.period_definition.period_number
                    )
            
            # ==================================================
            # BUILD DASHBOARD RESPONSE
            # ==================================================
            return StudentDashboardType(
                student_name=student_profile.full_name,
                register_number=student_profile.register_number,
                profile_photo_url=f"/media/{student_profile.profile_photo}" if student_profile.profile_photo else None,
                assignments_due_this_week=assignments_due,
                total_pending_assignments=total_pending,
                total_overdue_assignments=total_overdue,
                recent_activities=recent_activities,
                course_progress=course_progress,
                overall_progress_percentage=round(overall_progress, 1),
                current_gpa=current_gpa,
                next_class=next_class,
                today_classes=today_classes
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
            from django.db.models import Count, Q, Avg
            from attendance.models import StudentAttendance, AttendanceSession
            
            # Get student profile
            student_profile = StudentProfile.objects.select_related(
                'section', 'course', 'department'
            ).get(register_number=register_number)
            
            # Get current semester
            current_semester = Semester.objects.filter(is_current=True).first()
            
            if not current_semester or not student_profile.section:
                return []
            
            # Get all timetable entries for student's section (these are their enrolled courses)
            timetable_entries = TimetableEntry.objects.filter(
                section=student_profile.section,
                semester=current_semester,
                is_active=True
            ).select_related(
                'subject',
                'subject__department',
                'faculty',
                'room',
                'period_definition'
            ).order_by('subject__id')
            
            # Get unique subjects (SQLite doesn't support DISTINCT ON)
            seen_subjects = set()
            unique_entries = []
            for entry in timetable_entries:
                if entry.subject.id not in seen_subjects:
                    seen_subjects.add(entry.subject.id)
                    unique_entries.append(entry)
            
            enrolled_courses = []
            
            for entry in unique_entries:
                subject = entry.subject
                
                # Get all schedule entries for this subject
                schedule_entries = TimetableEntry.objects.filter(
                    section=student_profile.section,
                    subject=subject,
                    semester=current_semester,
                    is_active=True
                ).select_related('period_definition')
                
                # Build class schedule
                class_schedule = []
                day_names = {
                    1: 'Monday', 2: 'Tuesday', 3: 'Wednesday',
                    4: 'Thursday', 5: 'Friday', 6: 'Saturday', 7: 'Sunday'
                }
                
                for sched_entry in schedule_entries:
                    class_schedule.append(CourseScheduleType(
                        day_name=day_names.get(sched_entry.period_definition.day_of_week, 'Unknown'),
                        start_time=sched_entry.period_definition.start_time.strftime('%I:%M %p'),
                        end_time=sched_entry.period_definition.end_time.strftime('%I:%M %p')
                    ))
                
                # Get assignments for this subject
                subject_assignments = Assignment.objects.filter(
                    subject=subject,
                    section=student_profile.section,
                    status__in=['PUBLISHED', 'CLOSED', 'GRADED']
                )
                
                total_assignments = subject_assignments.count()
                completed_assignments = AssignmentSubmission.objects.filter(
                    assignment__in=subject_assignments,
                    student=student_profile
                ).count()
                
                # Calculate course progress
                course_progress = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0
                
                # Calculate grade (average of all graded assignments)
                grades = AssignmentGrade.objects.filter(
                    submission__assignment__subject=subject,
                    submission__student=student_profile
                )
                
                grade_letter = None
                if grades.exists():
                    avg_percentage = grades.aggregate(
                        avg=Avg('marks_obtained')
                    )['avg']
                    
                    if avg_percentage is not None:
                        # Convert to letter grade
                        if avg_percentage >= 90:
                            grade_letter = 'A+'
                        elif avg_percentage >= 85:
                            grade_letter = 'A'
                        elif avg_percentage >= 80:
                            grade_letter = 'A-'
                        elif avg_percentage >= 75:
                            grade_letter = 'B+'
                        elif avg_percentage >= 70:
                            grade_letter = 'B'
                        elif avg_percentage >= 65:
                            grade_letter = 'B-'
                        elif avg_percentage >= 60:
                            grade_letter = 'C+'
                        elif avg_percentage >= 55:
                            grade_letter = 'C'
                        elif avg_percentage >= 50:
                            grade_letter = 'D'
                        else:
                            grade_letter = 'F'
                
                # Calculate attendance percentage for this subject
                # Get all attendance sessions for this subject
                attendance_sessions = AttendanceSession.objects.filter(
                    timetable_entry__subject=subject,
                    timetable_entry__section=student_profile.section,
                    status__in=['CLOSED', 'BLOCKED', 'CANCELLED']
                )
                
                total_sessions = attendance_sessions.count()
                attended_sessions = StudentAttendance.objects.filter(
                    student=student_profile,
                    session__in=attendance_sessions,
                    status='PRESENT'
                ).count()
                
                attendance_percentage = (attended_sessions / total_sessions * 100) if total_sessions > 0 else 0
                
                # Get subject description
                description = subject.description or f"Advanced topics in {subject.name.lower()}"
                
                enrolled_courses.append(EnrolledCourseType(
                    id=subject.id,
                    subject_code=subject.code,
                    subject_name=subject.name,
                    subject_type=subject.subject_type,
                    credits=float(subject.credits),
                    faculty_name=(entry.faculty.email or entry.faculty.register_number) if entry.faculty else 'TBA',
                    faculty_email=entry.faculty.email if entry.faculty else None,
                    description=description,
                    course_progress=round(course_progress, 1),
                    grade=grade_letter,
                    attendance_percentage=round(attendance_percentage, 1),
                    completed_assignments=completed_assignments,
                    total_assignments=total_assignments,
                    class_schedule=class_schedule
                ))
            
            return enrolled_courses
            
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
            from django.db.models import Avg, Sum
            from attendance.models import StudentAttendance, AttendanceSession
            
            # Get student profile
            student_profile = StudentProfile.objects.select_related('section').get(
                register_number=register_number
            )
            
            # Get current semester
            current_semester = Semester.objects.filter(is_current=True).first()
            
            if not current_semester or not student_profile.section:
                return None
            
            # Get unique subjects for student's section
            subjects = TimetableEntry.objects.filter(
                section=student_profile.section,
                semester=current_semester,
                is_active=True
            ).values('subject').distinct().count()
            
            # Calculate total credits
            total_credits = TimetableEntry.objects.filter(
                section=student_profile.section,
                semester=current_semester,
                is_active=True
            ).values('subject').distinct().aggregate(
                total=Sum('subject__credits')
            )['total'] or 0
            
            # Calculate average progress across all courses
            all_assignments = Assignment.objects.filter(
                section=student_profile.section,
                status__in=['PUBLISHED', 'CLOSED', 'GRADED']
            )
            
            total_assignments_count = all_assignments.count()
            completed_count = AssignmentSubmission.objects.filter(
                assignment__in=all_assignments,
                student=student_profile
            ).count()
            
            avg_progress = (completed_count / total_assignments_count * 100) if total_assignments_count > 0 else 0
            
            # Calculate average attendance across all subjects
            all_sessions = AttendanceSession.objects.filter(
                timetable_entry__section=student_profile.section,
                timetable_entry__semester=current_semester,
                status__in=['CLOSED', 'BLOCKED', 'CANCELLED']
            )
            
            total_sessions_count = all_sessions.count()
            attended_count = StudentAttendance.objects.filter(
                student=student_profile,
                session__in=all_sessions,
                status='PRESENT'
            ).count()
            
            avg_attendance = (attended_count / total_sessions_count * 100) if total_sessions_count > 0 else 0
            
            return CourseOverviewType(
                total_courses=subjects,
                total_credits=float(total_credits),
                avg_progress=round(avg_progress, 1),
                avg_attendance=round(avg_attendance, 1)
            )
            
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
        user = info.context.request.user

        # Ensure the user is a faculty member
        if user.role.code not in ('FACULTY', 'HOD', 'ADMIN'):
            return None

        try:
            from profile_management.models import FacultyProfile
            try:
                faculty_profile = FacultyProfile.objects.select_related(
                    'user', 'department'
                ).get(user=user)
                faculty_name = faculty_profile.full_name or user.email or 'Faculty'
                department_name = faculty_profile.department.name if faculty_profile.department else None
            except FacultyProfile.DoesNotExist:
                faculty_name = user.email or 'Faculty'
                department_name = user.department.name if user.department else None

            now = timezone.now()
            today = now.date()
            current_day = now.isoweekday()  # 1=Monday … 7=Sunday

            # Get current semester
            current_semester = Semester.objects.filter(is_current=True).first()

            # ──────────────────────────────────────────────
            # FACULTY'S TIMETABLE ENTRIES (current semester)
            # ──────────────────────────────────────────────
            faculty_entries_qs = TimetableEntry.objects.filter(
                faculty=user,
                is_active=True,
            )
            if current_semester:
                faculty_entries_qs = faculty_entries_qs.filter(semester=current_semester)

            faculty_entries = faculty_entries_qs.select_related(
                'subject', 'section', 'section__course',
                'room', 'period_definition', 'semester'
            )

            # ──────────────────────────────────────────────
            # SUMMARY CARDS
            # ──────────────────────────────────────────────
            # Total Students – count of unique students across all sections the faculty teaches
            section_ids = faculty_entries.values_list('section_id', flat=True).distinct()
            total_students = StudentProfile.objects.filter(
                section_id__in=section_ids,
                academic_status='ACTIVE'
            ).count()

            # Active Courses – number of distinct subjects
            active_courses = faculty_entries.values('subject_id').distinct().count()

            # Pending Reviews – assignment submissions awaiting grading
            faculty_assignments = Assignment.objects.filter(created_by=user)
            if current_semester:
                faculty_assignments = faculty_assignments.filter(semester=current_semester)
            pending_reviews = AssignmentSubmission.objects.filter(
                assignment__in=faculty_assignments,
                status__in=['SUBMITTED', 'RESUBMITTED']
            ).count()

            # ──────────────────────────────────────────────
            # TODAY'S CLASSES
            # ──────────────────────────────────────────────
            today_entries = faculty_entries.filter(
                period_definition__day_of_week=current_day
            ).order_by('period_definition__start_time')

            today_classes = []
            for entry in today_entries:
                today_classes.append(FacultyTodayClassType(
                    id=entry.id,
                    subject_name=entry.subject.name,
                    subject_code=entry.subject.code,
                    section_name=str(entry.section),
                    room_number=entry.room.room_number if entry.room else None,
                    start_time=entry.period_definition.start_time.strftime('%I:%M %p'),
                    end_time=entry.period_definition.end_time.strftime('%I:%M %p'),
                    period_number=entry.period_definition.period_number,
                ))

            # ──────────────────────────────────────────────
            # ATTENDANCE OVERVIEW (this week)
            # ──────────────────────────────────────────────
            week_start = today - timedelta(days=today.weekday())  # Monday
            week_end = week_start + timedelta(days=6)  # Sunday

            # Get distinct subjects taught by this faculty
            taught_subject_ids = (
                faculty_entries.values_list('subject_id', flat=True).distinct()
            )
            taught_subjects = Subject.objects.filter(id__in=taught_subject_ids)

            attendance_overview = []
            for subject in taught_subjects:
                # All sessions for this subject taught by this faculty this week
                sessions = AttendanceSession.objects.filter(
                    timetable_entry__faculty=user,
                    timetable_entry__subject=subject,
                    date__gte=week_start,
                    date__lte=week_end,
                    status__in=['CLOSED', 'BLOCKED']
                )
                total_records = StudentAttendance.objects.filter(
                    session__in=sessions
                ).count()
                present_records = StudentAttendance.objects.filter(
                    session__in=sessions,
                    status__in=['PRESENT', 'LATE']
                ).count()

                pct = (present_records / total_records * 100) if total_records > 0 else 0.0
                attendance_overview.append(FacultyAttendanceOverviewType(
                    subject_name=subject.name,
                    subject_code=subject.code,
                    attendance_percentage=round(pct, 1),
                ))

            # ──────────────────────────────────────────────
            # RECENT ACTIVITY
            # ──────────────────────────────────────────────
            recent_activities: list[FacultyRecentActivityType] = []

            # Recent graded assignments (last 10)
            recent_grades = AssignmentGrade.objects.filter(
                graded_by=user
            ).select_related(
                'submission__assignment',
                'submission__assignment__subject',
                'submission__student'
            ).order_by('-graded_at')[:10]

            for grade in recent_grades:
                time_ago = ProfileQuery._get_time_ago(grade.graded_at)
                sub_count = AssignmentSubmission.objects.filter(
                    assignment=grade.submission.assignment,
                    grade__graded_by=user
                ).count()
                recent_activities.append(FacultyRecentActivityType(
                    id=grade.id,
                    activity_type='GRADED_ASSIGNMENT',
                    title=f"Graded Assignment – {grade.submission.assignment.subject.name}",
                    description=f"Graded {sub_count} submissions • {time_ago}",
                    timestamp=time_ago,
                ))

            # Recent attendance sessions marked (last 10)
            recent_sessions = AttendanceSession.objects.filter(
                timetable_entry__faculty=user,
                status__in=['CLOSED', 'BLOCKED'],
                closed_at__isnull=False
            ).select_related(
                'timetable_entry__subject'
            ).order_by('-closed_at')[:10]

            for session in recent_sessions:
                time_ago = ProfileQuery._get_time_ago(session.closed_at)
                recent_activities.append(FacultyRecentActivityType(
                    id=session.id,
                    activity_type='MARKED_ATTENDANCE',
                    title=f"Marked Attendance – {session.timetable_entry.subject.name}",
                    description=f"{session.present_count}/{session.total_students} present • {time_ago}",
                    timestamp=time_ago,
                ))

            # Sort and limit
            recent_activities.sort(key=lambda x: x.timestamp)
            recent_activities = recent_activities[:10]

            # ──────────────────────────────────────────────
            # BUILD RESPONSE
            # ──────────────────────────────────────────────
            return FacultyDashboardType(
                faculty_name=faculty_name,
                department_name=department_name,
                total_students=total_students,
                active_courses=active_courses,
                pending_reviews=pending_reviews,
                today_classes=today_classes,
                today_class_count=len(today_classes),
                attendance_overview=attendance_overview,
                recent_activities=recent_activities,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return None

    @strawberry.field
    @require_auth
    def faculty_courses(self, info: Info, semester_id: Optional[int] = None) -> Optional[FacultyCourseOverviewType]:
        """
        Get courses taught by faculty along with high-level statistics
        """
        user = info.context.request.user
        if user.role.code not in ('FACULTY', 'HOD', 'ADMIN'):
            return None

        try:
            # 1. Base Query
            faculty_entries_qs = TimetableEntry.objects.filter(
                faculty=user,
                is_active=True
            ).select_related(
                'subject', 'section', 'semester', 'room', 'period_definition'
            )

            if semester_id:
                faculty_entries_qs = faculty_entries_qs.filter(semester_id=semester_id)
            else:
                current_semester = Semester.objects.filter(is_current=True).first()
                if current_semester:
                    faculty_entries_qs = faculty_entries_qs.filter(semester=current_semester)

            # 2. Extract unique courses (Subject + Section combination)
            course_map = {}  # key: (subject.id, section.id), value: dict of info
            for entry in faculty_entries_qs:
                key = (entry.subject.id, entry.section.id)
                if key not in course_map:
                    course_map[key] = {
                        'subject': entry.subject,
                        'section': entry.section,
                        'semester': entry.semester,
                        'entries': []
                    }
                course_map[key]['entries'].append(entry)

            # 3. Aggregate data
            total_students_set = set()
            total_assignments = 0
            
            courses_list = []
            
            # For calculating overall avg attendance across all courses
            global_attendance_present = 0
            global_attendance_total = 0

            # Day name mapping
            day_names = {1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 7: 'Sun'}

            for key, data in course_map.items():
                subject = data['subject']
                section = data['section']
                semester = data['semester']
                entries = data['entries']
                
                # Students count for this course
                students_qs = StudentProfile.objects.filter(section=section, academic_status='ACTIVE')
                students_count = students_qs.count()
                for s_id in students_qs.values_list('id', flat=True):
                    total_students_set.add(s_id)
                
                # Assignments count
                course_assignments = Assignment.objects.filter(
                    subject=subject, section=section, created_by=user, semester=semester
                ).count()
                total_assignments += course_assignments

                # Calculate class progress & attendance
                # We need AttendanceSession for this subject/section/faculty
                sessions = AttendanceSession.objects.filter(
                    timetable_entry__faculty=user,
                    timetable_entry__subject=subject,
                    timetable_entry__section=section,
                    timetable_entry__semester=semester,
                    status__in=['CLOSED', 'BLOCKED']
                )
                classes_completed = sessions.filter(status='CLOSED').count()
                # Estimate total classes: typically based on timetable entries per week * weeks in semester.
                # Here we just use a baseline mapping or fake total since semester config might vary.
                # Assuming ~16 weeks * entries per week.
                classes_total = len(entries) * 16
                
                # Fetch attendance counts
                attendance_total = StudentAttendance.objects.filter(session__in=sessions).count()
                attendance_present = StudentAttendance.objects.filter(session__in=sessions, status__in=['PRESENT', 'LATE']).count()
                
                if attendance_total > 0:
                    avg_attendance = (attendance_present / attendance_total) * 100
                else:
                    avg_attendance = 0.0

                global_attendance_present += attendance_present
                global_attendance_total += attendance_total

                # Schedule summary (e.g. "Mon, Wed, Fri - 9:00 AM")
                # Group by start time to make short string
                time_groups = {}
                for e in entries:
                    t = e.period_definition.start_time.strftime('%I:%M %p')
                    day = day_names.get(e.period_definition.day_of_week, '')
                    if t not in time_groups:
                        time_groups[t] = []
                    if day not in time_groups[t]:
                        time_groups[t].append(day)
                
                schedule_summaries = []
                for t, days in time_groups.items():
                    schedule_summaries.append(f"{', '.join(days)} - {t}")
                schedule_summary = " | ".join(schedule_summaries)

                # Room number (take the first room from entries)
                room_number = None
                for e in entries:
                    if e.room:
                        room_number = e.room.room_number
                        break

                courses_list.append(FacultyCourseType(
                    id=subject.id,
                    subject_code=subject.code,
                    subject_name=subject.name,
                    section_name=f"Section {section.name}",
                    semester_name=f"{semester.academic_year.year_code} Sem {semester.get_number_display()}",
                    students_count=students_count,
                    assignments_count=course_assignments,
                    classes_completed=classes_completed,
                    classes_total=max(classes_total, classes_completed), # avoid x/0 logic issues
                    avg_attendance=round(avg_attendance, 1),
                    schedule_summary=schedule_summary,
                    room_number=room_number
                ))

            # Final global totals
            total_courses = len(courses_list)
            total_students = len(total_students_set)
            
            global_avg_attendance = 0.0
            if global_attendance_total > 0:
                global_avg_attendance = round((global_attendance_present / global_attendance_total) * 100, 1)

            return FacultyCourseOverviewType(
                total_courses=total_courses,
                total_students=total_students,
                avg_attendance=global_avg_attendance,
                total_assignments=total_assignments,
                courses=courses_list
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return None

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
        user = info.context.request.user
        if user.role.code not in ('FACULTY', 'HOD', 'ADMIN'):
            return None

        try:
            from django.db.models import Q
            from profile_management.models import StudentProfile, Semester
            from timetable.models import TimetableEntry
            from attendance.models import AttendanceSession, StudentAttendance

            current_semester = Semester.objects.filter(is_current=True).first()
            if not current_semester:
                return FacultyStudentListType(students=[], total_count=0)

            # Find all sections the faculty teaches this semester
            faculty_sections = TimetableEntry.objects.filter(
                faculty=user,
                is_active=True,
                semester=current_semester
            ).values_list('section_id', flat=True).distinct()

            # Base query: students in those sections
            qs = StudentProfile.objects.filter(section_id__in=faculty_sections).select_related(
                'user', 'department', 'section', 'course'
            ).distinct()

            # Apply filters
            if search:
                qs = qs.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(register_number__icontains=search) |
                    Q(user__email__icontains=search)
                )

            if department_id:
                qs = qs.filter(department_id=department_id)

            total_count = qs.count()

            # Apply ordering
            qs = qs.order_by('first_name', 'last_name')

            # Pagination
            offset = (page - 1) * page_size
            students_page = qs[offset:offset + page_size]

            # Collect results
            students_list = []
            
            for student in students_page:
                # Calculate attendance (overall for student this semester)
                sessions = AttendanceSession.objects.filter(
                    timetable_entry__section=student.section,
                    timetable_entry__semester=current_semester,
                    status__in=['CLOSED', 'BLOCKED']
                )
                total_classes = sessions.filter(status='CLOSED').count()
                
                attendance_present = StudentAttendance.objects.filter(
                    student=student,
                    session__in=sessions,
                    status__in=['PRESENT', 'LATE']
                ).count()
                
                if total_classes > 0:
                    att_pct = round((attendance_present / total_classes) * 100, 1)
                else:
                    att_pct = 0.0
                    
                section_name = student.section.name if student.section else "?"
                semester_section = f"Sem {student.semester} - {section_name}"

                students_list.append(FacultyStudentType(
                    id=student.id,
                    full_name=student.full_name,
                    email=student.user.email if hasattr(student, 'user') and student.user else None,
                    register_number=student.register_number,
                    department_name=student.department.name if student.department else "Unknown",
                    semester_section=semester_section,
                    attendance_percentage=att_pct,
                    gpa=float(student.current_gpa) if student.current_gpa is not None else 0.0,
                    status=student.academic_status
                ))

            return FacultyStudentListType(
                students=students_list,
                total_count=total_count
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
