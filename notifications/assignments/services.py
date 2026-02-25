"""
Assignment notification services.
Creates notifications for assignment-related events.
"""
import logging
from typing import List, Optional
from datetime import datetime
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


def notify_assignment_published(
    assignment,
    students: List[User],
    actor: Optional[User] = None
) -> List[Notification]:
    """
    Notify all students when a new assignment is published.
    
    Args:
        assignment: Assignment instance
        students: List of students to notify
        actor: Faculty who published the assignment
        
    Returns:
        List of created notifications
    """
    try:
        assignment_title = assignment.title if hasattr(assignment, 'title') else "New Assignment"
        subject_name = assignment.subject.name if hasattr(assignment, 'subject') else "Unknown Subject"
        due_date = assignment.due_date if hasattr(assignment, 'due_date') else None
        
        title = f"New Assignment: {assignment_title}"
        message = f"A new assignment '{assignment_title}' has been published for {subject_name}."
        
        if due_date:
            message += f" Due date: {due_date.strftime('%B %d, %Y at %I:%M %p')}"
        
        metadata = {
            "assignment_id": assignment.id if hasattr(assignment, 'id') else None,
            "assignment_title": assignment_title,
            "subject_name": subject_name,
            "subject_id": assignment.subject.id if hasattr(assignment, 'subject') else None,
            "due_date": due_date.isoformat() if due_date else None,
        }
        
        # Bulk create notifications
        notifications = bulk_create_notifications(
            recipients=students,
            notification_type=NotificationType.ASSIGNMENT_PUBLISHED,
            title=title,
            message=message,
            action_url="/student/assignments",
            metadata=metadata,
            actor=actor,
        )
        
        # Broadcast to all students
        notification_data = {
            "id": notifications[0].id if notifications else None,
            "notification_type": NotificationType.ASSIGNMENT_PUBLISHED,
            "title": title,
            "message": message,
            "category": "ASSIGNMENT",
            "priority": NotificationPriority.MEDIUM,
            "action_url": "/student/assignments",
            "metadata": metadata,
        }
        
        user_ids = [student.id for student in students]
        broadcast_to_multiple_users(user_ids, notification_data)
        
        logger.info(
            f"Notified {len(notifications)} students about new assignment {assignment.id if hasattr(assignment, 'id') else 'N/A'}"
        )
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to notify assignment published: {str(e)}")
        raise


def notify_assignment_graded(
    student: User,
    assignment,
    grade_value: str,
    actor: Optional[User] = None
) -> Notification:
    """
    Notify a student when their assignment has been graded.
    
    Args:
        student: Student to notify
        assignment: Assignment instance
        grade_value: Grade received
        actor: Faculty who graded the assignment
        
    Returns:
        Created notification
    """
    try:
        assignment_title = assignment.title if hasattr(assignment, 'title') else "Assignment"
        subject_name = assignment.subject.name if hasattr(assignment, 'subject') else "Unknown Subject"
        
        title = f"Assignment Graded: {assignment_title}"
        message = f"Your assignment '{assignment_title}' for {subject_name} has been graded: {grade_value}"
        
        metadata = {
            "assignment_id": assignment.id if hasattr(assignment, 'id') else None,
            "assignment_title": assignment_title,
            "subject_name": subject_name,
            "subject_id": assignment.subject.id if hasattr(assignment, 'subject') else None,
            "grade": grade_value,
        }
        
        notification = create_notification(
            recipient=student,
            notification_type=NotificationType.ASSIGNMENT_GRADED,
            title=title,
            message=message,
            action_url="/student/assignments",
            metadata=metadata,
            actor=actor,
        )
        
        # Broadcast via SSE
        notification_data = {
            "id": notification.id,
            "notification_type": NotificationType.ASSIGNMENT_GRADED,
            "title": title,
            "message": message,
            "category": "ASSIGNMENT",
            "priority": NotificationPriority.MEDIUM,
            "action_url": "/student/assignments",
            "metadata": metadata,
        }
        
        broadcast_notification(student.id, notification_data)
        
        logger.info(f"Notified student {student.id} about graded assignment {assignment.id if hasattr(assignment, 'id') else 'N/A'}")
        
        return notification
        
    except Exception as e:
        logger.error(f"Failed to notify assignment graded for student {student.id}: {str(e)}")
        raise


def notify_submission_received(
    faculty: User,
    student: User,
    assignment
) -> Notification:
    """
    Notify faculty when a student submits an assignment.
    
    Args:
        faculty: Faculty to notify
        student: Student who submitted
        assignment: Assignment instance
        
    Returns:
        Created notification
    """
    try:
        assignment_title = assignment.title if hasattr(assignment, 'title') else "Assignment"
        student_name = student.get_full_name() or student.email
        
        title = f"New Submission: {assignment_title}"
        message = f"{student_name} has submitted the assignment '{assignment_title}'."
        
        metadata = {
            "assignment_id": assignment.id if hasattr(assignment, 'id') else None,
            "assignment_title": assignment_title,
            "student_id": student.id,
            "student_name": student_name,
        }
        
        notification = create_notification(
            recipient=faculty,
            notification_type=NotificationType.SUBMISSION_RECEIVED,
            title=title,
            message=message,
            action_url="/faculty/assignments",
            metadata=metadata,
            actor=student,
            priority=NotificationPriority.LOW,
        )
        
        # Broadcast via SSE
        notification_data = {
            "id": notification.id,
            "notification_type": NotificationType.SUBMISSION_RECEIVED,
            "title": title,
            "message": message,
            "category": "ASSIGNMENT",
            "priority": NotificationPriority.LOW,
            "action_url": "/faculty/assignments",
            "metadata": metadata,
        }
        
        broadcast_notification(faculty.id, notification_data)
        
        logger.info(f"Notified faculty {faculty.id} about submission from student {student.id}")
        
        return notification
        
    except Exception as e:
        logger.error(f"Failed to notify submission received: {str(e)}")
        raise


def notify_assignment_due_soon(
    assignment,
    students: List[User],
    hours_remaining: int
) -> List[Notification]:
    """
    Notify students that an assignment is due soon.
    
    Args:
        assignment: Assignment instance
        students: List of students to notify
        hours_remaining: Hours until deadline
        
    Returns:
        List of created notifications
    """
    try:
        assignment_title = assignment.title if hasattr(assignment, 'title') else "Assignment"
        subject_name = assignment.subject.name if hasattr(assignment, 'subject') else "Unknown Subject"
        
        title = f"Assignment Due Soon: {assignment_title}"
        message = (
            f"Reminder: '{assignment_title}' for {subject_name} is due in {hours_remaining} hours. "
            f"Please submit before the deadline."
        )
        
        metadata = {
            "assignment_id": assignment.id if hasattr(assignment, 'id') else None,
            "assignment_title": assignment_title,
            "subject_name": subject_name,
            "hours_remaining": hours_remaining,
        }
        
        notifications = bulk_create_notifications(
            recipients=students,
            notification_type=NotificationType.ASSIGNMENT_DUE_SOON,
            title=title,
            message=message,
            action_url="/student/assignments",
            metadata=metadata,
            priority=NotificationPriority.HIGH,
        )
        
        # Broadcast to all students
        notification_data = {
            "id": notifications[0].id if notifications else None,
            "notification_type": NotificationType.ASSIGNMENT_DUE_SOON,
            "title": title,
            "message": message,
            "category": "ASSIGNMENT",
            "priority": NotificationPriority.HIGH,
            "action_url": "/student/assignments",
            "metadata": metadata,
        }
        
        user_ids = [student.id for student in students]
        broadcast_to_multiple_users(user_ids, notification_data)
        
        logger.info(f"Notified {len(notifications)} students about assignment due soon")
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to notify assignment due soon: {str(e)}")
        raise


def notify_assignment_overdue(
    student: User,
    assignment
) -> Notification:
    """
    Notify a student that they missed an assignment deadline.
    
    Args:
        student: Student to notify
        assignment: Assignment instance
        
    Returns:
        Created notification
    """
    try:
        assignment_title = assignment.title if hasattr(assignment, 'title') else "Assignment"
        subject_name = assignment.subject.name if hasattr(assignment, 'subject') else "Unknown Subject"
        
        title = f"Assignment Overdue: {assignment_title}"
        message = (
            f"You have missed the deadline for '{assignment_title}' in {subject_name}. "
            f"Please contact your instructor."
        )
        
        metadata = {
            "assignment_id": assignment.id if hasattr(assignment, 'id') else None,
            "assignment_title": assignment_title,
            "subject_name": subject_name,
        }
        
        notification = create_notification(
            recipient=student,
            notification_type=NotificationType.ASSIGNMENT_OVERDUE,
            title=title,
            message=message,
            action_url="/student/assignments",
            metadata=metadata,
            priority=NotificationPriority.URGENT,
        )
        
        # Broadcast via SSE
        notification_data = {
            "id": notification.id,
            "notification_type": NotificationType.ASSIGNMENT_OVERDUE,
            "title": title,
            "message": message,
            "category": "ASSIGNMENT",
            "priority": NotificationPriority.URGENT,
            "action_url": "/student/assignments",
            "metadata": metadata,
        }
        
        broadcast_notification(student.id, notification_data)
        
        logger.info(f"Notified student {student.id} about overdue assignment")
        
        return notification
        
    except Exception as e:
        logger.error(f"Failed to notify assignment overdue: {str(e)}")
        raise
