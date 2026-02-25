"""
Assignment notification mutations (if any specific to assignments).
Most mutations are handled by the core notification mutations.
"""
import strawberry

# Assignment notifications are created via signals/receivers
# No specific mutations needed at this time


@strawberry.type
class AssignmentNotificationMutation:
    """Placeholder for assignment-specific notification mutations."""
    
    @strawberry.field
    def placeholder(self) -> str:
        """Placeholder field."""
        return "No assignment-specific mutations at this time"
