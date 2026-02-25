"""
Cleanup service - handles deletion of old notifications.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db.models import Q

from notifications.models import Notification


logger = logging.getLogger(__name__)


def cleanup_old_notifications() -> dict:
    """
    Clean up old notifications based on configured settings.
    
    Deletes:
    1. All dismissed notifications older than 30 days
    2. All read notifications older than NOTIFICATION_CLEANUP_DAYS (default 90)
    3. All expired notifications (expires_at < now)
    
    Returns:
        Dict with counts of deleted notifications by type
    """
    try:
        now = timezone.now()
        
        # Get cleanup settings
        cleanup_days = getattr(settings, "NOTIFICATION_CLEANUP_DAYS", 90)
        dismissed_retention_days = 30
        
        counts = {
            "dismissed": 0,
            "read": 0,
            "expired": 0,
            "total": 0,
        }
        
        # Delete dismissed notifications older than 30 days
        dismissed_cutoff = now - timedelta(days=dismissed_retention_days)
        dismissed_count = Notification.objects.filter(
            is_dismissed=True,
            dismissed_at__lt=dismissed_cutoff
        ).delete()[0]
        counts["dismissed"] = dismissed_count
        
        logger.info(
            f"Deleted {dismissed_count} dismissed notifications older than {dismissed_retention_days} days"
        )
        
        # Delete read notifications older than cleanup_days
        read_cutoff = now - timedelta(days=cleanup_days)
        read_count = Notification.objects.filter(
            is_read=True,
            read_at__lt=read_cutoff,
            is_dismissed=False  # Don't double-count dismissed ones
        ).delete()[0]
        counts["read"] = read_count
        
        logger.info(
            f"Deleted {read_count} read notifications older than {cleanup_days} days"
        )
        
        # Delete expired notifications
        expired_count = Notification.objects.filter(
            expires_at__lt=now,
            is_dismissed=False,  # Don't double-count
            is_read=False  # Don't double-count
        ).delete()[0]
        counts["expired"] = expired_count
        
        logger.info(f"Deleted {expired_count} expired notifications")
        
        # Calculate total
        counts["total"] = dismissed_count + read_count + expired_count
        
        logger.info(f"Total notifications deleted: {counts['total']}")
        
        return counts
        
    except Exception as e:
        logger.error(f"Failed to cleanup old notifications: {str(e)}")
        raise


def cleanup_user_notifications(user_id: int, days: int = 90) -> int:
    """
    Clean up old notifications for a specific user.
    
    Args:
        user_id: User ID whose notifications to clean up
        days: Delete notifications older than this many days
        
    Returns:
        Number of notifications deleted
    """
    try:
        cutoff = timezone.now() - timedelta(days=days)
        
        count = Notification.objects.filter(
            recipient_id=user_id,
            created_at__lt=cutoff
        ).delete()[0]
        
        logger.info(
            f"Deleted {count} notifications for user {user_id} older than {days} days"
        )
        
        return count
        
    except Exception as e:
        logger.error(f"Failed to cleanup notifications for user {user_id}: {str(e)}")
        raise


def auto_dismiss_expired_notifications() -> int:
    """
    Auto-dismiss notifications that have passed their expiry time.
    
    Returns:
        Number of notifications auto-dismissed
    """
    try:
        now = timezone.now()
        
        count = Notification.objects.filter(
            expires_at__lt=now,
            is_dismissed=False
        ).update(
            is_dismissed=True,
            dismissed_at=now,
            updated_at=now
        )
        
        logger.info(f"Auto-dismissed {count} expired notifications")
        
        return count
        
    except Exception as e:
        logger.error(f"Failed to auto-dismiss expired notifications: {str(e)}")
        raise


def cleanup_by_category(category: str, days: int = 30) -> int:
    """
    Clean up old notifications for a specific category.
    Useful for categories that generate many notifications.
    
    Args:
        category: Notification category to clean up
        days: Delete notifications older than this many days
        
    Returns:
        Number of notifications deleted
    """
    try:
        cutoff = timezone.now() - timedelta(days=days)
        
        count = Notification.objects.filter(
            category=category,
            created_at__lt=cutoff,
            Q(is_read=True) | Q(is_dismissed=True)  # Only delete read or dismissed
        ).delete()[0]
        
        logger.info(
            f"Deleted {count} {category} notifications older than {days} days"
        )
        
        return count
        
    except Exception as e:
        logger.error(f"Failed to cleanup {category} notifications: {str(e)}")
        raise


def get_cleanup_statistics() -> dict:
    """
    Get statistics about notifications that would be cleaned up.
    Useful for previewing cleanup operations.
    
    Returns:
        Dict with counts by cleanup category
    """
    try:
        now = timezone.now()
        cleanup_days = getattr(settings, "NOTIFICATION_CLEANUP_DAYS", 90)
        dismissed_retention_days = 30
        
        dismissed_cutoff = now - timedelta(days=dismissed_retention_days)
        read_cutoff = now - timedelta(days=cleanup_days)
        
        stats = {
            "dismissed_candidates": Notification.objects.filter(
                is_dismissed=True,
                dismissed_at__lt=dismissed_cutoff
            ).count(),
            "read_candidates": Notification.objects.filter(
                is_read=True,
                read_at__lt=read_cutoff,
                is_dismissed=False
            ).count(),
            "expired_candidates": Notification.objects.filter(
                expires_at__lt=now,
                is_dismissed=False,
                is_read=False
            ).count(),
            "total_notifications": Notification.objects.count(),
        }
        
        stats["total_candidates"] = (
            stats["dismissed_candidates"] +
            stats["read_candidates"] +
            stats["expired_candidates"]
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get cleanup statistics: {str(e)}")
        raise
