"""
System notification services.
Creates notifications for system announcements, alerts, reminders, etc.
"""
import logging
from typing import List, Optional
from django.contrib.auth import get_user_model

from notifications.models import Notification
from notifications.constants import NotificationType, NotificationPriority
from notifications.services.notification_service import (
    create_notification,
    bulk_create_notifications,
)
from notifications.services.broadcast_service import (
    broadcast_notification,
    broadcast_to_multiple_users,
)


User = get_user_model()
logger = logging.getLogger(__name__)


def create_announcement(
    recipients: List[User],
    title: str,
    message: str,
    action_url: str = "",
    priority: str = NotificationPriority.MEDIUM,
    actor: Optional[User] = None,
    expires_in_hours: Optional[int] = None,
) -> List[Notification]:
    """
    Create an announcement notification for multiple users.
    
    Args:
        recipients: List of users to notify
        title: Announcement title
        message: Announcement message
        action_url: Optional action URL
        priority: Priority level
        actor: Admin/HOD who created announcement
        expires_in_hours: Hours until announcement expires
        
    Returns:
        List of created notifications
    """
    try:
        metadata = {
            "announcement_type": "general",
        }
        
        notifications = bulk_create_notifications(
            recipients=recipients,
            notification_type=NotificationType.ANNOUNCEMENT,
            title=title,
            message=message,
            action_url=action_url,
            metadata=metadata,
            actor=actor,
            priority=priority,
            expires_in_hours=expires_in_hours,
        )
        
        # Broadcast to all recipients
        notification_data = {
            "id": notifications[0].id if notifications else None,
            "notification_type": NotificationType.ANNOUNCEMENT,
            "title": title,
            "message": message,
            "category": "SYSTEM",
            "priority": priority,
            "action_url": action_url,
            "metadata": metadata,
        }
        
        user_ids = [user.id for user in recipients]
        broadcast_to_multiple_users(user_ids, notification_data)
        
        logger.info(f"Created announcement for {len(notifications)} users")
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to create announcement: {str(e)}")
        raise


def create_fee_reminder(
    students: List[User],
    amount_due: float,
    due_date: str,
    semester: Optional[str] = None,
) -> List[Notification]:
    """
    Create fee payment reminder notifications.
    
    Args:
        students: List of students with pending fees
        amount_due: Amount pending
        due_date: Payment deadline
        semester: Semester for which fee is due
        
    Returns:
        List of created notifications
    """
    try:
        title = "Fee Payment Reminder"
        message = f"Your fee payment of ₹{amount_due:,.2f} is due by {due_date}. Please pay before the deadline."
        
        if semester:
            message = f"Your {semester} fee payment of ₹{amount_due:,.2f} is due by {due_date}. Please pay before the deadline."
        
        metadata = {
            "amount_due": amount_due,
            "due_date": due_date,
            "semester": semester,
        }
        
        notifications = bulk_create_notifications(
            recipients=students,
            notification_type=NotificationType.FEE_REMINDER,
            title=title,
            message=message,
            action_url="/student/fees",
            metadata=metadata,
            priority=NotificationPriority.HIGH,
        )
        
        # Broadcast to all students
        notification_data = {
            "id": notifications[0].id if notifications else None,
            "notification_type": NotificationType.FEE_REMINDER,
            "title": title,
            "message": message,
            "category": "SYSTEM",
            "priority": NotificationPriority.HIGH,
            "action_url": "/student/fees",
            "metadata": metadata,
        }
        
        user_ids = [student.id for student in students]
        broadcast_to_multiple_users(user_ids, notification_data)
        
        logger.info(f"Created fee reminder for {len(notifications)} students")
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to create fee reminder: {str(e)}")
        raise


def create_system_alert(
    recipients: List[User],
    title: str,
    message: str,
    alert_type: str = "maintenance",
    action_url: str = "",
) -> List[Notification]:
    """
    Create a system alert notification.
    
    Args:
        recipients: List of users to notify
        title: Alert title
        message: Alert message
        alert_type: Type of alert (maintenance, security, etc.)
        action_url: Optional action URL
        
    Returns:
        List of created notifications
    """
    try:
        metadata = {
            "alert_type": alert_type,
        }
        
        notifications = bulk_create_notifications(
            recipients=recipients,
            notification_type=NotificationType.SYSTEM_ALERT,
            title=title,
            message=message,
            action_url=action_url,
            metadata=metadata,
            priority=NotificationPriority.URGENT,
        )
        
        # Broadcast to all recipients
        notification_data = {
            "id": notifications[0].id if notifications else None,
            "notification_type": NotificationType.SYSTEM_ALERT,
            "title": title,
            "message": message,
            "category": "SYSTEM",
            "priority": NotificationPriority.URGENT,
            "action_url": action_url,
            "metadata": metadata,
        }
        
        user_ids = [user.id for user in recipients]
        broadcast_to_multiple_users(user_ids, notification_data)
        
        logger.info(f"Created system alert for {len(notifications)} users")
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to create system alert: {str(e)}")
        raise


def notify_profile_update(
    user: User,
    update_type: str,
    details: str,
    actor: Optional[User] = None,
) -> Notification:
    """
    Notify a user about a profile update.
    
    Args:
        user: User whose profile was updated
        update_type: Type of update (password_changed, email_verified, etc.)
        details: Details of the update
        actor: User who made the update (if different from user)
        
    Returns:
        Created notification
    """
    try:
        title = "Profile Updated"
        message = details
        
        metadata = {
            "update_type": update_type,
        }
        
        notification = create_notification(
            recipient=user,
            notification_type=NotificationType.PROFILE_UPDATE,
            title=title,
            message=message,
            action_url="/profile",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.LOW,
        )
        
        # Broadcast via SSE
        notification_data = {
            "id": notification.id,
            "notification_type": NotificationType.PROFILE_UPDATE,
            "title": title,
            "message": message,
            "category": "SYSTEM",
            "priority": NotificationPriority.LOW,
            "action_url": "/profile",
            "metadata": metadata,
        }
        
        broadcast_notification(user.id, notification_data)
        
        logger.info(f"Notified user {user.id} about profile update")
        
        return notification
        
    except Exception as e:
        logger.error(f"Failed to notify profile update for user {user.id}: {str(e)}")
        raise
