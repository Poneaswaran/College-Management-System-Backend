import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q

from onboarding.constants import (
    TASK_ENTITY_CHOICES,
    TASK_ENTITY_STUDENT,
    TASK_STATUS_CHOICES,
    TASK_STATUS_PENDING,
    ID_CARD_STATUS_CHOICES,
    ID_CARD_STATUS_PENDING,
)


def onboarding_upload_file_path(instance, filename):
    return f"onboarding/uploads/{instance.entity_type.lower()}/{filename}"


def id_card_qr_path(instance, filename):
    return f"onboarding/id_cards/{instance.card_type.lower()}/qr/{filename}"


def id_card_pdf_path(instance, filename):
    return f"onboarding/id_cards/{instance.card_type.lower()}/pdf/{filename}"


class OnboardingTaskLog(models.Model):
    task_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    entity_type = models.CharField(max_length=20, choices=TASK_ENTITY_CHOICES, default=TASK_ENTITY_STUDENT)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="onboarding_task_logs",
    )
    file = models.FileField(upload_to=onboarding_upload_file_path)
    file_hash = models.CharField(max_length=64, db_index=True)
    idempotency_key = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    dry_run = models.BooleanField(default=False)
    is_retry = models.BooleanField(default=False)
    retry_attempt = models.PositiveIntegerField(default=0)
    source_task = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retry_tasks",
    )

    total_rows = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_duration_ms = models.PositiveBigIntegerField(default=0)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    failure_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default=TASK_STATUS_PENDING)
    error_log = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity_type", "file_hash"],
                condition=Q(is_active=True, dry_run=False, is_retry=False),
                name="uq_onboarding_entity_filehash_active",
            )
        ]
        indexes = [
            models.Index(fields=["entity_type", "status"]),
            models.Index(fields=["uploaded_by", "created_at"]),
            models.Index(fields=["is_active", "entity_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.entity_type} - {self.task_id}"


class FacultyOnboardingRecord(models.Model):
    faculty_profile = models.OneToOneField(
        "profile_management.FacultyProfile",
        on_delete=models.CASCADE,
        related_name="onboarding_record",
    )
    employee_id = models.CharField(max_length=40, unique=True, db_index=True)
    is_hod = models.BooleanField(default=False)
    subject_codes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_id"]

    def __str__(self):
        return self.employee_id


class StudentIDCard(models.Model):
    card_type = "STUDENT"
    student_profile = models.OneToOneField(
        "profile_management.StudentProfile",
        on_delete=models.CASCADE,
        related_name="id_card",
    )
    status = models.CharField(max_length=20, choices=ID_CARD_STATUS_CHOICES, default=ID_CARD_STATUS_PENDING)
    card_number = models.CharField(max_length=64, unique=True, db_index=True)
    qr_token = models.TextField(blank=True)
    qr_image = models.ImageField(upload_to=id_card_qr_path, null=True, blank=True)
    pdf_file = models.FileField(upload_to=id_card_pdf_path, null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_student_id_cards",
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-generated_at", "-id"]

    def __str__(self):
        return self.card_number


class FacultyIDCard(models.Model):
    card_type = "FACULTY"
    faculty_profile = models.OneToOneField(
        "profile_management.FacultyProfile",
        on_delete=models.CASCADE,
        related_name="id_card",
    )
    status = models.CharField(max_length=20, choices=ID_CARD_STATUS_CHOICES, default=ID_CARD_STATUS_PENDING)
    card_number = models.CharField(max_length=64, unique=True, db_index=True)
    qr_token = models.TextField(blank=True)
    qr_image = models.ImageField(upload_to=id_card_qr_path, null=True, blank=True)
    pdf_file = models.FileField(upload_to=id_card_pdf_path, null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_faculty_id_cards",
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-generated_at", "-id"]

    def __str__(self):
        return self.card_number
