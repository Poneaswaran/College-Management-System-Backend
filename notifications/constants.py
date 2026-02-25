"""
Constants for notification types, categories, and priorities.
"""
from django.db import models


class NotificationType(models.TextChoices):
    """All available notification types."""
    
    # Attendance
    ATTENDANCE_SESSION_OPENED = "ATTENDANCE_SESSION_OPENED", "Attendance Session Opened"
    ATTENDANCE_SESSION_CLOSED = "ATTENDANCE_SESSION_CLOSED", "Attendance Session Closed"
    LOW_ATTENDANCE_ALERT = "LOW_ATTENDANCE_ALERT", "Low Attendance Alert"
    ATTENDANCE_MARKED = "ATTENDANCE_MARKED", "Attendance Marked"
    
    # Assignments
    ASSIGNMENT_PUBLISHED = "ASSIGNMENT_PUBLISHED", "Assignment Published"
    ASSIGNMENT_DUE_SOON = "ASSIGNMENT_DUE_SOON", "Assignment Due Soon"
    ASSIGNMENT_OVERDUE = "ASSIGNMENT_OVERDUE", "Assignment Overdue"
    ASSIGNMENT_GRADED = "ASSIGNMENT_GRADED", "Assignment Graded"
    ASSIGNMENT_RETURNED = "ASSIGNMENT_RETURNED", "Assignment Returned"
    SUBMISSION_RECEIVED = "SUBMISSION_RECEIVED", "Submission Received"
    
    # Grades
    GRADE_PUBLISHED = "GRADE_PUBLISHED", "Grade Published"
    RESULT_DECLARED = "RESULT_DECLARED", "Result Declared"
    
    # System
    ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
    FEE_REMINDER = "FEE_REMINDER", "Fee Reminder"
    SYSTEM_ALERT = "SYSTEM_ALERT", "System Alert"
    PROFILE_UPDATE = "PROFILE_UPDATE", "Profile Update"


class NotificationPriority(models.TextChoices):
    """Notification priority levels."""
    
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    URGENT = "URGENT", "Urgent"


class NotificationCategory(models.TextChoices):
    """Notification categories for grouping and filtering."""
    
    ATTENDANCE = "ATTENDANCE", "Attendance"
    ASSIGNMENT = "ASSIGNMENT", "Assignment"
    GRADE = "GRADE", "Grade"
    SYSTEM = "SYSTEM", "System"


# Mapping notification types to categories
NOTIFICATION_TYPE_TO_CATEGORY = {
    NotificationType.ATTENDANCE_SESSION_OPENED: NotificationCategory.ATTENDANCE,
    NotificationType.ATTENDANCE_SESSION_CLOSED: NotificationCategory.ATTENDANCE,
    NotificationType.LOW_ATTENDANCE_ALERT: NotificationCategory.ATTENDANCE,
    NotificationType.ATTENDANCE_MARKED: NotificationCategory.ATTENDANCE,
    
    NotificationType.ASSIGNMENT_PUBLISHED: NotificationCategory.ASSIGNMENT,
    NotificationType.ASSIGNMENT_DUE_SOON: NotificationCategory.ASSIGNMENT,
    NotificationType.ASSIGNMENT_OVERDUE: NotificationCategory.ASSIGNMENT,
    NotificationType.ASSIGNMENT_GRADED: NotificationCategory.ASSIGNMENT,
    NotificationType.ASSIGNMENT_RETURNED: NotificationCategory.ASSIGNMENT,
    NotificationType.SUBMISSION_RECEIVED: NotificationCategory.ASSIGNMENT,
    
    NotificationType.GRADE_PUBLISHED: NotificationCategory.GRADE,
    NotificationType.RESULT_DECLARED: NotificationCategory.GRADE,
    
    NotificationType.ANNOUNCEMENT: NotificationCategory.SYSTEM,
    NotificationType.FEE_REMINDER: NotificationCategory.SYSTEM,
    NotificationType.SYSTEM_ALERT: NotificationCategory.SYSTEM,
    NotificationType.PROFILE_UPDATE: NotificationCategory.SYSTEM,
}


# Default priorities for notification types
NOTIFICATION_TYPE_DEFAULT_PRIORITY = {
    NotificationType.ATTENDANCE_SESSION_OPENED: NotificationPriority.MEDIUM,
    NotificationType.ATTENDANCE_SESSION_CLOSED: NotificationPriority.HIGH,
    NotificationType.LOW_ATTENDANCE_ALERT: NotificationPriority.URGENT,
    NotificationType.ATTENDANCE_MARKED: NotificationPriority.LOW,
    
    NotificationType.ASSIGNMENT_PUBLISHED: NotificationPriority.MEDIUM,
    NotificationType.ASSIGNMENT_DUE_SOON: NotificationPriority.HIGH,
    NotificationType.ASSIGNMENT_OVERDUE: NotificationPriority.URGENT,
    NotificationType.ASSIGNMENT_GRADED: NotificationPriority.MEDIUM,
    NotificationType.ASSIGNMENT_RETURNED: NotificationPriority.MEDIUM,
    NotificationType.SUBMISSION_RECEIVED: NotificationPriority.LOW,
    
    NotificationType.GRADE_PUBLISHED: NotificationPriority.HIGH,
    NotificationType.RESULT_DECLARED: NotificationPriority.HIGH,
    
    NotificationType.ANNOUNCEMENT: NotificationPriority.MEDIUM,
    NotificationType.FEE_REMINDER: NotificationPriority.HIGH,
    NotificationType.SYSTEM_ALERT: NotificationPriority.URGENT,
    NotificationType.PROFILE_UPDATE: NotificationPriority.LOW,
}
