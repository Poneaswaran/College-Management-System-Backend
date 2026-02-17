"""
GraphQL types for Assignment System
"""
import strawberry
import strawberry_django
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from assignment.models import Assignment, AssignmentSubmission, AssignmentGrade


# Input Types
@strawberry.input
class CreateAssignmentInput:
    """Input for creating an assignment"""
    subject_id: int
    section_id: int
    semester_id: int
    title: str
    description: str
    assignment_type: str
    due_date: datetime
    max_marks: Decimal
    weightage: Decimal
    allow_late_submission: bool = False
    late_submission_deadline: Optional[datetime] = None
    # Base64 file upload
    attachment_data: Optional[str] = None  # Base64 encoded file (data:type;base64,...)
    attachment_filename: Optional[str] = None  # Original filename


@strawberry.input
class UpdateAssignmentInput:
    """Input for updating an assignment"""
    assignment_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    max_marks: Optional[Decimal] = None
    weightage: Optional[Decimal] = None
    allow_late_submission: Optional[bool] = None
    late_submission_deadline: Optional[datetime] = None
    # Base64 file upload
    attachment_data: Optional[str] = None  # Base64 encoded file
    attachment_filename: Optional[str] = None  # Original filename


@strawberry.input
class SubmitAssignmentInput:
    """Input for submitting an assignment"""
    assignment_id: int
    submission_text: Optional[str] = None
    # File upload handled separately via mutation


@strawberry.input
class GradeAssignmentInput:
    """Input for grading a submission"""
    submission_id: int
    marks_obtained: Decimal
    feedback: Optional[str] = None
    grading_rubric: Optional[str] = None  # JSON string


@strawberry.input
class ReturnSubmissionInput:
    """Input for returning a submission for revision"""
    submission_id: int
    feedback: str


# Output Types
@strawberry_django.type(Assignment)
class AssignmentType:
    """GraphQL type for Assignment"""
    
    id: strawberry.ID
    title: str
    description: str
    assignment_type: str
    status: str
    due_date: datetime
    published_date: Optional[datetime]
    allow_late_submission: bool
    late_submission_deadline: Optional[datetime]
    max_marks: Decimal
    weightage: Decimal
    created_at: datetime
    updated_at: datetime
    
    # Properties
    is_overdue: bool
    can_submit: bool
    total_submissions: int
    graded_submissions: int
    pending_submissions: int
    
    # Relationships
    @strawberry_django.field
    def subject(self) -> 'SubjectType':
        return self.subject
    
    @strawberry_django.field
    def section(self) -> 'SectionType':
        return self.section
    
    @strawberry_django.field
    def semester(self) -> 'SemesterType':
        return self.semester
    
    @strawberry_django.field
    def created_by(self) -> 'UserType':
        return self.created_by
    
    @strawberry_django.field
    def submissions(self) -> List['AssignmentSubmissionType']:
        return self.submissions.all()
    
    # Custom fields
    @strawberry.field
    def subject_name(self) -> str:
        """Get subject name"""
        return self.subject.name
    
    @strawberry.field
    def section_name(self) -> str:
        """Get section name"""
        return self.section.name
    
    @strawberry.field
    def faculty_name(self) -> str:
        """Get faculty name"""
        return self.created_by.email or self.created_by.register_number or "Unknown"
    
    @strawberry.field
    def time_remaining(self) -> Optional[str]:
        """Get human-readable time remaining"""
        if self.is_overdue:
            return "Overdue"
        
        from django.utils import timezone
        delta = self.due_date - timezone.now()
        
        if delta.days > 0:
            return f"{delta.days} day(s)"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour(s)"
        else:
            minutes = delta.seconds // 60
            return f"{minutes} minute(s)"
    
    @strawberry.field
    def submission_percentage(self) -> float:
        """Get submission percentage"""
        from core.models import StudentProfile
        total_students = StudentProfile.objects.filter(
            section=self.section,
            is_active=True
        ).count()
        
        if total_students == 0:
            return 0.0
        
        return round((self.total_submissions / total_students) * 100, 2)
    
    @strawberry.field
    def statistics(self) -> 'AssignmentStatisticsType':
        """Get assignment statistics"""
        from assignment.utils import get_assignment_statistics
        stats = get_assignment_statistics(self)
        return AssignmentStatisticsType(
            total_students=stats['total_students'],
            total_submissions=stats['total_submissions'],
            not_submitted=stats['not_submitted'],
            submission_percentage=stats['submission_percentage'],
            graded_count=stats['graded_count'],
            pending_grading=stats['pending_grading'],
            late_submissions=stats['late_submissions'],
            average_marks=stats['average_marks'],
            average_percentage=stats['average_percentage']
        )
    
    # File attachment fields
    @strawberry.field
    def has_attachment(self) -> bool:
        """Check if assignment has attachment"""
        return bool(self.attachment)
    
    @strawberry.field
    def attachment_url(self) -> Optional[str]:
        """Get attachment URL"""
        if self.attachment:
            return self.attachment.url
        return None
    
    @strawberry.field
    def attachment_filename(self) -> Optional[str]:
        """Get attachment filename"""
        if self.attachment:
            import os
            return os.path.basename(self.attachment.name)
        return None


@strawberry_django.type(AssignmentSubmission)
class AssignmentSubmissionType:
    """GraphQL type for AssignmentSubmission"""
    
    id: strawberry.ID
    submission_text: Optional[str]
    submitted_at: datetime
    is_late: bool
    status: str
    graded_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Relationships
    @strawberry_django.field
    def assignment(self) -> AssignmentType:
        return self.assignment
    
    @strawberry_django.field
    def student(self) -> 'StudentProfileType':
        return self.student
    
    @strawberry_django.field
    def graded_by(self) -> Optional['UserType']:
        return self.graded_by
    
    @strawberry_django.field
    def grade(self) -> Optional['AssignmentGradeType']:
        return getattr(self, 'grade', None)
    
    # Custom fields
    @strawberry.field
    def student_name(self) -> str:
        """Get student name"""
        return f"{self.student.user.first_name} {self.student.user.last_name}"
    
    @strawberry.field
    def student_register_number(self) -> str:
        """Get student register number"""
        return self.student.register_number
    
    @strawberry.field
    def assignment_title(self) -> str:
        """Get assignment title"""
        return self.assignment.title
    
    @strawberry.field
    def has_attachment(self) -> bool:
        """Check if submission has attachment"""
        return bool(self.attachment)
    
    @strawberry.field
    def attachment_url(self) -> Optional[str]:
        """Get attachment URL"""
        if self.attachment:
            return self.attachment.url
        return None


@strawberry_django.type(AssignmentGrade)
class AssignmentGradeType:
    """GraphQL type for AssignmentGrade"""
    
    id: strawberry.ID
    marks_obtained: Decimal
    feedback: Optional[str]
    graded_at: datetime
    updated_at: datetime
    
    # Properties
    percentage: float
    grade_letter: str
    
    # Relationships
    @strawberry_django.field
    def submission(self) -> AssignmentSubmissionType:
        return self.submission
    
    @strawberry_django.field
    def graded_by(self) -> 'UserType':
        return self.graded_by
    
    # Custom fields
    @strawberry.field
    def max_marks(self) -> Decimal:
        """Get maximum marks from assignment"""
        return self.submission.assignment.max_marks


# Custom Types
@strawberry.type
class AssignmentStatisticsType:
    """Statistics for an assignment"""
    total_students: int
    total_submissions: int
    not_submitted: int
    submission_percentage: float
    graded_count: int
    pending_grading: int
    late_submissions: int
    average_marks: float
    average_percentage: float


@strawberry.type
class StudentAssignmentStatisticsType:
    """Statistics for a student's assignments"""
    total_assignments: int
    total_submitted: int
    pending_submission: int
    submission_percentage: float
    graded_count: int
    pending_grading: int
    overdue_count: int
    average_marks: float
    average_percentage: float


@strawberry.type
class SubmitAssignmentResponse:
    """Response for assignment submission"""
    success: bool
    message: str
    submission: Optional[AssignmentSubmissionType] = None


@strawberry.type
class GradeAssignmentResponse:
    """Response for grading"""
    success: bool
    message: str
    grade: Optional[AssignmentGradeType] = None


# Import types from other apps (at the end to avoid circular imports)
from timetable.graphql.types import SubjectType, SemesterType
from core.graphql.types import SectionType, UserType
from profile_management.graphql.types import StudentProfileType
