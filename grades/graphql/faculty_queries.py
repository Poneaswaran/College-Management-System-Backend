"""
GraphQL Queries for Faculty Grade Submission
Implements facultyGrades and facultyGradeDetail queries
"""
import strawberry
from typing import Optional
from strawberry.types import Info
from django.db.models import Q, Count
from django.utils import timezone

from grades.models import CourseSectionAssignment, GradeBatch, GradeEntry
from profile_management.models import FacultyProfile, Semester, StudentProfile
from grades.graphql.faculty_types import (
    FacultyGradesData,
    FacultyGradeSummary,
    GradeCourseSection,
    GradeStatus,
    GradeExamType,
    FacultyGradeDetailData,
    CourseSectionGradeStats,
    StudentGradeRecord,
    LetterGrade,
    GradeDistributionItem,
)


def _derive_letter_grade(pct: Optional[float], is_absent: bool) -> Optional[LetterGrade]:
    """Convert percentage to letter grade"""
    if is_absent:
        return LetterGrade.ABSENT
    if pct is None:
        return None
    if pct >= 91:
        return LetterGrade.O
    if pct >= 81:
        return LetterGrade.A_PLUS
    if pct >= 71:
        return LetterGrade.A
    if pct >= 61:
        return LetterGrade.B_PLUS
    if pct >= 51:
        return LetterGrade.B
    if pct >= 41:
        return LetterGrade.C
    return LetterGrade.F


def _derive_grade_point(grade: Optional[LetterGrade]) -> Optional[float]:
    """Convert letter grade to grade point"""
    if grade is None:
        return None
    grade_map = {
        LetterGrade.O: 10.0,
        LetterGrade.A_PLUS: 9.0,
        LetterGrade.A: 8.0,
        LetterGrade.B_PLUS: 7.0,
        LetterGrade.B: 6.0,
        LetterGrade.C: 5.0,
        LetterGrade.F: 0.0,
        LetterGrade.ABSENT: 0.0,
        LetterGrade.WITHHELD: 0.0,
    }
    return grade_map.get(grade)


def _build_media_url(file_field, request) -> Optional[str]:
    """Build full media URL from file field"""
    if not file_field:
        return None
    try:
        return request.build_absolute_uri(file_field.url)
    except:
        return None


def _build_grade_course_section(assignment, grade_batch) -> GradeCourseSection:
    """Convert CourseSectionAssignment to GradeCourseSection type"""
    status = GradeStatus(grade_batch.status) if grade_batch else GradeStatus.DRAFT
    submitted_count = 0
    last_modified_at = None
    submitted_at = None
    
    if grade_batch:
        submitted_count = grade_batch.grade_entries.exclude(
            internal_mark=None, external_mark=None
        ).count()
        last_modified_at = grade_batch.updated_at.isoformat() if grade_batch.updated_at else None
        submitted_at = grade_batch.submitted_at.isoformat() if grade_batch.submitted_at else None
    
    semester = assignment.semester
    internal_max = assignment.exam_config.internal_max_mark
    external_max = assignment.exam_config.external_max_mark
    
    return GradeCourseSection(
        id=assignment.id,
        subject_code=assignment.subject.code,
        subject_name=assignment.subject.name,
        section_name=assignment.section.name,
        semester=semester.number,
        semester_label=f"Semester {semester.number} — {semester.academic_year.year_code}",
        department=assignment.section.department.name,
        exam_type=GradeExamType(assignment.exam_config.exam_type),
        exam_date=assignment.exam_config.exam_date.isoformat(),
        internal_max_mark=internal_max,
        external_max_mark=external_max,
        total_max_mark=internal_max + external_max,
        pass_mark=assignment.exam_config.pass_mark,
        student_count=assignment.section.student_profiles.filter(is_active=True).count(),
        submitted_count=submitted_count,
        status=status,
        last_modified_at=last_modified_at,
        submitted_at=submitted_at,
    )


def _build_grade_stats(student_records: list[StudentGradeRecord], total_max: int) -> CourseSectionGradeStats:
    """Calculate statistics from student grade records"""
    total_students = len(student_records)
    pass_count = sum(1 for r in student_records if r.is_pass is True)
    fail_count = sum(1 for r in student_records if r.is_pass is False and not r.is_absent)
    absent_count = sum(1 for r in student_records if r.is_absent)
    
    pass_percentage = round((pass_count / total_students * 100), 2) if total_students > 0 else 0.0
    
    # Calculate mark statistics (exclude absent students)
    marks = [r.total_mark for r in student_records if r.total_mark is not None and not r.is_absent]
    avg_mark = round(sum(marks) / len(marks), 2) if marks else 0.0
    highest_mark = max(marks) if marks else 0.0
    lowest_mark = min(marks) if marks else 0.0
    
    # Grade distribution
    grade_counts = {}
    for record in student_records:
        if record.letter_grade:
            grade_counts[record.letter_grade] = grade_counts.get(record.letter_grade, 0) + 1
    
    grade_distribution = [
        GradeDistributionItem(
            grade=grade,
            count=count,
            percentage=round((count / total_students * 100), 2)
        )
        for grade, count in sorted(grade_counts.items(), key=lambda x: _derive_grade_point(x[0]) or 0, reverse=True)
    ]
    
    return CourseSectionGradeStats(
        total_students=total_students,
        pass_count=pass_count,
        fail_count=fail_count,
        absent_count=absent_count,
        pass_percentage=pass_percentage,
        avg_mark=avg_mark,
        highest_mark=highest_mark,
        lowest_mark=lowest_mark,
        grade_distribution=grade_distribution,
    )


@strawberry.type
class FacultyGradesQuery:
    @strawberry.field
    def faculty_grades(
        self,
        info: Info,
        semester_id: Optional[int] = None,
    ) -> FacultyGradesData:
        """
        Returns all course sections the authenticated faculty member is
        assigned to, with grade submission status for the given semester.
        """
        faculty_user = info.context.request.user
        
        # Get faculty profile
        try:
            faculty = FacultyProfile.objects.get(user=faculty_user)
        except FacultyProfile.DoesNotExist:
            raise ValueError("Faculty profile not found for the authenticated user.")
        
        # Determine semester
        if semester_id:
            try:
                semester = Semester.objects.get(id=semester_id)
            except Semester.DoesNotExist:
                raise ValueError(f"Semester with id {semester_id} not found.")
        else:
            try:
                semester = Semester.objects.get(is_current=True)
            except Semester.DoesNotExist:
                raise ValueError("No current semester found.")
        
        # Fetch all course section assignments for this faculty
        assignments = CourseSectionAssignment.objects.filter(
            faculty=faculty,
            semester=semester,
            is_active=True,
        ).select_related(
            'subject', 'section', 'section__department', 'semester', 
            'semester__academic_year', 'exam_config'
        ).order_by('subject__code')
        
        course_sections = []
        total_submitted = 0
        total_draft = 0
        total_approved = 0
        total_rejected = 0
        total_pending = 0
        
        for assignment in assignments:
            grade_batch = GradeBatch.objects.filter(
                course_section_assignment=assignment,
            ).first()
            
            course_section = _build_grade_course_section(assignment, grade_batch)
            course_sections.append(course_section)
            
            # Accumulate summary counts
            status = course_section.status
            if status == GradeStatus.DRAFT:
                total_draft += 1
            elif status == GradeStatus.SUBMITTED:
                total_pending += 1
            elif status == GradeStatus.APPROVED:
                total_approved += 1
            elif status == GradeStatus.REJECTED:
                total_rejected += 1
            
            if status != GradeStatus.DRAFT:
                total_submitted += 1
        
        summary = FacultyGradeSummary(
            total_courses=len(course_sections),
            total_submitted=total_submitted,
            total_draft=total_draft,
            total_pending_approval=total_pending,
            total_approved=total_approved,
            total_rejected=total_rejected,
            current_semester_label=f"Semester {semester.number} — {semester.academic_year.year_code}",
        )
        
        return FacultyGradesData(summary=summary, course_sections=course_sections)
    
    @strawberry.field
    def faculty_grade_detail(
        self,
        info: Info,
        course_section_id: int,
    ) -> FacultyGradeDetailData:
        """
        Returns the complete grade sheet for a course section assignment —
        including per-student marks, derived grades, and aggregate stats.
        Only accessible by the faculty assigned to this course section.
        """
        faculty_user = info.context.request.user
        
        # Get assignment with ownership check
        try:
            assignment = CourseSectionAssignment.objects.select_related(
                'faculty', 'faculty__user', 'subject', 'section', 'section__department',
                'semester', 'semester__academic_year', 'exam_config'
            ).get(
                id=course_section_id,
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
        
        # Get all students in the section
        students = StudentProfile.objects.filter(
            section=assignment.section,
            is_active=True,
        ).select_related('user').order_by('roll_number')
        
        # Get existing grade entries
        grade_map = {
            ge.student_id: ge
            for ge in GradeEntry.objects.filter(grade_batch=grade_batch)
        }
        
        internal_max = assignment.exam_config.internal_max_mark
        external_max = assignment.exam_config.external_max_mark
        total_max = internal_max + external_max
        
        # Build student records
        student_records = []
        for student in students:
            ge = grade_map.get(student.id)
            is_absent = ge.is_absent if ge else False
            internal = ge.internal_mark if ge and not is_absent else None
            external = ge.external_mark if ge and not is_absent else None
            
            # Calculate derived fields
            total = None
            pct = None
            if not is_absent and internal is not None and external is not None:
                total = internal + external
                pct = round((total / total_max) * 100, 2) if total_max > 0 else 0.0
            
            letter = _derive_letter_grade(pct, is_absent)
            gp = _derive_grade_point(letter)
            is_pass_val = None
            if letter is not None:
                is_pass_val = letter not in (LetterGrade.F, LetterGrade.ABSENT, LetterGrade.WITHHELD)
            
            student_records.append(StudentGradeRecord(
                student_id=str(student.id),
                register_number=student.register_number,
                roll_number=student.roll_number or "",
                student_name=student.full_name,
                profile_photo=_build_media_url(student.profile_photo, info.context.request),
                internal_mark=internal,
                external_mark=external,
                total_mark=total,
                percentage=pct,
                letter_grade=letter,
                grade_point=gp,
                is_pass=is_pass_val,
                is_absent=is_absent,
            ))
        
        stats = _build_grade_stats(student_records, total_max)
        course_section = _build_grade_course_section(assignment, grade_batch)
        
        return FacultyGradeDetailData(
            course_section=course_section,
            stats=stats,
            students=student_records,
        )
