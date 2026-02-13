"""
Validators for Assignment System
"""
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q


class AssignmentValidator:
    """
    Validates assignment operations
    """
    
    @staticmethod
    def validate_assignment_creation(subject, section, due_date, faculty_user):
        """
        Validate if faculty can create an assignment
        
        Args:
            subject: Subject instance
            section: Section instance
            due_date: Due date for assignment
            faculty_user: User instance (faculty)
        
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check if faculty teaches this subject to this section
        from timetable.models import TimetableEntry
        
        teaches_class = TimetableEntry.objects.filter(
            subject=subject,
            section=section,
            faculty=faculty_user,
            is_active=True
        ).exists()
        
        if not teaches_class:
            return False, "You are not assigned to teach this subject to this section"
        
        # Check if due date is in the future
        if due_date <= timezone.now():
            return False, "Due date must be in the future"
        
        return True, ""
    
    @staticmethod
    def validate_assignment_publish(assignment, faculty_user):
        """
        Validate if assignment can be published
        
        Args:
            assignment: Assignment instance
            faculty_user: User instance
        
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check if user is the creator
        if assignment.created_by.id != faculty_user.id:
            return False, "Only the creator can publish this assignment"
        
        # Check if already published
        if assignment.status == 'PUBLISHED':
            return False, "Assignment is already published"
        
        # Check if closed
        if assignment.status == 'CLOSED':
            return False, "Cannot publish a closed assignment"
        
        # Check if due date is in the future
        if assignment.due_date <= timezone.now():
            return False, "Cannot publish assignment with past due date"
        
        return True, ""
    
    @staticmethod
    def validate_submission(assignment, student_profile):
        """
        Validate if student can submit assignment
        
        Args:
            assignment: Assignment instance
            student_profile: StudentProfile instance
        
        Returns:
            tuple: (is_valid, error_message)
        """
        from assignment.models import AssignmentSubmission
        
        # Check if assignment is published
        if assignment.status != 'PUBLISHED':
            return False, "Assignment is not published yet"
        
        # Check if student belongs to the section
        if student_profile.section != assignment.section:
            return False, "You are not assigned to this section"
        
        # Check if already submitted
        existing_submission = AssignmentSubmission.objects.filter(
            assignment=assignment,
            student=student_profile
        ).first()
        
        if existing_submission:
            if existing_submission.status == 'RETURNED':
                # Allow resubmission
                pass
            else:
                return False, "You have already submitted this assignment"
        
        # Check if still accepting submissions
        if not assignment.can_submit:
            return False, "Assignment is no longer accepting submissions"
        
        return True, ""
    
    @staticmethod
    def validate_grading(submission, faculty_user, marks_obtained):
        """
        Validate if faculty can grade a submission
        
        Args:
            submission: AssignmentSubmission instance
            faculty_user: User instance
            marks_obtained: Marks to be awarded
        
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check if faculty is the assignment creator or teaches the subject
        assignment = submission.assignment
        
        if assignment.created_by.id != faculty_user.id:
            from timetable.models import TimetableEntry
            teaches = TimetableEntry.objects.filter(
                subject=assignment.subject,
                section=assignment.section,
                faculty=faculty_user,
                is_active=True
            ).exists()
            
            if not teaches:
                return False, "You are not authorized to grade this assignment"
        
        # Validate marks
        if marks_obtained < 0:
            return False, "Marks cannot be negative"
        
        if marks_obtained > assignment.max_marks:
            return False, f"Marks cannot exceed maximum marks ({assignment.max_marks})"
        
        # Check if submission is in valid state for grading
        if submission.status not in ['SUBMITTED', 'RESUBMITTED', 'GRADED']:
            return False, f"Cannot grade submission with status: {submission.status}"
        
        return True, ""
    
    @staticmethod
    def validate_file_upload(file):
        """
        Validate uploaded file
        
        Args:
            file: Uploaded file
        
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            return False, "File size cannot exceed 10MB"
        
        # Check file extension
        allowed_extensions = [
            '.pdf', '.doc', '.docx', '.txt',
            '.zip', '.rar', '.7z',
            '.jpg', '.jpeg', '.png',
            '.ppt', '.pptx', '.xls', '.xlsx'
        ]
        
        file_name = file.name.lower()
        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        
        return True, ""
    
    @staticmethod
    def validate_assignment_deletion(assignment, user):
        """
        Validate if assignment can be deleted
        
        Args:
            assignment: Assignment instance
            user: User instance
        
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check if user is the creator or admin
        if assignment.created_by.id != user.id:
            if user.role.name not in ['ADMIN', 'SUPER_ADMIN']:
                return False, "Only the creator or admin can delete this assignment"
        
        # Check if has submissions
        if assignment.submissions.exists():
            return False, "Cannot delete assignment with existing submissions"
        
        return True, ""
    
    @staticmethod
    def validate_late_submission(assignment, student_profile):
        """
        Check if late submission is allowed
        
        Args:
            assignment: Assignment instance
            student_profile: StudentProfile instance
        
        Returns:
            tuple: (is_allowed, message)
        """
        now = timezone.now()
        
        # Check if past due date
        if now <= assignment.due_date:
            return True, "Within deadline"
        
        # Check if late submissions allowed
        if not assignment.allow_late_submission:
            return False, "Late submissions not allowed"
        
        # Check if within late submission window
        if assignment.late_submission_deadline and now <= assignment.late_submission_deadline:
            return True, "Late submission allowed"
        
        return False, "Late submission deadline passed"
