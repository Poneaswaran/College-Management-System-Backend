"""
Core notification service - handles all notification CRUD operations.
All business logic for notifications resides here.
"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

from notifications.models import Notification
from notifications.constants import (
    NotificationType,
    NotificationPriority,
    NotificationCategory,
    NOTIFICATION_TYPE_TO_CATEGORY,
    NOTIFICATION_TYPE_DEFAULT_PRIORITY,
)


User = get_user_model()
logger = logging.getLogger(__name__)


def create_notification(
    recipient: User,
    notification_type: str,
    title: str,
    message: str,
    action_url: str = "",
    metadata: Optional[dict] = None,
    actor: Optional[User] = None,
    priority: Optional[str] = None,
    expires_in_hours: Optional[int] = None,
) -> Notification:
    """
    Create a single notification for a recipient.
    
    Args:
        recipient: User who will receive the notification
        notification_type: Type from NotificationType enum
        title: Notification title (max 255 chars)
        message: Notification message body
        action_url: Frontend route to navigate to
        metadata: Additional JSON data specific to notification type
        actor: User who triggered this notification (optional)
        priority: Priority level (auto-determined if None)
        expires_in_hours: Hours until notification expires (optional)
        
    Returns:
        Created Notification instance
        
    Raises:
        ValueError: If recipient not found or invalid notification type
    """
    try:
        # Validate notification type
        if notification_type not in NotificationType.values:
            raise ValueError(f"Invalid notification type: {notification_type}")
        
        # Auto-determine category from type
        category = NOTIFICATION_TYPE_TO_CATEGORY.get(
            notification_type,
            NotificationCategory.SYSTEM
        )
        
        # Auto-determine priority if not provided
        if priority is None:
            priority = NOTIFICATION_TYPE_DEFAULT_PRIORITY.get(
                notification_type,
                NotificationPriority.MEDIUM
            )
        
        # Calculate expiry time if specified
        expires_at = None
        if expires_in_hours:
            expires_at = timezone.now() + timedelta(hours=expires_in_hours)
        elif hasattr(settings, "NOTIFICATION_DEFAULT_EXPIRY_HOURS"):
            # Use default expiry for non-urgent notifications
            if priority not in [NotificationPriority.URGENT, NotificationPriority.HIGH]:
                default_hours = settings.NOTIFICATION_DEFAULT_EXPIRY_HOURS
                expires_at = timezone.now() + timedelta(hours=default_hours)
        
        # Create notification
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            category=category,
            priority=priority,
            title=title,
            message=message,
            action_url=action_url,
            metadata=metadata or {},
            actor=actor,
            expires_at=expires_at,
        )
        
        logger.info(
            f"Created notification {notification.id} for user {recipient.id} "
            f"({notification_type})"
        )
        
        return notification
        
    except Exception as e:
        logger.error(
            f"Failed to create notification for user {recipient.id if recipient else 'Unknown'}: {str(e)}"
        )
        raise


def bulk_create_notifications(
    recipients: List[User],
    notification_type: str,
    title: str,
    message: str,
    action_url: str = "",
    metadata: Optional[dict] = None,
    actor: Optional[User] = None,
    priority: Optional[str] = None,
    expires_in_hours: Optional[int] = None,
) -> List[Notification]:
    """
    Bulk create notifications for multiple recipients.
    More efficient than creating one by one.
    
    Args:
        recipients: List of users who will receive the notification
        Other args: Same as create_notification()
        
    Returns:
        List of created Notification instances
    """
    try:
        # Validate notification type
        if notification_type not in NotificationType.values:
            raise ValueError(f"Invalid notification type: {notification_type}")
        
        # Auto-determine category and priority
        category = NOTIFICATION_TYPE_TO_CATEGORY.get(
            notification_type,
            NotificationCategory.SYSTEM
        )
        
        if priority is None:
            priority = NOTIFICATION_TYPE_DEFAULT_PRIORITY.get(
                notification_type,
                NotificationPriority.MEDIUM
            )
        
        # Calculate expiry time
        expires_at = None
        if expires_in_hours:
            expires_at = timezone.now() + timedelta(hours=expires_in_hours)
        elif hasattr(settings, "NOTIFICATION_DEFAULT_EXPIRY_HOURS"):
            if priority not in [NotificationPriority.URGENT, NotificationPriority.HIGH]:
                default_hours = settings.NOTIFICATION_DEFAULT_EXPIRY_HOURS
                expires_at = timezone.now() + timedelta(hours=default_hours)
        
        # Prepare notification objects
        notifications = [
            Notification(
                recipient=recipient,
                notification_type=notification_type,
                category=category,
                priority=priority,
                title=title,
                message=message,
                action_url=action_url,
                metadata=metadata or {},
                actor=actor,
                expires_at=expires_at,
            )
            for recipient in recipients
        ]
        
        # Bulk create
        created = Notification.objects.bulk_create(notifications)
        
        logger.info(
            f"Bulk created {len(created)} notifications of type {notification_type}"
        )
        
        return created
        
    except Exception as e:
        logger.error(f"Failed to bulk create notifications: {str(e)}")
        raise


def mark_as_read(notification_id: int, user: User) -> Notification:
    """
    Mark a notification as read.
    
    Args:
        notification_id: ID of notification to mark as read
        user: User requesting the action (for ownership check)
        
    Returns:
        Updated Notification instance
        
    Raises:
        Notification.DoesNotExist: If notification not found
        PermissionError: If user doesn't own the notification
    """
    try:
        notification = Notification.objects.select_related("recipient").get(
            id=notification_id
        )
        
        # Verify ownership
        if notification.recipient != user:
            raise PermissionError(
                f"User {user.id} does not own notification {notification_id}"
            )
        
        # Mark as read if not already
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at", "updated_at"])
            
            logger.info(f"Marked notification {notification_id} as read")
        
        return notification
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        raise
    except Exception as e:
        logger.error(f"Failed to mark notification {notification_id} as read: {str(e)}")
        raise


def mark_all_as_read(
    user: User,
    category: Optional[str] = None
) -> int:
    """
    Mark all unread notifications as read for a user.
    
    Args:
        user: User whose notifications to mark as read
        category: Optional category filter (e.g., "ATTENDANCE")
        
    Returns:
        Number of notifications marked as read
    """
    try:
        query = Q(recipient=user, is_read=False)
        
        if category:
            query &= Q(category=category)
        
        count = Notification.objects.filter(query).update(
            is_read=True,
            read_at=timezone.now(),
            updated_at=timezone.now()
        )
        
        logger.info(
            f"Marked {count} notifications as read for user {user.id} "
            f"(category: {category or 'all'})"
        )
        
        return count
        
    except Exception as e:
        logger.error(f"Failed to mark all notifications as read for user {user.id}: {str(e)}")
        raise


def dismiss_notification(notification_id: int, user: User) -> bool:
    """
    Dismiss (soft delete) a notification.
    
    Args:
        notification_id: ID of notification to dismiss
        user: User requesting the action (for ownership check)
        
    Returns:
        True if dismissed successfully
        
    Raises:
        Notification.DoesNotExist: If notification not found
        PermissionError: If user doesn't own the notification
    """
    try:
        notification = Notification.objects.select_related("recipient").get(
            id=notification_id
        )
        
        # Verify ownership
        if notification.recipient != user:
            raise PermissionError(
                f"User {user.id} does not own notification {notification_id}"
            )
        
        # Dismiss if not already
        if not notification.is_dismissed:
            notification.is_dismissed = True
            notification.dismissed_at = timezone.now()
            notification.save(update_fields=["is_dismissed", "dismissed_at", "updated_at"])
            
            logger.info(f"Dismissed notification {notification_id}")
        
        return True
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
        raise
    except Exception as e:
        logger.error(f"Failed to dismiss notification {notification_id}: {str(e)}")
        raise


def bulk_dismiss_notifications(
    notification_ids: List[int],
    user: User
) -> int:
    """
    Bulk dismiss multiple notifications.
    
    Args:
        notification_ids: List of notification IDs to dismiss
        user: User requesting the action (for ownership check)
        
    Returns:
        Number of notifications dismissed
    """
    try:
        count = Notification.objects.filter(
            id__in=notification_ids,
            recipient=user,
            is_dismissed=False
        ).update(
            is_dismissed=True,
            dismissed_at=timezone.now(),
            updated_at=timezone.now()
        )
        
        logger.info(f"Bulk dismissed {count} notifications for user {user.id}")
        
        return count
        
    except Exception as e:
        logger.error(f"Failed to bulk dismiss notifications for user {user.id}: {str(e)}")
        raise


def get_user_notifications(
    user: User,
    category: Optional[str] = None,
    is_read: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
) -> QuerySet[Notification]:
    """
    Get notifications for a user with filtering and pagination.
    
    Args:
        user: User whose notifications to retrieve
        category: Optional category filter
        is_read: Optional read status filter
        limit: Maximum number of notifications to return
        offset: Number of notifications to skip
        
    Returns:
        QuerySet of Notification instances
    """
    try:
        query = Q(recipient=user, is_dismissed=False)
        
        if category:
            query &= Q(category=category)
        
        if is_read is not None:
            query &= Q(is_read=is_read)
        
        notifications = (
            Notification.objects.filter(query)
            .select_related("actor", "recipient")
            .order_by("-created_at")[offset:offset + limit]
        )
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to get notifications for user {user.id}: {str(e)}")
        raise


def get_unread_count(
    user: User,
    category: Optional[str] = None
) -> int:
    """
    Get count of unread notifications for a user.
    
    Args:
        user: User whose unread count to retrieve
        category: Optional category filter
        
    Returns:
        Count of unread notifications
    """
    try:
        query = Q(recipient=user, is_read=False, is_dismissed=False)
        
        if category:
            query &= Q(category=category)
        
        count = Notification.objects.filter(query).count()
        
        return count
        
    except Exception as e:
        logger.error(f"Failed to get unread count for user {user.id}: {str(e)}")
        return 0


def get_total_count(
    user: User,
    category: Optional[str] = None,
    is_read: Optional[bool] = None,
) -> int:
    """
    Get total count of notifications for a user.
    
    Args:
        user: User whose notification count to retrieve
        category: Optional category filter
        is_read: Optional read status filter
        
    Returns:
        Total count of notifications
    """
    try:
        query = Q(recipient=user, is_dismissed=False)
        
        if category:
            query &= Q(category=category)
        
        if is_read is not None:
            query &= Q(is_read=is_read)
        
        count = Notification.objects.filter(query).count()
        
        return count
        
    except Exception as e:
        logger.error(f"Failed to get total count for user {user.id}: {str(e)}")
        return 0
