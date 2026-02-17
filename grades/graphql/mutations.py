"""
GraphQL mutations for grades management
"""
import strawberry
from typing import Optional
from strawberry.types import Info
from datetime import date

from grades.models import CourseGrade, SemesterGPA, StudentCGPA
from profile_management.models import StudentProfile, Semester
from timetable.models import Subject
from .types import CourseGradeType
from core.graphql.auth import require_auth


@strawberry.input
class CourseGradeInput:
    """Input for creating/updating course grade"""
    student_register_number: str
    subject_id: int
    semester_id: int
    internal_marks: float
    internal_max_marks: float = 40.0
    exam_marks: float
    exam_max_marks: float = 60.0
    exam_type: str = "FINAL"
    exam_date: Optional[date] = None
    remarks: Optional[str] = ""
    is_published: bool = False


@strawberry.type
class CourseGradeMutationResponse:
    """Response for course grade mutations"""
    success: bool
    message: str
    grade: Optional[CourseGradeType]


@strawberry.type
class GradesMutation:
    """Grades-related mutations"""
    
    @strawberry.mutation
    @require_auth
    def create_course_grade(
        self,
        info: Info,
        input: CourseGradeInput
    ) -> CourseGradeMutationResponse:
        """
        Create a new course grade (Faculty/Admin only)
        """
        user = info.context.request.user
        
        # Check permissions
        if user.role.code not in ['FACULTY', 'ADMIN', 'HOD']:
            return CourseGradeMutationResponse(
                success=False,
                message="Only faculty and admins can create grades",
                grade=None
            )
        
        try:
            student = StudentProfile.objects.get(register_number=input.student_register_number)
            subject = Subject.objects.get(id=input.subject_id)
            semester = Semester.objects.get(id=input.semester_id)
            
            # Check if grade already exists
            if CourseGrade.objects.filter(
                student=student,
                subject=subject,
                semester=semester
            ).exists():
                return CourseGradeMutationResponse(
                    success=False,
                    message="Grade for this course already exists. Use update mutation instead.",
                    grade=None
                )
            
            # Create grade
            grade = CourseGrade.objects.create(
                student=student,
                subject=subject,
                semester=semester,
                internal_marks=input.internal_marks,
                internal_max_marks=input.internal_max_marks,
                exam_marks=input.exam_marks,
                exam_max_marks=input.exam_max_marks,
                exam_type=input.exam_type,
                exam_date=input.exam_date,
                remarks=input.remarks or "",
                is_published=input.is_published,
                graded_by=user
            )
            
            # Recalculate semester GPA
            SemesterGPA.calculate_semester_gpa(student, semester)
            
            # Recalculate CGPA
            StudentCGPA.calculate_cgpa(student)
            
            return CourseGradeMutationResponse(
                success=True,
                message="Grade created successfully",
                grade=grade
            )
            
        except StudentProfile.DoesNotExist:
            return CourseGradeMutationResponse(
                success=False,
                message="Student not found",
                grade=None
            )
        except Subject.DoesNotExist:
            return CourseGradeMutationResponse(
                success=False,
                message="Subject not found",
                grade=None
            )
        except Semester.DoesNotExist:
            return CourseGradeMutationResponse(
                success=False,
                message="Semester not found",
                grade=None
            )
        except Exception as e:
            return CourseGradeMutationResponse(
                success=False,
                message=f"Error creating grade: {str(e)}",
                grade=None
            )
    
    @strawberry.mutation
    @require_auth
    def update_course_grade(
        self,
        info: Info,
        grade_id: int,
        input: CourseGradeInput
    ) -> CourseGradeMutationResponse:
        """
        Update an existing course grade (Faculty/Admin only)
        """
        user = info.context.request.user
        
        # Check permissions
        if user.role.code not in ['FACULTY', 'ADMIN', 'HOD']:
            return CourseGradeMutationResponse(
                success=False,
                message="Only faculty and admins can update grades",
                grade=None
            )
        
        try:
            grade = CourseGrade.objects.get(id=grade_id)
            
            # Update fields
            grade.internal_marks = input.internal_marks
            grade.internal_max_marks = input.internal_max_marks
            grade.exam_marks = input.exam_marks
            grade.exam_max_marks = input.exam_max_marks
            grade.exam_type = input.exam_type
            grade.exam_date = input.exam_date
            grade.remarks = input.remarks or ""
            grade.is_published = input.is_published
            grade.graded_by = user
            
            grade.save()
            
            # Recalculate semester GPA
            SemesterGPA.calculate_semester_gpa(grade.student, grade.semester)
            
            # Recalculate CGPA
            StudentCGPA.calculate_cgpa(grade.student)
            
            return CourseGradeMutationResponse(
                success=True,
                message="Grade updated successfully",
                grade=grade
            )
            
        except CourseGrade.DoesNotExist:
            return CourseGradeMutationResponse(
                success=False,
                message="Grade not found",
                grade=None
            )
        except Exception as e:
            return CourseGradeMutationResponse(
                success=False,
                message=f"Error updating grade: {str(e)}",
                grade=None
            )
    
    @strawberry.mutation
    @require_auth
    def publish_grade(
        self,
        info: Info,
        grade_id: int
    ) -> CourseGradeMutationResponse:
        """
        Publish a grade to make it visible to student
        """
        user = info.context.request.user
        
        # Check permissions
        if user.role.code not in ['FACULTY', 'ADMIN', 'HOD']:
            return CourseGradeMutationResponse(
                success=False,
                message="Only faculty and admins can publish grades",
                grade=None
            )
        
        try:
            grade = CourseGrade.objects.get(id=grade_id)
            grade.is_published = True
            grade.save()
            
            return CourseGradeMutationResponse(
                success=True,
                message="Grade published successfully",
                grade=grade
            )
            
        except CourseGrade.DoesNotExist:
            return CourseGradeMutationResponse(
                success=False,
                message="Grade not found",
                grade=None
            )
