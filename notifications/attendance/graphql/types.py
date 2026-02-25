"""
Attendance-specific notification GraphQL types.
Extends base NotificationType with attendance-specific fields.
"""
import strawberry
from typing import Optional
from notifications.graphql.types import NotificationType


@strawberry.type
class AttendanceNotificationPayload:
    """
    Extended notification payload for attendance notifications.
    Includes attendance-specific metadata fields.
    """
    
    notification: NotificationType
    
    @strawberry.field
    def session_id(self) -> Optional[int]:
        """Extract session_id from metadata."""
        return self.notification.metadata.get("session_id")
    
    @strawberry.field
    def subject_name(self) -> Optional[str]:
        """Extract subject_name from metadata."""
        return self.notification.metadata.get("subject_name")
    
    @strawberry.field
    def section_name(self) -> Optional[str]:
        """Extract section_name from metadata."""
        return self.notification.metadata.get("section_name")
    
    @strawberry.field
    def attendance_status(self) -> Optional[str]:
        """Extract attendance status from metadata."""
        return self.notification.metadata.get("status")
    
    @strawberry.field
    def attendance_percentage(self) -> Optional[float]:
        """Extract current attendance percentage from metadata."""
        return self.notification.metadata.get("current_percentage")
