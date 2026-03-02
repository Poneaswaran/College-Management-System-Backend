"""
GraphQL Mutations for Faculty Grade Submission
Implements saveGradesDraft and submitGrades mutations
"""
import strawberry
from strawberry.types import Info
from django.utils import timezone
from django.db.models import Q

from grades.models import CourseSectionAssignment, GradeBatch, GradeEntry
from profile_management.models import FacultyProfile, StudentProfile
from grades.graphql.faculty_types import (
    SaveGradesDraftInput,
    SaveGradesDraftResult,
    SubmitGradesInput,
    SubmitGradesResult,
    GradeStatus,
)


@strawberry.type
class FacultyGradesMutation:
    @strawberry.mutation
    def save_grades_draft(
        self,
        info: Info,
        input: SaveGradesDraftInput,
    ) -> SaveGradesDraftResult:
        """
        Saves or updates grade entries as a draft.
        Idempotent — safe to call multiple times.
        Does NOT change the GradeBatch status (remains DRAFT).
        """
        faculty_user = info.context.request.user
        
        # Get assignment with ownership check
        try:
            assignment = CourseSectionAssignment.objects.select_related(
                'faculty', 'faculty__user'
            ).get(
                id=input.course_section_id,
                faculty__user=faculty_user,
                is_active=True,
            )
        except CourseSectionAssignment.DoesNotExist:
            raise ValueError("Course section not found or access denied.")
        
        # Get or create grade batch
        grade_batch, _ = GradeBatch.objects.get_or_create(
            course_section_assignment=assignment,
            defaults={'status': 'DRAFT'},
        )
        
        # Only drafts or rejected batches can be edited
        if grade_batch.status not in ('DRAFT', 'REJECTED'):
            raise ValueError("Cannot edit a grade batch that is SUBMITTED or APPROVED.")
        
        # Upsert grade entries
        for grade_input in input.grades:
            try:
                student_id = int(grade_input.student_id)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid student_id: {grade_input.student_id}")
            
            # Verify student belongs to the section
            try:
                student = StudentProfile.objects.get(
                    id=student_id,
                    section=assignment.section,
                    is_active=True,
                )
            except StudentProfile.DoesNotExist:
                raise ValueError(f"Student {grade_input.student_id} not found in section {assignment.section.name}")
            
            GradeEntry.objects.update_or_create(
                grade_batch=grade_batch,
                student=student,
                defaults={
                    'internal_mark': None if grade_input.is_absent else grade_input.internal_mark,
                    'external_mark': None if grade_input.is_absent else grade_input.external_mark,
                    'is_absent': grade_input.is_absent,
                },
            )
        
        grade_batch.updated_at = timezone.now()
        grade_batch.save(update_fields=['updated_at'])
        
        return SaveGradesDraftResult(
            success=True,
            message="Draft saved successfully.",
            updated_at=grade_batch.updated_at.isoformat(),
        )
    
    @strawberry.mutation
    def submit_grades(
        self,
        info: Info,
        input: SubmitGradesInput,
    ) -> SubmitGradesResult:
        """
        Submits the grade batch for HOD/admin approval.
        After submission, the faculty cannot edit until the batch is rejected.
        All student grades must have marks entered (or marked absent) before submission.
        """
        faculty_user = info.context.request.user
        
        # Get assignment with ownership check
        try:
            assignment = CourseSectionAssignment.objects.select_related(
                'faculty', 'faculty__user', 'section'
            ).get(
                id=input.course_section_id,
                faculty__user=faculty_user,
                is_active=True,
            )
        except CourseSectionAssignment.DoesNotExist:
            raise ValueError("Course section not found or access denied.")
        
        # Get or create grade batch
        grade_batch, _ = GradeBatch.objects.get_or_create(
            course_section_assignment=assignment,
            defaults={'status': 'DRAFT'},
        )
        
        # Only drafts or rejected batches can be submitted
        if grade_batch.status not in ('DRAFT', 'REJECTED'):
            raise ValueError("Grades are already submitted or approved.")
        
        # Upsert all grade entries (same logic as saveGradesDraft)
        for grade_input in input.grades:
            try:
                student_id = int(grade_input.student_id)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid student_id: {grade_input.student_id}")
            
            # Verify student belongs to the section
            try:
                student = StudentProfile.objects.get(
                    id=student_id,
                    section=assignment.section,
                    is_active=True,
                )
            except StudentProfile.DoesNotExist:
                raise ValueError(f"Student {grade_input.student_id} not found in section {assignment.section.name}")
            
            GradeEntry.objects.update_or_create(
                grade_batch=grade_batch,
                student=student,
                defaults={
                    'internal_mark': None if grade_input.is_absent else grade_input.internal_mark,
                    'external_mark': None if grade_input.is_absent else grade_input.external_mark,
                    'is_absent': grade_input.is_absent,
                },
            )
        
        # Validation: all students must have marks or be marked absent
        total_students = assignment.section.student_profiles.filter(is_active=True).count()
        complete_entries = GradeEntry.objects.filter(
            grade_batch=grade_batch,
        ).filter(
            Q(is_absent=True) |
            Q(internal_mark__isnull=False, external_mark__isnull=False)
        ).count()
        
        if complete_entries < total_students:
            raise ValueError(
                f"All {total_students} students must have marks entered or be marked absent before submission. "
                f"Only {complete_entries} are complete."
            )
        
        # Update batch status to SUBMITTED
        now = timezone.now()
        grade_batch.status = 'SUBMITTED'
        grade_batch.submitted_at = now
        grade_batch.updated_at = now
        grade_batch.save(update_fields=['status', 'submitted_at', 'updated_at'])
        
        # TODO: Send notification to HOD about new grade submission
        # notify_hod_grade_submission(assignment, grade_batch)
        
        return SubmitGradesResult(
            success=True,
            message="Grades submitted successfully and sent for approval.",
            submitted_at=now.isoformat(),
            status=GradeStatus.SUBMITTED,
        )
