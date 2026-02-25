"""
Strawberry GraphQL types for notifications.
"""
import strawberry
from typing import Optional
from datetime import datetime
from django.utils import timezone
from notifications.models import Notification, NotificationPreference


def get_time_ago(created_at: datetime) -> str:
    """
    Convert a datetime to a human-readable time ago string.
    
    Args:
        created_at: Datetime to convert
        
    Returns:
        Human-readable string like "2 minutes ago", "1 hour ago", etc.
    """
    now = timezone.now()
    diff = now - created_at
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    elif seconds < 31536000:
        months = int(seconds / 2592000)
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = int(seconds / 31536000)
        return f"{years} year{'s' if years != 1 else ''} ago"


@strawberry.type
class NotificationType:
    """GraphQL type for Notification model."""
    
    id: int
    notification_type: str
    category: str
    priority: str
    title: str
    message: str
    action_url: str
    metadata: strawberry.scalars.JSON
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime
    
    @strawberry.field
    def actor_name(self) -> Optional[str]:
        """Resolve actor's full name if actor exists."""
        # Access the original model instance
        notification: Notification = self._notification
        if notification.actor:
            full_name = notification.actor.get_full_name()
            return full_name if full_name else notification.actor.email
        return None
    
    @strawberry.field
    def time_ago(self) -> str:
        """Resolve human-readable time ago string."""
        notification: Notification = self._notification
        return get_time_ago(notification.created_at)
    
    @classmethod
    def from_model(cls, notification: Notification) -> "NotificationType":
        """Create GraphQL type from model instance."""
        instance = cls(
            id=notification.id,
            notification_type=notification.notification_type,
            category=notification.category,
            priority=notification.priority,
            title=notification.title,
            message=notification.message,
            action_url=notification.action_url,
            metadata=notification.metadata,
            is_read=notification.is_read,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )
        # Store original model for field resolvers
        instance._notification = notification
        return instance


@strawberry.type
class NotificationConnection:
    """Paginated notification connection with metadata."""
    
    notifications: list[NotificationType]
    total_count: int
    unread_count: int
    has_more: bool
    
    @classmethod
    def from_queryset(
        cls,
        notifications: list[Notification],
        total_count: int,
        unread_count: int,
        limit: int,
        offset: int,
    ) -> "NotificationConnection":
        """Create connection from queryset and counts."""
        notification_types = [
            NotificationType.from_model(n) for n in notifications
        ]
        
        has_more = (offset + len(notifications)) < total_count
        
        return cls(
            notifications=notification_types,
            total_count=total_count,
            unread_count=unread_count,
            has_more=has_more,
        )


@strawberry.type
class NotificationPreferenceType:
    """GraphQL type for NotificationPreference model."""
    
    category: str
    is_enabled: bool
    is_sse_enabled: bool
    is_email_enabled: bool
    
    @classmethod
    def from_model(cls, preference: NotificationPreference) -> "NotificationPreferenceType":
        """Create GraphQL type from model instance."""
        return cls(
            category=preference.category,
            is_enabled=preference.is_enabled,
            is_sse_enabled=preference.is_sse_enabled,
            is_email_enabled=preference.is_email_enabled,
        )


@strawberry.type
class NotificationStats:
    """Statistics about user's notifications."""
    
    total_count: int
    unread_count: int
    read_count: int
    by_category: strawberry.scalars.JSON
    
    @classmethod
    def from_data(
        cls,
        total_count: int,
        unread_count: int,
        read_count: int,
        by_category: dict,
    ) -> "NotificationStats":
        """Create stats from data."""
        return cls(
            total_count=total_count,
            unread_count=unread_count,
            read_count=read_count,
            by_category=by_category,
        )
