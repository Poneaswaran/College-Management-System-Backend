import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q

from onboarding.constants import (
    TASK_ENTITY_CHOICES,
    TASK_ENTITY_STUDENT,
    TASK_ENTITY_FACULTY,
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


class OnboardingAuditLog(models.Model):
    action = models.CharField(max_length=80, db_index=True)
    entity_type = models.CharField(max_length=20, choices=TASK_ENTITY_CHOICES, default=TASK_ENTITY_STUDENT)
    entity_id = models.CharField(max_length=120, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="onboarding_audit_logs",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "action", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
        ]


class StudentOnboardingApproval(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    student_profile = models.OneToOneField(
        "profile_management.StudentProfile",
        on_delete=models.CASCADE,
        related_name="onboarding_approval",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_student_onboarding_approvals",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_student_onboarding_approvals",
    )
    remarks = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class FacultyOnboardingApproval(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    faculty_profile = models.OneToOneField(
        "profile_management.FacultyProfile",
        on_delete=models.CASCADE,
        related_name="onboarding_approval",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_faculty_onboarding_approvals",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_faculty_onboarding_approvals",
    )
    remarks = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class TemporaryOnboardingAccess(models.Model):
    SCOPE_ALL = "ALL"
    SCOPE_CHOICES = [
        (TASK_ENTITY_STUDENT, "Student"),
        (TASK_ENTITY_FACULTY, "Faculty"),
        (SCOPE_ALL, "All"),
    ]

    faculty_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="temporary_onboarding_accesses",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="granted_onboarding_accesses",
    )
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_ALL)
    can_bulk_upload = models.BooleanField(default=True)
    can_retry = models.BooleanField(default=True)
    expires_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["faculty_user", "is_active", "expires_at"]),
        ]


class OnboardingDraft(models.Model):
    STATUS_DRAFT = "DRAFT"
    STATUS_SUBMITTED = "SUBMITTED"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
    ]

    entity_type = models.CharField(max_length=20, choices=TASK_ENTITY_CHOICES)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_onboarding_drafts",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_onboarding_drafts",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_onboarding_drafts",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["entity_type", "status", "updated_at"]),
            models.Index(fields=["created_by", "updated_at"]),
        ]


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
