from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from core.models import Department, Course, Section


# ==================================================
# ACADEMIC YEAR & SEMESTER
# ==================================================

class AcademicYear(models.Model):
    """
    Track academic sessions like '2024-25', '2025-26'
    Only one academic year can be current at a time
    """
    year_code = models.CharField(max_length=20, unique=True, help_text="e.g., '2024-25'")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, help_text="Only one academic year can be current")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Academic Year"
        verbose_name_plural = "Academic Years"

    def __str__(self):
        return self.year_code

    def clean(self):
        """Validate that start_date is before end_date"""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date")

    def save(self, *args, **kwargs):
        """Ensure only one academic year is current at a time"""
        if self.is_current:
            # Set all other academic years to not current
            AcademicYear.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class Semester(models.Model):
    """
    Represent Odd (1) or Even (2) semester within an academic year
    Only one semester can be current at a time
    """
    SEMESTER_CHOICES = [
        (1, 'Odd Semester'),
        (2, 'Even Semester'),
    ]

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="semesters"
    )
    number = models.PositiveIntegerField(
        choices=SEMESTER_CHOICES,
        help_text="1 = Odd Semester, 2 = Even Semester"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, help_text="Only one semester can be current")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('academic_year', 'number')
        ordering = ['-academic_year__start_date', 'number']
        verbose_name = "Semester"
        verbose_name_plural = "Semesters"

    def __str__(self):
        return f"{self.academic_year.year_code} - {self.get_number_display()}"

    def clean(self):
        """Validate that start_date is before end_date"""
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date")

    def save(self, *args, **kwargs):
        """Ensure only one semester is current at a time"""
        if self.is_current:
            # Set all other semesters to not current
            Semester.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


# ==================================================
# STUDENT PROFILE
# ==================================================

class StudentProfile(models.Model):
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other'),
    ]
    
    ACADEMIC_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('PASSED', 'Passed'),
        ('DROPPED', 'Dropped'),
    ]
    
    ID_PROOF_CHOICES = [
        ('AADHAR', 'Aadhar Card'),
        ('PAN', 'PAN Card'),
        ('DRIVING_LICENSE', 'Driving License'),
        ('PASSPORT', 'Passport'),
    ]

    # OneToOne relation with User
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile"
    )

    # ==================================================
    # BASIC PERSONAL INFORMATION (Editable by Student)
    # ==================================================
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=15)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    profile_photo = models.ImageField(upload_to='student_profiles/', null=True, blank=True)

    # ==================================================
    # ACADEMIC INFORMATION (Read-Only for Student)
    # ==================================================
    register_number = models.CharField(max_length=20, unique=True)
    roll_number = models.CharField(max_length=20, null=True, blank=True)
    
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="student_profiles"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="student_profiles"
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="student_profiles"
    )
    
    year = models.PositiveIntegerField(default=1)  # 1, 2, 3, 4
    semester = models.PositiveIntegerField(default=1)  # 1-8
    admission_date = models.DateField(null=True, blank=True)
    academic_status = models.CharField(
        max_length=20,
        choices=ACADEMIC_STATUS_CHOICES,
        default='ACTIVE'
    )

    # ==================================================
    # GUARDIAN / PARENT DETAILS (Editable by Student)
    # ==================================================
    guardian_name = models.CharField(max_length=100, null=True, blank=True)
    guardian_relationship = models.CharField(max_length=50, null=True, blank=True)
    guardian_phone = models.CharField(max_length=15, null=True, blank=True)
    guardian_email = models.EmailField(null=True, blank=True)

    # ==================================================
    # IDENTIFICATION & GOVERNMENT DETAILS (Admin Only)
    # ==================================================
    aadhar_number = models.CharField(max_length=12, null=True, blank=True)
    id_proof_type = models.CharField(
        max_length=20,
        choices=ID_PROOF_CHOICES,
        null=True,
        blank=True
    )
    id_proof_number = models.CharField(max_length=50, null=True, blank=True)

    # ==================================================
    # SYSTEM & META FIELDS
    # ==================================================
    is_active = models.BooleanField(default=True)
    profile_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['register_number']),
            models.Index(fields=['academic_status']),
        ]

    def __str__(self):
        return f"{self.register_number} - {self.first_name} {self.last_name or ''}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name or ''}".strip()


# ==================================================
# PARENT / GUARDIAN PROFILE
# ==================================================

class ParentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_profile"
    )

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="parents"
    )

    relationship = models.CharField(max_length=50)  # Father, Mother, Guardian
    phone_number = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.relationship} of {self.student.register_number}"


# ==================================================
# PARENT LOGIN OTP (temporary codes for parent auth)
# ==================================================

class ParentLoginOTP(models.Model):
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='parent_otps'
    )
    code = models.CharField(max_length=10)
    contact = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'code']),
        ]

    def __str__(self):
        return f"OTP for {self.student.register_number} -> {self.code} ({'used' if self.used else 'active'})"
