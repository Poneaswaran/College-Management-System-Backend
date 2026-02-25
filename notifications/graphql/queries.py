"""
Strawberry GraphQL queries for notifications.
"""
import strawberry
from typing import Optional
from strawberry.types import Info

from notifications.graphql.types import (
    NotificationType,
    NotificationConnection,
    NotificationPreferenceType,
    NotificationStats,
)
from notifications.graphql.permissions import IsAuthenticated
from notifications.services import notification_service, preference_service
from notifications.constants import NotificationCategory
from notifications.models import Notification


@strawberry.type
class NotificationQuery:
    """Root notification queries."""
    
    @strawberry.field(permission_classes=[IsAuthenticated])
    def my_notifications(
        self,
        info: Info,
        category: Optional[str] = None,
        is_read: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> NotificationConnection:
        """
        Get current user's notifications with filtering and pagination.
        
        Args:
            category: Filter by category (ATTENDANCE, ASSIGNMENT, GRADE, SYSTEM)
            is_read: Filter by read status (true/false/null for all)
            limit: Maximum number of notifications to return
            offset: Number of notifications to skip
            
        Returns:
            NotificationConnection with paginated results
        """
        request = info.context.get("request")
        user = request.user
        
        # Get paginated notifications
        notifications = list(
            notification_service.get_user_notifications(
                user=user,
                category=category,
                is_read=is_read,
                limit=limit,
                offset=offset,
            )
        )
        
        # Get total count
        total_count = notification_service.get_total_count(
            user=user,
            category=category,
            is_read=is_read,
        )
        
        # Get unread count
        unread_count = notification_service.get_unread_count(
            user=user,
            category=category,
        )
        
        return NotificationConnection.from_queryset(
            notifications=notifications,
            total_count=total_count,
            unread_count=unread_count,
            limit=limit,
            offset=offset,
        )
    
    @strawberry.field(permission_classes=[IsAuthenticated])
    def unread_count(
        self,
        info: Info,
        category: Optional[str] = None
    ) -> int:
        """
        Get count of unread notifications for current user.
        
        Args:
            category: Optional category filter
            
        Returns:
            Number of unread notifications
        """
        request = info.context.get("request")
        user = request.user
        
        return notification_service.get_unread_count(
            user=user,
            category=category,
        )
    
    @strawberry.field(permission_classes=[IsAuthenticated])
    def my_notification_preferences(
        self,
        info: Info
    ) -> list[NotificationPreferenceType]:
        """
        Get notification preferences for current user.
        
        Returns:
            List of notification preferences by category
        """
        request = info.context.get("request")
        user = request.user
        
        preferences = preference_service.get_user_preferences(user)
        
        return [
            NotificationPreferenceType.from_model(pref)
            for pref in preferences
        ]
    
    @strawberry.field(permission_classes=[IsAuthenticated])
    def notification_stats(
        self,
        info: Info
    ) -> NotificationStats:
        """
        Get notification statistics for current user.
        
        Returns:
            Statistics including total, unread, read counts and breakdown by category
        """
        request = info.context.get("request")
        user = request.user
        
        total_count = notification_service.get_total_count(user=user)
        unread_count = notification_service.get_unread_count(user=user)
        read_count = total_count - unread_count
        
        # Get counts by category
        by_category = {}
        for category in NotificationCategory.values:
            category_total = notification_service.get_total_count(
                user=user,
                category=category
            )
            category_unread = notification_service.get_unread_count(
                user=user,
                category=category
            )
            by_category[category] = {
                "total": category_total,
                "unread": category_unread,
                "read": category_total - category_unread,
            }
        
        return NotificationStats.from_data(
            total_count=total_count,
            unread_count=unread_count,
            read_count=read_count,
            by_category=by_category,
        )
    
    @strawberry.field(permission_classes=[IsAuthenticated])
    def notification_by_id(
        self,
        info: Info,
        notification_id: int
    ) -> Optional[NotificationType]:
        """
        Get a specific notification by ID.
        
        Args:
            notification_id: ID of the notification
            
        Returns:
            NotificationType or None if not found or not owned by user
        """
        request = info.context.get("request")
        user = request.user
        
        try:
            notification = Notification.objects.select_related("actor").get(
                id=notification_id,
                recipient=user
            )
            return NotificationType.from_model(notification)
        except Notification.DoesNotExist:
            return None
