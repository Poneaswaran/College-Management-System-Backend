"""GraphQL queries for profile management"""
import strawberry
from typing import List, Optional
from strawberry.types import Info
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Count, Q

from profile_management.models import StudentProfile, ParentProfile, AcademicYear, Semester
from .types import StudentProfileType, ParentProfileType
from core.graphql.auth import require_auth
from timetable.graphql.types import AcademicYearType, SemesterType
from assignment.models import Assignment, AssignmentSubmission, AssignmentGrade
from timetable.models import TimetableEntry


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
    assignments_due_this_week: List[AssignmentDueType]
    total_pending_assignments: int
    total_overdue_assignments: int
    recent_activities: List[RecentActivityType]
    course_progress: List[CourseProgressType]
    overall_progress_percentage: float
    current_gpa: Optional[float]
    next_class: Optional[NextClassType]
    today_classes: List[NextClassType]


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
                time_ago = self._get_time_ago(submission.submitted_at)
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
                time_ago = self._get_time_ago(grade.graded_at)
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
            # Get all graded assignments for the student
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
    
    def _get_time_ago(self, dt: datetime) -> str:
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
