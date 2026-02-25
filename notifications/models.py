"""
Notification models for persistent storage and user preferences.
"""
from django.db import models
from django.conf import settings
from notifications.constants import (
    NotificationType,
    NotificationPriority,
    NotificationCategory,
)


class Notification(models.Model):
    """
    Core notification model — one row per notification per recipient.
    Stores all notification data with read/dismissed status tracking.
    """

    id = models.BigAutoField(primary_key=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices
    )
    category = models.CharField(
        max_length=20,
        choices=NotificationCategory.choices
    )
    priority = models.CharField(
        max_length=10,
        choices=NotificationPriority.choices,
        default=NotificationPriority.MEDIUM
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    action_url = models.CharField(
        max_length=500,
        blank=True,
        default=""
    )  # Frontend route to navigate to

    # Metadata — JSON field for category-specific extra data
    metadata = models.JSONField(
        default=dict,
        blank=True
    )  # e.g., {"session_id": 42, "subject_name": "Math"}

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    # Actor — who triggered this notification (nullable for system-generated)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_notifications"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True
    )  # Auto-dismiss after this time

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["recipient", "category", "-created_at"]),
            models.Index(fields=["notification_type"]),
            models.Index(fields=["expires_at"]),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self) -> str:
        return f"{self.notification_type} for {self.recipient.get_full_name()} - {self.title}"


class NotificationPreference(models.Model):
    """
    Per-user, per-category notification preferences.
    Controls which notification delivery channels are enabled.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences"
    )
    category = models.CharField(
        max_length=20,
        choices=NotificationCategory.choices
    )
    is_enabled = models.BooleanField(default=True)  # Master toggle for category
    is_sse_enabled = models.BooleanField(default=True)  # Real-time SSE delivery
    is_email_enabled = models.BooleanField(default=False)  # Email delivery (future)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "category"]
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} - {self.category} preferences"
