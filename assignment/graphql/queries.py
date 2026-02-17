"""
GraphQL Queries for Assignment System
"""
import strawberry
from typing import List, Optional
from django.db.models import Q

from assignment.models import Assignment, AssignmentSubmission, AssignmentGrade
from assignment.utils import (
    get_active_assignments_for_student,
    get_pending_assignments_for_student,
    get_overdue_assignments_for_student,
    get_faculty_assignments,
    get_assignment_statistics,
    get_student_assignment_statistics
)
from assignment.graphql.types import (
    AssignmentType,
    AssignmentSubmissionType,
    AssignmentGradeType,
    StudentAssignmentStatisticsType
)


@strawberry.type
class AssignmentQuery:
    """Assignment-related queries"""
    
    @strawberry.field
    def assignment(self, info, id: int) -> Optional[AssignmentType]:
        """
        Get a single assignment by ID
        """
        user = info.context.request.user
        
        try:
            assignment = Assignment.objects.get(id=id)
        except Assignment.DoesNotExist:
            return None
        
        # Check permissions
        if user.role.code == 'STUDENT':
            # Students can only see published assignments for their section
            from core.models import StudentProfile
            try:
                student_profile = StudentProfile.objects.get(user=user)
                if assignment.section != student_profile.section or assignment.status == 'DRAFT':
                    return None
            except StudentProfile.DoesNotExist:
                return None
        elif user.role.code == 'FACULTY':
            # Faculty can see assignments they created
            if assignment.created_by.id != user.id:
                return None
        
        return assignment
    
    @strawberry.field
    def assignments(
        self,
        info,
        section_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        semester_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[AssignmentType]:
        """
        Get list of assignments with filters
        """
        user = info.context.request.user
        
        # Base query based on user role
        if user.role.code == 'STUDENT':
            # Students see only published assignments for their section
            from core.models import StudentProfile
            try:
                student_profile = StudentProfile.objects.get(user=user)
                assignments = Assignment.objects.filter(
                    section=student_profile.section,
                    status='PUBLISHED'
                )
            except StudentProfile.DoesNotExist:
                return []
        
        elif user.role.code == 'FACULTY':
            # Faculty see assignments they created
            assignments = Assignment.objects.filter(created_by=user)
        
        elif user.role.code in ['ADMIN', 'HOD']:
            # Admin sees all assignments
            assignments = Assignment.objects.all()
        
        else:
            return []
        
        # Apply filters
        if section_id:
            assignments = assignments.filter(section_id=section_id)
        
        if subject_id:
            assignments = assignments.filter(subject_id=subject_id)
        
        if semester_id:
            assignments = assignments.filter(semester_id=semester_id)
        
        if status:
            assignments = assignments.filter(status=status)
        
        return list(assignments.select_related('subject', 'section', 'semester', 'created_by'))
    
    @strawberry.field
    def my_assignments(self, info) -> List[AssignmentType]:
        """
        Get assignments for current user (student or faculty)
        """
        user = info.context.request.user
        
        if user.role.code == 'STUDENT':
            from core.models import StudentProfile
            try:
                student_profile = StudentProfile.objects.get(user=user)
                assignments = get_active_assignments_for_student(student_profile)
                return list(assignments)
            except StudentProfile.DoesNotExist:
                return []
        
        elif user.role.code == 'FACULTY':
            assignments = get_faculty_assignments(user)
            return list(assignments)
        
        return []
    
    @strawberry.field
    def pending_assignments(self, info) -> List[AssignmentType]:
        """
        Get pending assignments for current student
        """
        user = info.context.request.user
        
        if user.role.code != 'STUDENT':
            raise Exception("Only students can query pending assignments")
        
        from core.models import StudentProfile
        try:
            student_profile = StudentProfile.objects.get(user=user)
            assignments = get_pending_assignments_for_student(student_profile)
            return list(assignments)
        except StudentProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def overdue_assignments(self, info) -> List[AssignmentType]:
        """
        Get overdue assignments for current student
        """
        user = info.context.request.user
        
        if user.role.code != 'STUDENT':
            raise Exception("Only students can query overdue assignments")
        
        from core.models import StudentProfile
        try:
            student_profile = StudentProfile.objects.get(user=user)
            assignments = get_overdue_assignments_for_student(student_profile)
            return list(assignments)
        except StudentProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def assignment_submissions(
        self,
        info,
        assignment_id: int
    ) -> List[AssignmentSubmissionType]:
        """
        Get all submissions for an assignment (faculty only)
        """
        user = info.context.request.user
        
        if user.role.code not in ['FACULTY', 'ADMIN', 'HOD']:
            raise Exception("Only faculty can view all submissions")
        
        try:
            assignment = Assignment.objects.get(id=assignment_id)
        except Assignment.DoesNotExist:
            raise Exception("Assignment not found")
        
        # Check if faculty is authorized
        if user.role.code == 'FACULTY':
            if assignment.created_by.id != user.id:
                from timetable.models import TimetableEntry
                teaches = TimetableEntry.objects.filter(
                    subject=assignment.subject,
                    section=assignment.section,
                    faculty=user,
                    is_active=True
                ).exists()
                
                if not teaches:
                    raise Exception("Not authorized to view these submissions")
        
        submissions = assignment.submissions.all().select_related(
            'student__user',
            'grade',
            'graded_by'
        )
        
        return list(submissions)
    
    @strawberry.field
    def my_submissions(self, info) -> List[AssignmentSubmissionType]:
        """
        Get all submissions for current student
        """
        user = info.context.request.user
        
        if user.role.code != 'STUDENT':
            raise Exception("Only students can query their submissions")
        
        from core.models import StudentProfile
        try:
            student_profile = StudentProfile.objects.get(user=user)
            submissions = AssignmentSubmission.objects.filter(
                student=student_profile
            ).select_related('assignment', 'grade', 'graded_by')
            
            return list(submissions)
        except StudentProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def submission(self, info, id: int) -> Optional[AssignmentSubmissionType]:
        """
        Get a single submission by ID
        """
        user = info.context.request.user
        
        try:
            submission = AssignmentSubmission.objects.get(id=id)
        except AssignmentSubmission.DoesNotExist:
            return None
        
        # Check permissions
        if user.role.code == 'STUDENT':
            # Students can only see their own submissions
            if submission.student.user.id != user.id:
                return None
        elif user.role.code == 'FACULTY':
            # Faculty can see submissions for their assignments
            if submission.assignment.created_by.id != user.id:
                from timetable.models import TimetableEntry
                teaches = TimetableEntry.objects.filter(
                    subject=submission.assignment.subject,
                    section=submission.assignment.section,
                    faculty=user,
                    is_active=True
                ).exists()
                
                if not teaches:
                    return None
        
        return submission
    
    @strawberry.field
    def student_assignment_statistics(
        self,
        info,
        student_id: Optional[int] = None,
        semester_id: Optional[int] = None
    ) -> StudentAssignmentStatisticsType:
        """
        Get assignment statistics for a student
        """
        user = info.context.request.user
        
        # Determine which student
        from core.models import StudentProfile
        
        if student_id:
            # Faculty/Admin querying specific student
            if user.role.code not in ['FACULTY', 'ADMIN', 'HOD']:
                raise Exception("Not authorized")
            
            try:
                student_profile = StudentProfile.objects.get(id=student_id)
            except StudentProfile.DoesNotExist:
                raise Exception("Student not found")
        else:
            # Student querying their own stats
            if user.role.code != 'STUDENT':
                raise Exception("Student ID required for non-student users")
            
            try:
                student_profile = StudentProfile.objects.get(user=user)
            except StudentProfile.DoesNotExist:
                raise Exception("Student profile not found")
        
        # Get semester if provided
        semester = None
        if semester_id:
            from profile_management.models import Semester
            try:
                semester = Semester.objects.get(id=semester_id)
            except Semester.DoesNotExist:
                pass
        
        # Get statistics
        stats = get_student_assignment_statistics(student_profile, semester)
        
        return StudentAssignmentStatisticsType(
            total_assignments=stats['total_assignments'],
            total_submitted=stats['total_submitted'],
            pending_submission=stats['pending_submission'],
            submission_percentage=stats['submission_percentage'],
            graded_count=stats['graded_count'],
            pending_grading=stats['pending_grading'],
            overdue_count=stats['overdue_count'],
            average_marks=stats['average_marks'],
            average_percentage=stats['average_percentage']
        )
    
    @strawberry.field
    def pending_grading(self, info) -> List[AssignmentSubmissionType]:
        """
        Get submissions pending grading for current faculty
        """
        user = info.context.request.user
        
        if user.role.code not in ['FACULTY', 'ADMIN', 'HOD']:
            raise Exception("Only faculty can query pending grading")
        
        # Get assignments created by this faculty
        assignments = Assignment.objects.filter(created_by=user)
        
        # Get submissions pending grading
        submissions = AssignmentSubmission.objects.filter(
            assignment__in=assignments,
            status__in=['SUBMITTED', 'RESUBMITTED']
        ).select_related('student__user', 'assignment').order_by('submitted_at')
        
        return list(submissions)
