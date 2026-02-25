"""
Attendance notification mutations (if any specific to attendance).
Most mutations are handled by the core notification mutations.
"""
import strawberry
from strawberry.types import Info

# Attendance notifications are created via signals/receivers
# No specific mutations needed at this time
# All operations use core notification mutations


@strawberry.type
class AttendanceNotificationMutation:
    """Placeholder for attendance-specific notification mutations."""
    
    @strawberry.field
    def placeholder(self) -> str:
        """Placeholder field."""
        return "No attendance-specific mutations at this time"
