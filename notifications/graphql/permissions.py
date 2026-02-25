"""
Strawberry GraphQL permission classes for notifications.
"""
import strawberry
from strawberry.types import Info
from typing import Any


class IsAuthenticated(strawberry.BasePermission):
    """Permission class to check if user is authenticated."""
    
    message = "User is not authenticated"
    
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        """Check if request has an authenticated user."""
        request = info.context.get("request")
        if not request:
            return False
        
        return hasattr(request, "user") and request.user.is_authenticated


class IsOwner(strawberry.BasePermission):
    """Permission class to check if user owns the notification."""
    
    message = "User does not own this notification"
    
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        """Check if user owns the notification being accessed."""
        request = info.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        
        # For mutations that pass notification_id
        notification_id = kwargs.get("notification_id")
        if notification_id:
            from notifications.models import Notification
            try:
                notification = Notification.objects.get(id=notification_id)
                return notification.recipient == request.user
            except Notification.DoesNotExist:
                return False
        
        # For queries, user can only access their own notifications
        return True
