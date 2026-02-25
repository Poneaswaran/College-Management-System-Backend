"""
Grade-specific notification GraphQL types.
Extends base NotificationType with grade-specific fields.
"""
import strawberry
from typing import Optional
from notifications.graphql.types import NotificationType


@strawberry.type
class GradeNotificationPayload:
    """
    Extended notification payload for grade notifications.
    Includes grade-specific metadata fields.
    """
    
    notification: NotificationType
    
    @strawberry.field
    def subject_name(self) -> Optional[str]:
        """Extract subject_name from metadata."""
        return self.notification.metadata.get("subject_name")
    
    @strawberry.field
    def grade(self) -> Optional[str]:
        """Extract grade from metadata."""
        return self.notification.metadata.get("grade")
    
    @strawberry.field
    def grade_type(self) -> Optional[str]:
        """Extract grade_type from metadata (Midterm, Final, etc.)."""
        return self.notification.metadata.get("grade_type")
    
    @strawberry.field
    def exam_name(self) -> Optional[str]:
        """Extract exam_name from metadata."""
        return self.notification.metadata.get("exam_name")
    
    @strawberry.field
    def semester(self) -> Optional[str]:
        """Extract semester from metadata."""
        return self.notification.metadata.get("semester")
