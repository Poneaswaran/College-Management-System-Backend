"""
Assignment-specific notification GraphQL types.
Extends base NotificationType with assignment-specific fields.
"""
import strawberry
from typing import Optional
from datetime import datetime
from notifications.graphql.types import NotificationType


@strawberry.type
class AssignmentNotificationPayload:
    """
    Extended notification payload for assignment notifications.
    Includes assignment-specific metadata fields.
    """
    
    notification: NotificationType
    
    @strawberry.field
    def assignment_id(self) -> Optional[int]:
        """Extract assignment_id from metadata."""
        return self.notification.metadata.get("assignment_id")
    
    @strawberry.field
    def assignment_title(self) -> Optional[str]:
        """Extract assignment_title from metadata."""
        return self.notification.metadata.get("assignment_title")
    
    @strawberry.field
    def subject_name(self) -> Optional[str]:
        """Extract subject_name from metadata."""
        return self.notification.metadata.get("subject_name")
    
    @strawberry.field
    def grade(self) -> Optional[str]:
        """Extract grade from metadata."""
        return self.notification.metadata.get("grade")
    
    @strawberry.field
    def due_date(self) -> Optional[str]:
        """Extract due_date from metadata."""
        return self.notification.metadata.get("due_date")
    
    @strawberry.field
    def hours_remaining(self) -> Optional[int]:
        """Extract hours_remaining from metadata."""
        return self.notification.metadata.get("hours_remaining")
