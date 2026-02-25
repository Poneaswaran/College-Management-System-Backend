"""
Attendance notification services.
Creates notifications for attendance-related events.
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


def notify_session_opened(
    session,
    students: List[User],
    actor: Optional[User] = None
) -> List[Notification]:
    """
    Notify all students in a section that an attendance session has been opened.
    
    Args:
        session: AttendanceSession instance
        students: List of students to notify
        actor: Faculty who opened the session
        
    Returns:
        List of created notifications
    """
    try:
        # Get subject and section names
        subject_name = session.subject.name if hasattr(session, 'subject') else "Unknown Subject"
        section_name = session.section.name if hasattr(session, 'section') else "Unknown Section"
        
        title = f"Attendance Opened: {subject_name}"
        message = (
            f"Attendance session for {subject_name} ({section_name}) is now open. "
            f"Please mark your attendance."
        )
        
        metadata = {
            "session_id": session.id,
            "subject_name": subject_name,
            "section_name": section_name,
            "subject_id": session.subject.id if hasattr(session, 'subject') else None,
            "section_id": session.section.id if hasattr(session, 'section') else None,
        }
        
        # Bulk create notifications
        notifications = bulk_create_notifications(
            recipients=students,
            notification_type=NotificationType.ATTENDANCE_SESSION_OPENED,
            title=title,
            message=message,
            action_url="/student/mark-attendance",
            metadata=metadata,
            actor=actor,
        )
        
        # Broadcast to all students via Redis/SSE
        notification_data = {
            "id": notifications[0].id if notifications else None,
            "notification_type": NotificationType.ATTENDANCE_SESSION_OPENED,
            "title": title,
            "message": message,
            "category": "ATTENDANCE",
            "priority": NotificationPriority.MEDIUM,
            "action_url": "/student/mark-attendance",
            "metadata": metadata,
        }
        
        user_ids = [student.id for student in students]
        broadcast_to_multiple_users(user_ids, notification_data)
        
        logger.info(
            f"Notified {len(notifications)} students about attendance session {session.id}"
        )
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to notify session opened for session {session.id}: {str(e)}")
        raise


def notify_session_closed_absent(
    session,
    absent_students: List[User],
    actor: Optional[User] = None
) -> List[Notification]:
    """
    Notify students who missed attendance that the session has closed.
    
    Args:
        session: AttendanceSession instance
        absent_students: List of students who didn't mark attendance
        actor: Faculty who closed the session
        
    Returns:
        List of created notifications
    """
    try:
        subject_name = session.subject.name if hasattr(session, 'subject') else "Unknown Subject"
        section_name = session.section.name if hasattr(session, 'section') else "Unknown Section"
        
        title = f"Missed Attendance: {subject_name}"
        message = (
            f"You missed marking attendance for {subject_name} ({section_name}). "
            f"The session is now closed."
        )
        
        metadata = {
            "session_id": session.id,
            "subject_name": subject_name,
            "section_name": section_name,
            "subject_id": session.subject.id if hasattr(session, 'subject') else None,
            "section_id": session.section.id if hasattr(session, 'section') else None,
            "status": "absent",
        }
        
        # Bulk create notifications with HIGH priority
        notifications = bulk_create_notifications(
            recipients=absent_students,
            notification_type=NotificationType.ATTENDANCE_SESSION_CLOSED,
            title=title,
            message=message,
            action_url="/student/attendance",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.HIGH,
        )
        
        # Broadcast to absent students
        notification_data = {
            "id": notifications[0].id if notifications else None,
            "notification_type": NotificationType.ATTENDANCE_SESSION_CLOSED,
            "title": title,
            "message": message,
            "category": "ATTENDANCE",
            "priority": NotificationPriority.HIGH,
            "action_url": "/student/attendance",
            "metadata": metadata,
        }
        
        user_ids = [student.id for student in absent_students]
        broadcast_to_multiple_users(user_ids, notification_data)
        
        logger.info(
            f"Notified {len(notifications)} absent students about session {session.id} closure"
        )
        
        return notifications
        
    except Exception as e:
        logger.error(
            f"Failed to notify absent students for session {session.id}: {str(e)}"
        )
        raise


def notify_low_attendance(
    student: User,
    subject,
    percentage: float,
    threshold: float = 75.0
) -> Notification:
    """
    Notify a student when their attendance drops below threshold.
    
    Args:
        student: Student to notify
        subject: Subject with low attendance
        percentage: Current attendance percentage
        threshold: Minimum required percentage
        
    Returns:
        Created notification
    """
    try:
        subject_name = subject.name if hasattr(subject, 'name') else "Unknown Subject"
        
        title = f"Low Attendance Alert: {subject_name}"
        message = (
            f"Your attendance in {subject_name} has dropped to {percentage:.1f}%. "
            f"Minimum required: {threshold:.1f}%. Please improve your attendance."
        )
        
        metadata = {
            "subject_name": subject_name,
            "subject_id": subject.id if hasattr(subject, 'id') else None,
            "current_percentage": percentage,
            "required_percentage": threshold,
        }
        
        # Create URGENT notification
        notification = create_notification(
            recipient=student,
            notification_type=NotificationType.LOW_ATTENDANCE_ALERT,
            title=title,
            message=message,
            action_url="/student/attendance",
            metadata=metadata,
            priority=NotificationPriority.URGENT,
        )
        
        # Broadcast via SSE
        notification_data = {
            "id": notification.id,
            "notification_type": NotificationType.LOW_ATTENDANCE_ALERT,
            "title": title,
            "message": message,
            "category": "ATTENDANCE",
            "priority": NotificationPriority.URGENT,
            "action_url": "/student/attendance",
            "metadata": metadata,
        }
        
        broadcast_notification(student.id, notification_data)
        
        logger.info(
            f"Notified student {student.id} about low attendance in subject {subject.id if hasattr(subject, 'id') else 'N/A'}"
        )
        
        return notification
        
    except Exception as e:
        logger.error(
            f"Failed to notify low attendance for student {student.id}: {str(e)}"
        )
        raise


def notify_attendance_marked(
    student: User,
    session,
    status: str,
    actor: Optional[User] = None
) -> Notification:
    """
    Notify a student when their attendance has been marked.
    
    Args:
        student: Student whose attendance was marked
        session: AttendanceSession instance
        status: Attendance status (PRESENT, ABSENT, LATE, etc.)
        actor: Faculty who marked the attendance
        
    Returns:
        Created notification
    """
    try:
        subject_name = session.subject.name if hasattr(session, 'subject') else "Unknown Subject"
        
        title = f"Attendance Marked: {subject_name}"
        
        if status == "PRESENT":
            message = f"Your attendance for {subject_name} has been marked as Present."
        elif status == "ABSENT":
            message = f"Your attendance for {subject_name} has been marked as Absent."
        else:
            message = f"Your attendance for {subject_name} has been marked as {status}."
        
        metadata = {
            "session_id": session.id,
            "subject_name": subject_name,
            "subject_id": session.subject.id if hasattr(session, 'subject') else None,
            "status": status,
        }
        
        notification = create_notification(
            recipient=student,
            notification_type=NotificationType.ATTENDANCE_MARKED,
            title=title,
            message=message,
            action_url="/student/attendance",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.LOW,
        )
        
        # Broadcast via SSE
        notification_data = {
            "id": notification.id,
            "notification_type": NotificationType.ATTENDANCE_MARKED,
            "title": title,
            "message": message,
            "category": "ATTENDANCE",
            "priority": NotificationPriority.LOW,
            "action_url": "/student/attendance",
            "metadata": metadata,
        }
        
        broadcast_notification(student.id, notification_data)
        
        return notification
        
    except Exception as e:
        logger.error(
            f"Failed to notify attendance marked for student {student.id}: {str(e)}"
        )
        raise
