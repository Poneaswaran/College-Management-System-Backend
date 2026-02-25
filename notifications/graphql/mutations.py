"""
Strawberry GraphQL mutations for notifications.
"""
import strawberry
from typing import Optional
from strawberry.types import Info

from notifications.graphql.types import NotificationType, NotificationPreferenceType
from notifications.graphql.permissions import IsAuthenticated
from notifications.services import notification_service, preference_service
from notifications.models import Notification


@strawberry.type
class NotificationMutation:
    """Root notification mutations."""
    
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def mark_notification_read(
        self,
        info: Info,
        notification_id: int
    ) -> Optional[NotificationType]:
        """
        Mark a notification as read.
        
        Args:
            notification_id: ID of notification to mark as read
            
        Returns:
            Updated notification or None if not found/not owned
        """
        request = info.context.get("request")
        user = request.user
        
        try:
            notification = notification_service.mark_as_read(
                notification_id=notification_id,
                user=user
            )
            return NotificationType.from_model(notification)
        except Notification.DoesNotExist:
            return None
        except PermissionError:
            return None
    
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def mark_all_notifications_read(
        self,
        info: Info,
        category: Optional[str] = None
    ) -> int:
        """
        Mark all unread notifications as read.
        
        Args:
            category: Optional category filter (mark all in category)
            
        Returns:
            Number of notifications marked as read
        """
        request = info.context.get("request")
        user = request.user
        
        count = notification_service.mark_all_as_read(
            user=user,
            category=category
        )
        
        return count
    
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def dismiss_notification(
        self,
        info: Info,
        notification_id: int
    ) -> bool:
        """
        Dismiss (soft delete) a notification.
        
        Args:
            notification_id: ID of notification to dismiss
            
        Returns:
            True if successful, False otherwise
        """
        request = info.context.get("request")
        user = request.user
        
        try:
            return notification_service.dismiss_notification(
                notification_id=notification_id,
                user=user
            )
        except (Notification.DoesNotExist, PermissionError):
            return False
    
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def bulk_dismiss_notifications(
        self,
        info: Info,
        notification_ids: list[int]
    ) -> int:
        """
        Bulk dismiss multiple notifications.
        
        Args:
            notification_ids: List of notification IDs to dismiss
            
        Returns:
            Number of notifications dismissed
        """
        request = info.context.get("request")
        user = request.user
        
        count = notification_service.bulk_dismiss_notifications(
            notification_ids=notification_ids,
            user=user
        )
        
        return count
    
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def update_notification_preference(
        self,
        info: Info,
        category: str,
        is_enabled: Optional[bool] = None,
        is_sse_enabled: Optional[bool] = None,
        is_email_enabled: Optional[bool] = None,
    ) -> Optional[NotificationPreferenceType]:
        """
        Update notification preference for a category.
        
        Args:
            category: Category to update (ATTENDANCE, ASSIGNMENT, GRADE, SYSTEM)
            is_enabled: Master toggle for category
            is_sse_enabled: Enable/disable SSE delivery
            is_email_enabled: Enable/disable email delivery
            
        Returns:
            Updated preference or None if invalid category
        """
        request = info.context.get("request")
        user = request.user
        
        try:
            preference = preference_service.update_preference(
                user=user,
                category=category,
                is_enabled=is_enabled,
                is_sse_enabled=is_sse_enabled,
                is_email_enabled=is_email_enabled,
            )
            
            return NotificationPreferenceType.from_model(preference)
        except ValueError:
            # Invalid category
            return None
    
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def reset_notification_preferences(
        self,
        info: Info
    ) -> list[NotificationPreferenceType]:
        """
        Reset all notification preferences to defaults.
        
        Returns:
            List of reset preferences
        """
        request = info.context.get("request")
        user = request.user
        
        preferences = preference_service.reset_to_defaults(user)
        
        return [
            NotificationPreferenceType.from_model(pref)
            for pref in preferences
        ]
