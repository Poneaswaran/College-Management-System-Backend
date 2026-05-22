import os
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import BaseModel

# File Upload Path Functions
def company_logo_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4()}{ext}"
    company_id = instance.id or "new"
    return f"placement/companies/{company_id}/logos/{unique_name}"


def application_resume_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4()}{ext}"
    student_id = instance.student_id or "new"
    drive_id = instance.drive_id or "new"
    return f"placement/applications/{student_id}/{drive_id}/{unique_name}"


def offer_letter_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4()}{ext}"
    application_id = instance.application_id or "new"
    return f"placement/offers/{application_id}/{unique_name}"


def student_resume_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4()}{ext}"
    student_id = instance.student_id or "new"
    return f"placement/students/{student_id}/resume/{unique_name}"


# Managers
class PlacementDriveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related('company')


class StudentApplicationManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related('student', 'drive__company')


class RoundResultManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related(
            'application__student',
            'application__drive',
            'round__drive',
            'evaluated_by'
        )


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
    
    tier = models.CharField(
        max_length=20,
        choices=[("dream", "Dream"), ("super_dream", "Super Dream"), ("mass", "Mass Recruiter")],
        default="mass",
    )
    is_returning = models.BooleanField(default=False)
    average_package = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name", "is_active"], name="placement_company_active_idx"),
        ]
        verbose_name = "Company"
        verbose_name_plural = "Companies"

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
    eligible_courses = models.ManyToManyField(
        "core.Course",
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
    
    vacancy_count = models.PositiveIntegerField(null=True, blank=True)
    work_mode = models.CharField(
        max_length=10,
        choices=[("remote", "Remote"), ("hybrid", "Hybrid"), ("onsite", "On-site")],
        default="onsite",
    )
    experience_type = models.CharField(
        max_length=15,
        choices=[("internship", "Internship"), ("fulltime", "Full-time"), ("contract", "Contract")],
        default="fulltime",
    )
    max_applications = models.PositiveIntegerField(null=True, blank=True)
    category = models.CharField(
        max_length=15,
        choices=[("dream", "Dream"), ("super_dream", "Super Dream"), ("regular", "Regular")],
        default="regular",
    )

    objects = PlacementDriveManager()

    class Meta:
        ordering = ["-drive_date"]
        indexes = [
            models.Index(fields=["status", "drive_type"], name="place_drive_status_type_idx"),
            models.Index(fields=["eligible_batch_year", "min_cgpa"], name="place_drive_batch_cgpa_idx"),
            models.Index(fields=["application_deadline"], name="placement_drive_deadline_idx"),
        ]
        verbose_name = "Placement Drive"
        verbose_name_plural = "Placement Drives"

    def clean(self):
        super().clean()
        if self.application_deadline and self.drive_date:
            if self.application_deadline >= self.drive_date:
                raise ValidationError({
                    "application_deadline": "Application deadline must be strictly before the drive date."
                })
        if self.min_cgpa is not None and self.min_cgpa > 10.0:
            raise ValidationError({
                "min_cgpa": "Minimum CGPA cannot exceed 10.0."
            })

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
    
    shortlisted_at = models.DateTimeField(null=True, blank=True)
    interviewed_at = models.DateTimeField(null=True, blank=True)
    selected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    objects = StudentApplicationManager()

    class Meta:
        ordering = ["-applied_at"]
        indexes = [
            models.Index(fields=["status", "drive"], name="place_app_status_drive_idx"),
            models.Index(fields=["student", "status"], name="place_app_stud_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["student", "drive"], name="unique_student_drive_application")
        ]
        verbose_name = "Student Application"
        verbose_name_plural = "Student Applications"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if self.pk:
            try:
                orig = StudentApplication.objects.get(pk=self.pk)
                prev_status = orig.status
            except StudentApplication.DoesNotExist:
                prev_status = None
        else:
            prev_status = None

        if self.status != prev_status:
            now_time = timezone.now()
            if self.status == "shortlisted" and self.shortlisted_at is None:
                self.shortlisted_at = now_time
                if update_fields is not None:
                    update_fields = set(update_fields)
                    update_fields.add('shortlisted_at')
                    kwargs['update_fields'] = update_fields
            elif self.status == "interviewed" and self.interviewed_at is None:
                self.interviewed_at = now_time
                if update_fields is not None:
                    update_fields = set(update_fields)
                    update_fields.add('interviewed_at')
                    kwargs['update_fields'] = update_fields
            elif self.status == "selected" and self.selected_at is None:
                self.selected_at = now_time
                if update_fields is not None:
                    update_fields = set(update_fields)
                    update_fields.add('selected_at')
                    kwargs['update_fields'] = update_fields

        super().save(*args, **kwargs)

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
    
    conducted_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_rounds",
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_eliminatory = models.BooleanField(default=True)
    mode = models.CharField(
        max_length=10,
        choices=[("online", "Online"), ("offline", "Offline"), ("hybrid", "Hybrid")],
        default="offline",
    )
    meeting_link = models.URLField(blank=True)

    class Meta:
        ordering = ["round_number"]
        indexes = [
            models.Index(fields=["drive", "round_number"], name="placement_round_drive_num_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["drive", "round_number"], name="unique_drive_round_number")
        ]
        verbose_name = "Placement Round"
        verbose_name_plural = "Placement Rounds"

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
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    
    evaluated_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluated_results",
    )

    objects = RoundResultManager()

    class Meta:
        indexes = [
            models.Index(fields=["round", "result"], name="placement_result_round_idx"),
            models.Index(fields=["application", "round"], name="placement_result_app_round_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["application", "round"], name="unique_application_round_result")
        ]
        verbose_name = "Round Result"
        verbose_name_plural = "Round Results"

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
    
    offer_deadline = models.DateField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_accepted"], name="placement_offer_accepted_idx"),
        ]
        verbose_name = "Placement Offer"
        verbose_name_plural = "Placement Offers"

    def clean(self):
        super().clean()
        if self.is_accepted:
            if self.accepted_at is None:
                raise ValidationError({
                    "accepted_at": "Accepted date/time must be set if the offer is accepted."
                })
        else:
            if self.accepted_at is not None:
                raise ValidationError({
                    "accepted_at": "Accepted date/time must be None if the offer is not accepted."
                })

    def save(self, *args, **kwargs):
        if self.is_accepted:
            if self.accepted_at is None:
                self.accepted_at = timezone.now()
        else:
            self.accepted_at = None
        self.full_clean()
        super().save(*args, **kwargs)

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
    
    willing_to_relocate = models.BooleanField(default=False)
    preferred_locations = models.JSONField(default=list, blank=True)
    opted_out = models.BooleanField(default=False)
    no_of_offers = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["student__register_number"]
        indexes = [
            models.Index(fields=["is_placed", "placed_company"], name="place_profile_placed_co_idx"),
        ]
        verbose_name = "Student Placement Profile"
        verbose_name_plural = "Student Placement Profiles"

    def __str__(self):
        return f"Placement Profile - {self.student.register_number}"


# Signals (At the bottom of the file after all models)
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

@receiver(post_save, sender=PlacementOffer)
def sync_placement_profile(sender, instance, **kwargs):
    if not instance.is_accepted:
        return
    with transaction.atomic():
        offer = (
            PlacementOffer.objects
            .select_related(
                'application__student__placement_profile',
                'application__drive__company'
            )
            .get(pk=instance.pk)
        )
        profile = offer.application.student.placement_profile
        profile.is_placed = True
        profile.placed_company = offer.application.drive.company
        profile.placed_package = offer.ctc
        profile.no_of_offers = models.F('no_of_offers') + 1
        profile.save(update_fields=[
            'is_placed', 'placed_company', 'placed_package',
            'no_of_offers', 'updated_at'
        ])
