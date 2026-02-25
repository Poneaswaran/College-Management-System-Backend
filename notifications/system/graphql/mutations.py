"""
System notification mutations.
Includes admin-only mutations for creating announcements and alerts.
"""
import strawberry
from typing import Optional, List
from strawberry.types import Info

from notifications.graphql.types import NotificationType
from notifications.graphql.permissions import IsAuthenticated
from notifications.system.services import create_announcement, create_system_alert
from django.contrib.auth import get_user_model


User = get_user_model()


@strawberry.type
class SystemNotificationMutation:
    """System notification mutations (admin only)."""
    
    @strawberry.mutation(permission_classes=[IsAuthenticated])
    def send_announcement(
        self,
        info: Info,
        title: str,
        message: str,
        recipient_role: Optional[str] = None,
        action_url: Optional[str] = "",
        priority: Optional[str] = "MEDIUM",
    ) -> int:
        """
        Send an announcement to users (admin only).
        
        Args:
            title: Announcement title
            message: Announcement message
            recipient_role: Filter recipients by role (STUDENT, FACULTY, etc.)
            action_url: Optional action URL
            priority: Priority level (LOW, MEDIUM, HIGH, URGENT)
            
        Returns:
            Number of users notified
        """
        request = info.context.get("request")
        user = request.user
        
        # Check if user is admin/HOD
        if not hasattr(user, 'role') or user.role not in ['ADMIN', 'HOD']:
            return 0
        
        # Get recipients
        recipients_query = User.objects.all()
        
        if recipient_role:
            recipients_query = recipients_query.filter(role=recipient_role)
        
        recipients = list(recipients_query)
        
        if not recipients:
            return 0
        
        # Create announcement
        notifications = create_announcement(
            recipients=recipients,
            title=title,
            message=message,
            action_url=action_url or "",
            priority=priority,
            actor=user,
        )
        
        return len(notifications)
