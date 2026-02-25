"""
System notification GraphQL types.
Extends base NotificationType with system notification-specific fields.
"""
import strawberry
from typing import Optional
from notifications.graphql.types import NotificationType


@strawberry.type
class SystemNotificationPayload:
    """
    Extended notification payload for system notifications.
    Includes system notification-specific metadata fields.
    """
    
    notification: NotificationType
    
    @strawberry.field
    def announcement_type(self) -> Optional[str]:
        """Extract announcement_type from metadata."""
        return self.notification.metadata.get("announcement_type")
    
    @strawberry.field
    def alert_type(self) -> Optional[str]:
        """Extract alert_type from metadata."""
        return self.notification.metadata.get("alert_type")
    
    @strawberry.field
    def update_type(self) -> Optional[str]:
        """Extract update_type from metadata."""
        return self.notification.metadata.get("update_type")
    
    @strawberry.field
    def amount_due(self) -> Optional[float]:
        """Extract amount_due from metadata (for fee reminders)."""
        return self.notification.metadata.get("amount_due")
    
    @strawberry.field
    def due_date(self) -> Optional[str]:
        """Extract due_date from metadata."""
        return self.notification.metadata.get("due_date")
    
    @strawberry.field
    def semester(self) -> Optional[str]:
        """Extract semester from metadata."""
        return self.notification.metadata.get("semester")
