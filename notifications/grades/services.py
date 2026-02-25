"""
Grade notification services.
Creates notifications for grade-related events.
"""
import logging
from typing import List, Optional
from django.contrib.auth import get_user_model

from notifications.models import Notification
from notifications.constants import NotificationType, NotificationPriority
from notifications.services.notification_service import (
    create_notification,
    bulk_create_notifications,
)
from notifications.services.broadcast_service import (
    broadcast_notification,
    broadcast_to_multiple_users,
)


User = get_user_model()
logger = logging.getLogger(__name__)


def notify_grade_published(
    student: User,
    subject,
    grade_value: str,
    grade_type: str = "Final Grade",
    actor: Optional[User] = None
) -> Notification:
    """
    Notify a student when a grade is published.
    
    Args:
        student: Student to notify
        subject: Subject for which grade is published
        grade_value: Grade value (A, B+, etc.)
        grade_type: Type of grade (Midterm, Final, etc.)
        actor: Faculty who published the grade
        
    Returns:
        Created notification
    """
    try:
        subject_name = subject.name if hasattr(subject, 'name') else "Unknown Subject"
        
        title = f"Grade Published: {subject_name}"
        message = f"Your {grade_type} for {subject_name} has been published: {grade_value}"
        
        metadata = {
            "subject_name": subject_name,
            "subject_id": subject.id if hasattr(subject, 'id') else None,
            "grade": grade_value,
            "grade_type": grade_type,
        }
        
        notification = create_notification(
            recipient=student,
            notification_type=NotificationType.GRADE_PUBLISHED,
            title=title,
            message=message,
            action_url="/student/grades",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.HIGH,
        )
        
        # Broadcast via SSE
        notification_data = {
            "id": notification.id,
            "notification_type": NotificationType.GRADE_PUBLISHED,
            "title": title,
            "message": message,
            "category": "GRADE",
            "priority": NotificationPriority.HIGH,
            "action_url": "/student/grades",
            "metadata": metadata,
        }
        
        broadcast_notification(student.id, notification_data)
        
        logger.info(f"Notified student {student.id} about grade published")
        
        return notification
        
    except Exception as e:
        logger.error(f"Failed to notify grade published for student {student.id}: {str(e)}")
        raise


def notify_result_declared(
    students: List[User],
    exam_name: str,
    semester: Optional[str] = None,
    actor: Optional[User] = None
) -> List[Notification]:
    """
    Notify students when semester results are declared.
    
    Args:
        students: List of students to notify
        exam_name: Name of exam (End Semester, Midterm, etc.)
        semester: Semester information
        actor: Admin/Faculty who declared results
        
    Returns:
        List of created notifications
    """
    try:
        title = f"Results Declared: {exam_name}"
        message = f"{exam_name} results have been declared. Check your grades now."
        
        if semester:
            message = f"{exam_name} results for {semester} have been declared. Check your grades now."
        
        metadata = {
            "exam_name": exam_name,
            "semester": semester,
        }
        
        notifications = bulk_create_notifications(
            recipients=students,
            notification_type=NotificationType.RESULT_DECLARED,
            title=title,
            message=message,
            action_url="/student/grades",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.HIGH,
        )
        
        # Broadcast to all students
        notification_data = {
            "id": notifications[0].id if notifications else None,
            "notification_type": NotificationType.RESULT_DECLARED,
            "title": title,
            "message": message,
            "category": "GRADE",
            "priority": NotificationPriority.HIGH,
            "action_url": "/student/grades",
            "metadata": metadata,
        }
        
        user_ids = [student.id for student in students]
        broadcast_to_multiple_users(user_ids, notification_data)
        
        logger.info(f"Notified {len(notifications)} students about result declaration")
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to notify result declared: {str(e)}")
        raise
