"""
Grades Models for College Management System
Tracks semester-wise course grades, GPA, and CGPA
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from decimal import Decimal


class CourseGrade(models.Model):
    """
    Represents final grade for a course in a specific semester
    Combines internal marks, assignment grades, and final exam marks
    """
    
    GRADE_CHOICES = [
        ('A+', 'A+ (90-100%)'),
        ('A', 'A (80-89%)'),
        ('B+', 'B+ (70-79%)'),
        ('B', 'B (60-69%)'),
        ('C', 'C (50-59%)'),
        ('D', 'D (40-49%)'),
        ('F', 'F (Below 40%)'),
        ('I', 'Incomplete'),
        ('W', 'Withdrawn'),
    ]
    
    EXAM_TYPE_CHOICES = [
        ('MIDTERM', 'Midterm Exam'),
        ('FINAL', 'Final Exam'),
        ('BOTH', 'Midterm + Final'),
    ]
    
    # Core References
    student = models.ForeignKey(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='course_grades',
        help_text="Student who received this grade"
    )
    subject = models.ForeignKey(
        'timetable.Subject',
        on_delete=models.CASCADE,
        related_name='course_grades',
        help_text="Subject for which grade is assigned"
    )
    semester = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='course_grades',
        help_text="Academic semester"
    )
    
    # Marks Breakdown
    internal_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Internal assessment marks (assignments, quizzes, etc.)"
    )
    internal_max_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=40,
        help_text="Maximum internal marks"
    )
    
    exam_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Final exam marks"
    )
    exam_max_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=60,
        help_text="Maximum exam marks"
    )
    
    exam_type = models.CharField(
        max_length=20,
        choices=EXAM_TYPE_CHOICES,
        default='FINAL',
        help_text="Type of exam"
    )
    exam_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of final exam"
    )
    
    # Final Grade
    total_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Total marks obtained"
    )
    total_max_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        help_text="Total maximum marks"
    )
    
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage scored"
    )
    
    grade = models.CharField(
        max_length=2,
        choices=GRADE_CHOICES,
        help_text="Letter grade"
    )
    
    grade_points = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        help_text="Grade points (for GPA calculation)"
    )
    
    # Additional Info
    credits = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        help_text="Course credits"
    )
    
    remarks = models.TextField(
        blank=True,
        help_text="Additional remarks or comments"
    )
    
    is_published = models.BooleanField(
        default=False,
        help_text="Whether grade is published to student"
    )
    
    # Metadata
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_course_grades',
        help_text="Faculty who assigned the grade"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-semester__start_date', 'subject__code']
        verbose_name = "Course Grade"
        verbose_name_plural = "Course Grades"
        unique_together = [['student', 'subject', 'semester']]
        indexes = [
            models.Index(fields=['student', 'semester']),
            models.Index(fields=['semester', 'is_published']),
        ]
    
    def __str__(self):
        return f"{self.student.register_number} - {self.subject.code} - {self.grade}"
    
    def clean(self):
        """Validate grade data"""
        if self.internal_marks is not None and self.internal_max_marks is not None:
            if self.internal_marks > self.internal_max_marks:
                raise ValidationError("Internal marks cannot exceed maximum")
        
        if self.exam_marks is not None and self.exam_max_marks is not None:
            if self.exam_marks > self.exam_max_marks:
                raise ValidationError("Exam marks cannot exceed maximum")
        
        if self.total_marks is not None and self.total_max_marks is not None:
            if self.total_marks > self.total_max_marks:
                raise ValidationError("Total marks cannot exceed maximum")
    
    def save(self, *args, **kwargs):
        """Calculate total marks, percentage, grade, and grade points before saving"""
        # Calculate totals
        self.total_marks = self.internal_marks + self.exam_marks
        self.total_max_marks = self.internal_max_marks + self.exam_max_marks
        
        # Calculate percentage
        if self.total_max_marks > 0:
            self.percentage = (self.total_marks / self.total_max_marks) * 100
        else:
            self.percentage = 0
        
        # Determine grade and grade points
        if self.percentage >= 90:
            self.grade = 'A+'
            self.grade_points = Decimal('10.0')
        elif self.percentage >= 80:
            self.grade = 'A'
            self.grade_points = Decimal('9.0')
        elif self.percentage >= 70:
            self.grade = 'B+'
            self.grade_points = Decimal('8.0')
        elif self.percentage >= 60:
            self.grade = 'B'
            self.grade_points = Decimal('7.0')
        elif self.percentage >= 50:
            self.grade = 'C'
            self.grade_points = Decimal('6.0')
        elif self.percentage >= 40:
            self.grade = 'D'
            self.grade_points = Decimal('5.0')
        else:
            self.grade = 'F'
            self.grade_points = Decimal('0.0')
        
        # Set credits from subject
        if not self.credits:
            self.credits = self.subject.credits
        
        super().save(*args, **kwargs)


class SemesterGPA(models.Model):
    """
    Calculated GPA for a student for a specific semester
    """
    student = models.ForeignKey(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='semester_gpas',
        help_text="Student"
    )
    semester = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='semester_gpas',
        help_text="Academic semester"
    )
    
    gpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        help_text="Semester GPA"
    )
    
    total_credits = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        help_text="Total credits for the semester"
    )
    
    credits_earned = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        help_text="Credits earned (passed courses)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-semester__start_date']
        verbose_name = "Semester GPA"
        verbose_name_plural = "Semester GPAs"
        unique_together = [['student', 'semester']]
    
    def __str__(self):
        return f"{self.student.register_number} - {self.semester} - GPA: {self.gpa}"
    
    @classmethod
    def calculate_semester_gpa(cls, student, semester):
        """Calculate GPA for a student in a specific semester"""
        grades = CourseGrade.objects.filter(
            student=student,
            semester=semester,
            is_published=True
        )
        
        if not grades.exists():
            return None
        
        total_points = Decimal('0')
        total_credits = Decimal('0')
        credits_earned = Decimal('0')
        
        for grade in grades:
            credit_points = grade.grade_points * grade.credits
            total_points += credit_points
            total_credits += grade.credits
            
            if grade.grade not in ['F', 'I', 'W']:
                credits_earned += grade.credits
        
        if total_credits > 0:
            gpa = total_points / total_credits
        else:
            gpa = Decimal('0')
        
        # Create or update SemesterGPA
        semester_gpa, created = cls.objects.update_or_create(
            student=student,
            semester=semester,
            defaults={
                'gpa': gpa,
                'total_credits': total_credits,
                'credits_earned': credits_earned
            }
        )
        
        return semester_gpa


class StudentCGPA(models.Model):
    """
    Cumulative GPA (CGPA) for a student across all semesters
    """
    student = models.OneToOneField(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='cgpa_record',
        help_text="Student"
    )
    
    cgpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        help_text="Cumulative GPA"
    )
    
    total_credits = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        help_text="Total credits across all semesters"
    )
    
    credits_earned = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        help_text="Total credits earned (passed courses)"
    )
    
    performance_trend = models.CharField(
        max_length=20,
        choices=[
            ('IMPROVING', 'Improving'),
            ('STABLE', 'Stable'),
            ('DECLINING', 'Declining'),
        ],
        default='STABLE',
        help_text="Performance trend based on recent semesters"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Student CGPA"
        verbose_name_plural = "Student CGPAs"
    
    def __str__(self):
        return f"{self.student.register_number} - CGPA: {self.cgpa}"
    
    @classmethod
    def calculate_cgpa(cls, student):
        """Calculate CGPA for a student across all semesters"""
        semester_gpas = SemesterGPA.objects.filter(student=student).order_by('semester__start_date')
        
        if not semester_gpas.exists():
            return None
        
        total_points = Decimal('0')
        total_credits = Decimal('0')
        total_credits_earned = Decimal('0')
        
        for sem_gpa in semester_gpas:
            total_points += (sem_gpa.gpa * sem_gpa.total_credits)
            total_credits += sem_gpa.total_credits
            total_credits_earned += sem_gpa.credits_earned
        
        if total_credits > 0:
            cgpa = total_points / total_credits
        else:
            cgpa = Decimal('0')
        
        # Determine performance trend (compare last 2 semesters)
        performance_trend = 'STABLE'
        if semester_gpas.count() >= 2:
            recent_gpas = list(semester_gpas.values_list('gpa', flat=True))[-2:]
            if recent_gpas[1] > recent_gpas[0] + Decimal('0.5'):
                performance_trend = 'IMPROVING'
            elif recent_gpas[1] < recent_gpas[0] - Decimal('0.5'):
                performance_trend = 'DECLINING'
        
        # Create or update StudentCGPA
        student_cgpa, created = cls.objects.update_or_create(
            student=student,
            defaults={
                'cgpa': cgpa,
                'total_credits': total_credits,
                'credits_earned': total_credits_earned,
                'performance_trend': performance_trend
            }
        )
        
        return student_cgpa


# ==================================================
# FACULTY GRADE SUBMISSION MODELS
# ==================================================

class ExamConfig(models.Model):
    """
    Configuration for exam marks structure
    Defines maximum marks for internal and external components
    """
    EXAM_TYPE_CHOICES = [
        ('INTERNAL', 'Internal Assessment'),
        ('EXTERNAL', 'External Exam'),
        ('QUIZ', 'Quiz'),
        ('LAB', 'Lab Exam'),
        ('ASSIGNMENT', 'Assignment'),
    ]
    
    exam_type = models.CharField(
        max_length=20,
        choices=EXAM_TYPE_CHOICES,
        default='INTERNAL',
        help_text="Type of examination"
    )
    exam_date = models.DateField(
        help_text="Date of the exam"
    )
    internal_max_mark = models.IntegerField(
        default=40,
        help_text="Maximum marks for internal assessment"
    )
    external_max_mark = models.IntegerField(
        default=60,
        help_text="Maximum marks for external exam"
    )
    pass_mark = models.IntegerField(
        default=40,
        help_text="Minimum marks required to pass"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Exam Configuration"
        verbose_name_plural = "Exam Configurations"
    
    def __str__(self):
        return f"{self.get_exam_type_display()} - I:{self.internal_max_mark}/E:{self.external_max_mark}"
    
    @property
    def total_max_mark(self):
        return self.internal_max_mark + self.external_max_mark


class CourseSectionAssignment(models.Model):
    """
    Links a faculty member to a subject + section for grade submission
    Represents one course section that a faculty teaches
    """
    faculty = models.ForeignKey(
        'profile_management.FacultyProfile',
        on_delete=models.CASCADE,
        related_name='course_assignments',
        help_text="Faculty member assigned to teach"
    )
    subject = models.ForeignKey(
        'timetable.Subject',
        on_delete=models.CASCADE,
        related_name='course_assignments',
        help_text="Subject being taught"
    )
    section = models.ForeignKey(
        'core.Section',
        on_delete=models.CASCADE,
        related_name='course_assignments',
        help_text="Section being taught"
    )
    semester = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='course_assignments',
        help_text="Academic semester"
    )
    exam_config = models.ForeignKey(
        ExamConfig,
        on_delete=models.CASCADE,
        related_name='course_assignments',
        help_text="Exam configuration for this course section"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('faculty', 'subject', 'section', 'semester')]
        verbose_name = "Course Section Assignment"
        verbose_name_plural = "Course Section Assignments"
        indexes = [
            models.Index(fields=['faculty', 'semester']),
            models.Index(fields=['section', 'semester']),
        ]
    
    def __str__(self):
        return f"{self.faculty.full_name} - {self.subject.code} - {self.section.name}"


class GradeBatch(models.Model):
    """
    Tracks the submission lifecycle of grades for one course section assignment
    One batch per faculty + subject + section + semester
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    course_section_assignment = models.OneToOneField(
        CourseSectionAssignment,
        on_delete=models.CASCADE,
        related_name='grade_batch',
        help_text="Course section this batch belongs to"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        help_text="Current submission status"
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When grades were submitted for approval"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last modification timestamp"
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection (if applicable)"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_grade_batches',
        help_text="HOD/Admin who approved"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When grades were approved"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Grade Batch"
        verbose_name_plural = "Grade Batches"
        indexes = [
            models.Index(fields=['status', 'submitted_at']),
        ]
    
    def __str__(self):
        return f"{self.course_section_assignment} - {self.get_status_display()}"


class GradeEntry(models.Model):
    """
    Individual student grade record within a grade batch
    Stores raw marks; letter grades and points are computed
    """
    grade_batch = models.ForeignKey(
        GradeBatch,
        on_delete=models.CASCADE,
        related_name='grade_entries',
        help_text="Parent batch"
    )
    student = models.ForeignKey(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='grade_entries',
        help_text="Student receiving the grade"
    )
    
    # Raw marks (input by faculty)
    internal_mark = models.FloatField(
        null=True,
        blank=True,
        help_text="Internal assessment marks"
    )
    external_mark = models.FloatField(
        null=True,
        blank=True,
        help_text="External exam marks"
    )
    is_absent = models.BooleanField(
        default=False,
        help_text="Student was absent for the exam"
    )
    
    # Computed fields (derived from marks)
    total_mark = models.FloatField(
        null=True,
        blank=True,
        help_text="Total marks (internal + external)"
    )
    percentage = models.FloatField(
        null=True,
        blank=True,
        help_text="Percentage scored"
    )
    letter_grade = models.CharField(
        max_length=10,
        blank=True,
        help_text="Letter grade (O, A+, A, B+, B, C, F, ABSENT, WITHHELD)"
    )
    grade_point = models.FloatField(
        null=True,
        blank=True,
        help_text="Grade point (0-10 scale)"
    )
    is_pass = models.BooleanField(
        null=True,
        help_text="Whether student passed"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [('grade_batch', 'student')]
        verbose_name = "Grade Entry"
        verbose_name_plural = "Grade Entries"
        indexes = [
            models.Index(fields=['grade_batch', 'student']),
            models.Index(fields=['letter_grade']),
        ]
    
    def __str__(self):
        return f"{self.student.register_number} - {self.letter_grade or 'Pending'}"
    
    def compute_derived_fields(self):
        """
        Compute total_mark, percentage, letter_grade, grade_point, is_pass
        Based on the 10-point GPA scale (Anna University pattern)
        """
        if self.is_absent:
            self.total_mark = None
            self.percentage = None
            self.letter_grade = 'ABSENT'
            self.grade_point = 0.0
            self.is_pass = False
            return
        
        if self.internal_mark is None or self.external_mark is None:
            return  # Not yet complete
        
        # Calculate total and percentage
        self.total_mark = self.internal_mark + self.external_mark
        exam_config = self.grade_batch.course_section_assignment.exam_config
        total_max = exam_config.total_max_mark
        
        if total_max > 0:
            self.percentage = round((self.total_mark / total_max) * 100, 2)
        else:
            self.percentage = 0.0
        
        # Derive letter grade and grade point
        pct = self.percentage
        if pct >= 91:
            self.letter_grade = 'O'
            self.grade_point = 10.0
            self.is_pass = True
        elif pct >= 81:
            self.letter_grade = 'A+'
            self.grade_point = 9.0
            self.is_pass = True
        elif pct >= 71:
            self.letter_grade = 'A'
            self.grade_point = 8.0
            self.is_pass = True
        elif pct >= 61:
            self.letter_grade = 'B+'
            self.grade_point = 7.0
            self.is_pass = True
        elif pct >= 51:
            self.letter_grade = 'B'
            self.grade_point = 6.0
            self.is_pass = True
        elif pct >= 41:
            self.letter_grade = 'C'
            self.grade_point = 5.0
            self.is_pass = True
        else:
            self.letter_grade = 'F'
            self.grade_point = 0.0
            self.is_pass = False
    
    def save(self, *args, **kwargs):
        """Automatically compute derived fields when saving"""
        self.compute_derived_fields()
        super().save(*args, **kwargs)
