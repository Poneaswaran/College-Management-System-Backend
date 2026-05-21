from django.db import models
from django.core.validators import MinValueValidator
from core.models import BaseModel


def company_logo_path(instance, filename):
    return f"placement/companies/{instance.id or 'new'}/logos/{filename}"


def application_resume_path(instance, filename):
    return f"placement/applications/{instance.student_id}/{instance.drive_id}/{filename}"


def offer_letter_path(instance, filename):
    return f"placement/offers/{instance.application_id}/{filename}"


def student_resume_path(instance, filename):
    return f"placement/students/{instance.student_id}/resume/{filename}"


class Company(BaseModel):
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to=company_logo_path, null=True, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    package_range = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name", "is_active"], name="placement_company_active_idx"),
        ]

    def __str__(self):
        return self.name


class PlacementDrive(BaseModel):
    DRIVE_TYPE_CHOICES = [
        ("on_campus", "On Campus"),
        ("off_campus", "Off Campus"),
        ("pool", "Pool"),
    ]

    STATUS_CHOICES = [
        ("upcoming", "Upcoming"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="drives",
    )
    title = models.CharField(max_length=255)
    drive_type = models.CharField(max_length=20, choices=DRIVE_TYPE_CHOICES)
    job_role = models.CharField(max_length=255)
    job_description = models.TextField()
    required_skills = models.TextField(blank=True)
    min_cgpa = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    eligible_branches = models.ManyToManyField(
        "core.Department",
        related_name="placement_drives",
        blank=True,
    )
    eligible_batch_year = models.PositiveIntegerField()
    application_deadline = models.DateTimeField()
    drive_date = models.DateTimeField()
    venue = models.CharField(max_length=255, blank=True)
    package_offered = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    bond_years = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="upcoming",
        db_index=True,
    )

    class Meta:
        ordering = ["-drive_date"]
        indexes = [
            models.Index(fields=["status", "drive_type"], name="placement_drive_status_type_idx"),
            models.Index(fields=["eligible_batch_year", "min_cgpa"], name="placement_drive_batch_cgpa_idx"),
            models.Index(fields=["application_deadline"], name="placement_drive_deadline_idx"),
        ]

    def __str__(self):
        return f"{self.title} - {self.company.name}"


class StudentApplication(BaseModel):
    STATUS_CHOICES = [
        ("applied", "Applied"),
        ("shortlisted", "Shortlisted"),
        ("interviewed", "Interviewed"),
        ("selected", "Selected"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
    ]

    student = models.ForeignKey(
        "profile_management.StudentProfile",
        on_delete=models.CASCADE,
        related_name="placement_applications",
    )
    drive = models.ForeignKey(
        PlacementDrive,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    resume = models.FileField(upload_to=application_resume_path, null=True, blank=True)
    cover_letter = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="applied",
        db_index=True,
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-applied_at"]
        unique_together = ("student", "drive")
        indexes = [
            models.Index(fields=["status", "drive"], name="placement_app_status_drive_idx"),
            models.Index(fields=["student", "status"], name="placement_app_student_status_idx"),
        ]

    def __str__(self):
        return f"{self.student.register_number} - {self.drive.title}"


class PlacementRound(BaseModel):
    ROUND_TYPE_CHOICES = [
        ("aptitude", "Aptitude"),
        ("technical", "Technical"),
        ("hr", "HR"),
        ("group_discussion", "Group Discussion"),
        ("final", "Final"),
    ]

    drive = models.ForeignKey(
        PlacementDrive,
        on_delete=models.CASCADE,
        related_name="rounds",
    )
    round_number = models.PositiveIntegerField()
    round_type = models.CharField(max_length=30, choices=ROUND_TYPE_CHOICES)
    scheduled_at = models.DateTimeField()
    venue = models.CharField(max_length=255, blank=True)
    instructions = models.TextField(blank=True)

    class Meta:
        ordering = ["round_number"]
        unique_together = ("drive", "round_number")
        indexes = [
            models.Index(fields=["drive", "round_number"], name="placement_round_drive_num_idx"),
        ]

    def __str__(self):
        return f"{self.drive.title} - Round {self.round_number}"


class RoundResult(BaseModel):
    RESULT_CHOICES = [
        ("pass", "Pass"),
        ("fail", "Fail"),
        ("pending", "Pending"),
    ]

    application = models.ForeignKey(
        StudentApplication,
        on_delete=models.CASCADE,
        related_name="round_results",
    )
    round = models.ForeignKey(
        PlacementRound,
        on_delete=models.CASCADE,
        related_name="results",
    )
    result = models.CharField(
        max_length=10,
        choices=RESULT_CHOICES,
        default="pending",
    )
    interviewer_notes = models.TextField(blank=True)
    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        unique_together = ("application", "round")
        indexes = [
            models.Index(fields=["round", "result"], name="placement_result_round_idx"),
        ]

    def __str__(self):
        return f"{self.application} - {self.round} ({self.result})"


class PlacementOffer(BaseModel):
    application = models.OneToOneField(
        StudentApplication,
        on_delete=models.CASCADE,
        related_name="offer",
    )
    offer_letter = models.FileField(upload_to=offer_letter_path, null=True, blank=True)
    ctc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    joining_date = models.DateField()
    location = models.CharField(max_length=255, blank=True)
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Offer for {self.application}"


class StudentPlacementProfile(BaseModel):
    student = models.OneToOneField(
        "profile_management.StudentProfile",
        on_delete=models.CASCADE,
        related_name="placement_profile",
    )
    resume = models.FileField(upload_to=student_resume_path, null=True, blank=True)
    skills = models.JSONField(default=list, blank=True)
    portfolio_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    is_placed = models.BooleanField(default=False)
    placed_company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="placed_students",
    )
    placed_package = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        ordering = ["student__register_number"]

    def __str__(self):
        return f"Placement Profile - {self.student.register_number}"
