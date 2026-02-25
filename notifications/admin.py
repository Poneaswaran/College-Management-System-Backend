"""
Django admin configuration for notifications.
"""
from django.contrib import admin
from django.utils.html import format_html
from notifications.models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model."""

    list_display = [
        "id",
        "recipient_name",
        "notification_type",
        "category",
        "priority_badge",
        "title",
        "is_read",
        "is_dismissed",
        "created_at",
    ]
    list_filter = [
        "category",
        "priority",
        "notification_type",
        "is_read",
        "is_dismissed",
        "created_at",
    ]
    search_fields = [
        "recipient__first_name",
        "recipient__last_name",
        "recipient__email",
        "title",
        "message",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "read_at",
        "dismissed_at",
    ]
    date_hierarchy = "created_at"
    list_per_page = 50

    fieldsets = (
        ("Recipient Information", {
            "fields": ("recipient", "actor")
        }),
        ("Notification Details", {
            "fields": (
                "notification_type",
                "category",
                "priority",
                "title",
                "message",
                "action_url",
                "metadata",
            )
        }),
        ("Status", {
            "fields": (
                "is_read",
                "read_at",
                "is_dismissed",
                "dismissed_at",
                "expires_at",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

    def recipient_name(self, obj):
        """Display recipient's full name."""
        return obj.recipient.get_full_name() or obj.recipient.email

    recipient_name.short_description = "Recipient"
    recipient_name.admin_order_field = "recipient__first_name"

    def priority_badge(self, obj):
        """Display priority as colored badge."""
        colors = {
            "LOW": "#6c757d",
            "MEDIUM": "#0d6efd",
            "HIGH": "#fd7e14",
            "URGENT": "#dc3545",
        }
        color = colors.get(obj.priority, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.priority
        )

    priority_badge.short_description = "Priority"
    priority_badge.admin_order_field = "priority"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("recipient", "actor")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin interface for NotificationPreference model."""

    list_display = [
        "id",
        "user_name",
        "category",
        "is_enabled",
        "is_sse_enabled",
        "is_email_enabled",
        "updated_at",
    ]
    list_filter = [
        "category",
        "is_enabled",
        "is_sse_enabled",
        "is_email_enabled",
    ]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
    ]
    readonly_fields = ["created_at", "updated_at"]
    list_per_page = 50

    fieldsets = (
        ("User and Category", {
            "fields": ("user", "category")
        }),
        ("Preferences", {
            "fields": (
                "is_enabled",
                "is_sse_enabled",
                "is_email_enabled",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

    def user_name(self, obj):
        """Display user's full name."""
        return obj.user.get_full_name() or obj.user.email

    user_name.short_description = "User"
    user_name.admin_order_field = "user__first_name"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("user")
