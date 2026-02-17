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

