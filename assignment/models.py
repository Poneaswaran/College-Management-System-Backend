"""
Assignment Models for College Management System
Faculty creates assignments, students submit, faculty grades
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
import os


def assignment_file_path(instance, filename):
    """
    Generate unique path for assignment files
    Format: assignments/files/{semester_id}/{subject_id}/{assignment_id}/{filename}
    """
    return os.path.join(
        'assignments',
        'files',
        str(instance.subject.semester_number),
        str(instance.subject.id),
        str(instance.id),
        filename
    )


def submission_file_path(instance, filename):
    """
    Generate unique path for submission files
    Format: assignments/submissions/{assignment_id}/{student_id}/{timestamp}_{filename}
    """
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(
        'assignments',
        'submissions',
        str(instance.assignment.id),
        str(instance.student.id),
        f"{timestamp}_{filename}"
    )


class Assignment(models.Model):
    """
    Represents an assignment created by faculty for a subject
    """
    
    ASSIGNMENT_TYPE_CHOICES = [
        ('INDIVIDUAL', 'Individual'),
        ('GROUP', 'Group'),
        ('LAB', 'Lab Assignment'),
        ('PROJECT', 'Project'),
        ('QUIZ', 'Quiz'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),           # Not yet published
        ('PUBLISHED', 'Published'),   # Active and visible to students
        ('CLOSED', 'Closed'),         # Submissions no longer accepted
        ('GRADED', 'Graded'),         # All submissions graded
    ]
    
    # Core References
    subject = models.ForeignKey(
        'timetable.Subject',
        on_delete=models.CASCADE,
        related_name='assignments',
        help_text="Subject for which assignment is created"
    )
    section = models.ForeignKey(
        'core.Section',
        on_delete=models.CASCADE,
        related_name='assignments',
        help_text="Section to which assignment is assigned"
    )
    semester = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='assignments',
        help_text="Academic semester"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_assignments',
        help_text="Faculty who created this assignment"
    )
    
    # Assignment Details
    title = models.CharField(
        max_length=200,
        help_text="Assignment title"
    )
    description = models.TextField(
        help_text="Detailed description and instructions"
    )
    assignment_type = models.CharField(
        max_length=20,
        choices=ASSIGNMENT_TYPE_CHOICES,
        default='INDIVIDUAL'
    )
    
    # Files
    attachment = models.FileField(
        upload_to=assignment_file_path,
        null=True,
        blank=True,
        help_text="Optional assignment file (PDF, DOC, etc.)"
    )
    
    # Timing
    published_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When assignment was published to students"
    )
    due_date = models.DateTimeField(
        help_text="Submission deadline"
    )
    allow_late_submission = models.BooleanField(
        default=False,
        help_text="Allow submissions after due date"
    )
    late_submission_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Final deadline for late submissions"
    )
    
    # Grading
    max_marks = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Maximum marks for this assignment"
    )
    weightage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        help_text="Weightage in final grade (percentage)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        db_index=True
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date']
        verbose_name = "Assignment"
        verbose_name_plural = "Assignments"
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['subject', 'section']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.subject.name} ({self.section.name})"
    
    def clean(self):
        """Validate assignment data"""
        if self.due_date and self.due_date < timezone.now():
            if self.status == 'DRAFT':
                raise ValidationError("Due date cannot be in the past for new assignments")
        
        if self.allow_late_submission and not self.late_submission_deadline:
            raise ValidationError("Late submission deadline is required when late submissions are allowed")
        
        if self.late_submission_deadline and self.late_submission_deadline <= self.due_date:
            raise ValidationError("Late submission deadline must be after the due date")
    
    @property
    def is_overdue(self):
        """Check if assignment is past due date"""
        return timezone.now() > self.due_date
    
    @property
    def can_submit(self):
        """Check if students can still submit"""
        if self.status != 'PUBLISHED':
            return False
        
        now = timezone.now()
        if now <= self.due_date:
            return True
        
        if self.allow_late_submission and self.late_submission_deadline:
            return now <= self.late_submission_deadline
        
        return False
    
    @property
    def total_submissions(self):
        """Get total number of submissions"""
        return self.submissions.count()
    
    @property
    def graded_submissions(self):
        """Get number of graded submissions"""
        return self.submissions.filter(status='GRADED').count()
    
    @property
    def pending_submissions(self):
        """Get number of pending submissions"""
        from core.models import StudentProfile
        total_students = StudentProfile.objects.filter(
            section=self.section,
            is_active=True
        ).count()
        return total_students - self.total_submissions


class AssignmentSubmission(models.Model):
    """
    Represents a student's submission for an assignment
    """
    
    STATUS_CHOICES = [
        ('SUBMITTED', 'Submitted'),     # Submitted, awaiting grading
        ('GRADED', 'Graded'),           # Graded by faculty
        ('RETURNED', 'Returned'),       # Returned to student for revision
        ('RESUBMITTED', 'Resubmitted'), # Resubmitted after revision
    ]
    
    # Core References
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions',
        help_text="Assignment being submitted"
    )
    student = models.ForeignKey(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
        help_text="Student submitting the assignment"
    )
    
    # Submission Details
    submission_text = models.TextField(
        blank=True,
        help_text="Text submission or comments"
    )
    attachment = models.FileField(
        upload_to=submission_file_path,
        null=True,
        blank=True,
        help_text="Submitted file (PDF, DOC, ZIP, etc.)"
    )
    
    # Timing
    submitted_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When submission was made"
    )
    is_late = models.BooleanField(
        default=False,
        help_text="Whether submission was after due date"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='SUBMITTED',
        db_index=True
    )
    
    # Grading
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_submissions',
        help_text="Faculty who graded this submission"
    )
    graded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When submission was graded"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Assignment Submission"
        verbose_name_plural = "Assignment Submissions"
        unique_together = [['assignment', 'student']]
        indexes = [
            models.Index(fields=['assignment', 'status']),
            models.Index(fields=['student', 'submitted_at']),
        ]
    
    def __str__(self):
        return f"{self.student.user.email} - {self.assignment.title}"
    
    def clean(self):
        """Validate submission data"""
        # Check if student belongs to the assignment's section
        if self.student.section != self.assignment.section:
            raise ValidationError("Student does not belong to this assignment's section")
        
        # Check if assignment accepts submissions
        if not self.assignment.can_submit and not self.pk:
            raise ValidationError("Assignment is no longer accepting submissions")
    
    def save(self, *args, **kwargs):
        """Override save to set is_late flag"""
        if not self.pk:  # New submission
            self.is_late = timezone.now() > self.assignment.due_date
        super().save(*args, **kwargs)


class AssignmentGrade(models.Model):
    """
    Represents grading and feedback for a submission
    """
    
    # Core References
    submission = models.OneToOneField(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name='grade',
        help_text="Submission being graded"
    )
    
    # Grading
    marks_obtained = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Marks awarded to student"
    )
    feedback = models.TextField(
        blank=True,
        help_text="Faculty feedback and comments"
    )
    
    # Additional fields
    grading_rubric = models.JSONField(
        null=True,
        blank=True,
        help_text="Detailed rubric breakdown (optional)"
    )
    
    # Metadata
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_grades',
        help_text="Faculty who graded"
    )
    graded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-graded_at']
        verbose_name = "Assignment Grade"
        verbose_name_plural = "Assignment Grades"
    
    def __str__(self):
        return f"Grade for {self.submission}"
    
    def clean(self):
        """Validate grade data"""
        if self.marks_obtained > self.submission.assignment.max_marks:
            raise ValidationError(
                f"Marks obtained ({self.marks_obtained}) cannot exceed maximum marks ({self.submission.assignment.max_marks})"
            )
        
        if self.marks_obtained < 0:
            raise ValidationError("Marks cannot be negative")
    
    @property
    def percentage(self):
        """Calculate percentage"""
        max_marks = self.submission.assignment.max_marks
        if max_marks > 0:
            return (self.marks_obtained / max_marks) * 100
        return 0
    
    @property
    def grade_letter(self):
        """Calculate letter grade"""
        percentage = self.percentage
        if percentage >= 90:
            return 'A+'
        elif percentage >= 80:
            return 'A'
        elif percentage >= 70:
            return 'B+'
        elif percentage >= 60:
            return 'B'
        elif percentage >= 50:
            return 'C'
        elif percentage >= 40:
            return 'D'
        else:
            return 'F'
