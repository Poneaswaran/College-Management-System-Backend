"""
GraphQL Mutations for Assignment System
"""
import strawberry
from typing import Optional
from django.utils import timezone
from django.core.files.base import ContentFile
import json

from assignment.models import Assignment, AssignmentSubmission, AssignmentGrade
from assignment.validators import AssignmentValidator
from assignment.graphql.types import (
    AssignmentType,
    AssignmentSubmissionType,
    AssignmentGradeType,
    CreateAssignmentInput,
    UpdateAssignmentInput,
    SubmitAssignmentInput,
    GradeAssignmentInput,
    ReturnSubmissionInput,
    SubmitAssignmentResponse,
    GradeAssignmentResponse
)


@strawberry.type
class AssignmentMutation:
    """Assignment-related mutations"""
    
    @strawberry.mutation
    def create_assignment(
        self,
        info,
        input: CreateAssignmentInput
    ) -> AssignmentType:
        """
        Faculty creates a new assignment
        """
        user = info.context.request.user
        
        # Check if user is faculty
        if user.role.name not in ['FACULTY', 'ADMIN', 'SUPER_ADMIN']:
            raise Exception("Only faculty can create assignments")
        
        # Get related objects
        from timetable.models import Subject
        from core.models import Section
        from profile_management.models import Semester
        
        try:
            subject = Subject.objects.get(id=input.subject_id)
            section = Section.objects.get(id=input.section_id)
            semester = Semester.objects.get(id=input.semester_id)
        except Exception as e:
            raise Exception(f"Invalid reference: {str(e)}")
        
        # Validate
        is_valid, error_message = AssignmentValidator.validate_assignment_creation(
            subject,
            section,
            input.due_date,
            user
        )
        
        if not is_valid:
            raise Exception(error_message)
        
        # Create assignment
        assignment = Assignment.objects.create(
            subject=subject,
            section=section,
            semester=semester,
            created_by=user,
            title=input.title,
            description=input.description,
            assignment_type=input.assignment_type,
            due_date=input.due_date,
            max_marks=input.max_marks,
            weightage=input.weightage,
            allow_late_submission=input.allow_late_submission,
            late_submission_deadline=input.late_submission_deadline,
            status='DRAFT'
        )
        
        return assignment
    
    @strawberry.mutation
    def update_assignment(
        self,
        info,
        input: UpdateAssignmentInput
    ) -> AssignmentType:
        """
        Faculty updates an existing assignment
        """
        user = info.context.request.user
        
        # Get assignment
        try:
            assignment = Assignment.objects.get(id=input.assignment_id)
        except Assignment.DoesNotExist:
            raise Exception("Assignment not found")
        
        # Check if user is the creator
        if assignment.created_by.id != user.id:
            if user.role.name not in ['ADMIN', 'SUPER_ADMIN']:
                raise Exception("Only the creator can update this assignment")
        
        # Check if assignment is published (restrict updates)
        if assignment.status != 'DRAFT':
            # Only allow certain updates for published assignments
            if input.title:
                assignment.title = input.title
            if input.description:
                assignment.description = input.description
            if input.feedback:
                assignment.feedback = input.feedback
        else:
            # Update all fields for draft assignments
            if input.title:
                assignment.title = input.title
            if input.description:
                assignment.description = input.description
            if input.due_date:
                assignment.due_date = input.due_date
            if input.max_marks is not None:
                assignment.max_marks = input.max_marks
            if input.weightage is not None:
                assignment.weightage = input.weightage
            if input.allow_late_submission is not None:
                assignment.allow_late_submission = input.allow_late_submission
            if input.late_submission_deadline:
                assignment.late_submission_deadline = input.late_submission_deadline
        
        assignment.save()
        return assignment
    
    @strawberry.mutation
    def publish_assignment(
        self,
        info,
        assignment_id: int
    ) -> AssignmentType:
        """
        Faculty publishes an assignment (makes it visible to students)
        """
        user = info.context.request.user
        
        # Get assignment
        try:
            assignment = Assignment.objects.get(id=assignment_id)
        except Assignment.DoesNotExist:
            raise Exception("Assignment not found")
        
        # Validate
        is_valid, error_message = AssignmentValidator.validate_assignment_publish(
            assignment,
            user
        )
        
        if not is_valid:
            raise Exception(error_message)
        
        # Publish
        assignment.status = 'PUBLISHED'
        assignment.published_date = timezone.now()
        assignment.save()
        
        return assignment
    
    @strawberry.mutation
    def close_assignment(
        self,
        info,
        assignment_id: int
    ) -> AssignmentType:
        """
        Faculty closes an assignment (no more submissions accepted)
        """
        user = info.context.request.user
        
        # Get assignment
        try:
            assignment = Assignment.objects.get(id=assignment_id)
        except Assignment.DoesNotExist:
            raise Exception("Assignment not found")
        
        # Check if user is the creator
        if assignment.created_by.id != user.id:
            if user.role.name not in ['ADMIN', 'SUPER_ADMIN']:
                raise Exception("Only the creator can close this assignment")
        
        # Close
        assignment.status = 'CLOSED'
        assignment.save()
        
        return assignment
    
    @strawberry.mutation
    def delete_assignment(
        self,
        info,
        assignment_id: int
    ) -> bool:
        """
        Delete an assignment (only if no submissions)
        """
        user = info.context.request.user
        
        # Get assignment
        try:
            assignment = Assignment.objects.get(id=assignment_id)
        except Assignment.DoesNotExist:
            raise Exception("Assignment not found")
        
        # Validate
        is_valid, error_message = AssignmentValidator.validate_assignment_deletion(
            assignment,
            user
        )
        
        if not is_valid:
            raise Exception(error_message)
        
        # Delete
        assignment.delete()
        return True
    
    @strawberry.mutation
    def submit_assignment(
        self,
        info,
        input: SubmitAssignmentInput
    ) -> SubmitAssignmentResponse:
        """
        Student submits an assignment
        """
        user = info.context.request.user
        
        # Check if user is student
        if user.role.name != 'STUDENT':
            raise Exception("Only students can submit assignments")
        
        # Get student profile
        try:
            from core.models import StudentProfile
            student_profile = StudentProfile.objects.get(user=user)
        except StudentProfile.DoesNotExist:
            raise Exception("Student profile not found")
        
        # Get assignment
        try:
            assignment = Assignment.objects.get(id=input.assignment_id)
        except Assignment.DoesNotExist:
            raise Exception("Assignment not found")
        
        # Validate
        is_valid, error_message = AssignmentValidator.validate_submission(
            assignment,
            student_profile
        )
        
        if not is_valid:
            return SubmitAssignmentResponse(
                success=False,
                message=error_message,
                submission=None
            )
        
        # Check if this is a resubmission
        existing_submission = AssignmentSubmission.objects.filter(
            assignment=assignment,
            student=student_profile
        ).first()
        
        if existing_submission and existing_submission.status == 'RETURNED':
            # Resubmission
            existing_submission.submission_text = input.submission_text
            existing_submission.status = 'RESUBMITTED'
            existing_submission.save()
            
            return SubmitAssignmentResponse(
                success=True,
                message="Assignment resubmitted successfully",
                submission=existing_submission
            )
        
        # Create new submission
        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=student_profile,
            submission_text=input.submission_text or ""
        )
        
        return SubmitAssignmentResponse(
            success=True,
            message="Assignment submitted successfully",
            submission=submission
        )
    
    @strawberry.mutation
    def grade_assignment(
        self,
        info,
        input: GradeAssignmentInput
    ) -> GradeAssignmentResponse:
        """
        Faculty grades a submission
        """
        user = info.context.request.user
        
        # Check if user is faculty
        if user.role.name not in ['FACULTY', 'ADMIN', 'SUPER_ADMIN']:
            raise Exception("Only faculty can grade assignments")
        
        # Get submission
        try:
            submission = AssignmentSubmission.objects.get(id=input.submission_id)
        except AssignmentSubmission.DoesNotExist:
            raise Exception("Submission not found")
        
        # Validate
        is_valid, error_message = AssignmentValidator.validate_grading(
            submission,
            user,
            input.marks_obtained
        )
        
        if not is_valid:
            return GradeAssignmentResponse(
                success=False,
                message=error_message,
                grade=None
            )
        
        # Parse rubric if provided
        grading_rubric = None
        if input.grading_rubric:
            try:
                grading_rubric = json.loads(input.grading_rubric)
            except:
                pass
        
        # Check if grade already exists
        grade = None
        try:
            grade = AssignmentGrade.objects.get(submission=submission)
            # Update existing grade
            grade.marks_obtained = input.marks_obtained
            grade.feedback = input.feedback or ""
            grade.grading_rubric = grading_rubric
            grade.graded_by = user
            grade.save()
        except AssignmentGrade.DoesNotExist:
            # Create new grade
            grade = AssignmentGrade.objects.create(
                submission=submission,
                marks_obtained=input.marks_obtained,
                feedback=input.feedback or "",
                grading_rubric=grading_rubric,
                graded_by=user
            )
        
        # Update submission status
        submission.status = 'GRADED'
        submission.graded_by = user
        submission.graded_at = timezone.now()
        submission.save()
        
        return GradeAssignmentResponse(
            success=True,
            message="Assignment graded successfully",
            grade=grade
        )
    
    @strawberry.mutation
    def return_submission(
        self,
        info,
        input: ReturnSubmissionInput
    ) -> AssignmentSubmissionType:
        """
        Faculty returns a submission for revision
        """
        user = info.context.request.user
        
        # Check if user is faculty
        if user.role.name not in ['FACULTY', 'ADMIN', 'SUPER_ADMIN']:
            raise Exception("Only faculty can return submissions")
        
        # Get submission
        try:
            submission = AssignmentSubmission.objects.get(id=input.submission_id)
        except AssignmentSubmission.DoesNotExist:
            raise Exception("Submission not found")
        
        # Check authorization
        assignment = submission.assignment
        if assignment.created_by.id != user.id:
            from timetable.models import TimetableEntry
            teaches = TimetableEntry.objects.filter(
                subject=assignment.subject,
                section=assignment.section,
                faculty=user,
                is_active=True
            ).exists()
            
            if not teaches and user.role.name not in ['ADMIN', 'SUPER_ADMIN']:
                raise Exception("Not authorized to return this submission")
        
        # Return submission
        submission.status = 'RETURNED'
        submission.graded_by = user
        submission.graded_at = timezone.now()
        
        # Update or create grade with feedback
        try:
            grade = AssignmentGrade.objects.get(submission=submission)
            grade.feedback = input.feedback
            grade.save()
        except AssignmentGrade.DoesNotExist:
            # Don't create grade yet, just update submission
            pass
        
        submission.save()
        
        return submission
