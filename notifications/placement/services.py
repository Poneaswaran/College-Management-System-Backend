"""
Placement notification services.
Creates notifications for placement-related events.
"""
import logging
from typing import Optional

from django.contrib.auth import get_user_model

from notifications.models import Notification
from notifications.constants import NotificationType, NotificationPriority
from notifications.services.notification_service import create_notification
from notifications.services.broadcast_service import broadcast_notification


User = get_user_model()
logger = logging.getLogger(__name__)


def _get_application_context(application):
    drive = getattr(application, "drive", None)
    company = getattr(drive, "company", None) if drive else None
    student = getattr(application, "student", None)

    drive_title = getattr(drive, "title", None) or "Placement Drive"
    company_name = getattr(company, "name", None) or "Company"
    student_user = getattr(student, "user", None)

    return {
        "drive": drive,
        "company": company,
        "student_user": student_user,
        "drive_title": drive_title,
        "company_name": company_name,
    }


def notify_application_confirmed(application, actor: Optional[User] = None) -> Optional[Notification]:
    """
    Notify a student when their application is received.
    """
    try:
        context = _get_application_context(application)
        student_user = context["student_user"]
        if not student_user:
            logger.warning("Placement application confirmed skipped - student user missing")
            return None

        title = f"Application submitted: {context['drive_title']}"
        message = (
            f"Your application for {context['drive_title']} at {context['company_name']} "
            f"has been received."
        )

        metadata = {
            "application_id": application.id,
            "drive_id": context["drive"].id if context["drive"] else None,
            "drive_title": context["drive_title"],
            "company_id": context["company"].id if context["company"] else None,
            "company_name": context["company_name"],
            "status": getattr(application, "status", None),
        }

        notification = create_notification(
            recipient=student_user,
            notification_type=NotificationType.PLACEMENT_APPLICATION_CONFIRMED,
            title=title,
            message=message,
            action_url="/student/placements",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.MEDIUM,
        )

        broadcast_notification(student_user.id, {
            "id": notification.id,
            "notification_type": NotificationType.PLACEMENT_APPLICATION_CONFIRMED,
            "title": title,
            "message": message,
            "category": "PLACEMENT",
            "priority": NotificationPriority.MEDIUM,
            "action_url": "/student/placements",
            "metadata": metadata,
        })

        logger.info("Placement application confirmed notification sent to user %s", student_user.id)
        return notification
    except Exception as exc:
        logger.error("Failed to notify placement application confirmed: %s", str(exc))
        raise


def notify_application_shortlisted(application, actor: Optional[User] = None) -> Optional[Notification]:
    """
    Notify a student when they are shortlisted for a placement drive.
    """
    try:
        context = _get_application_context(application)
        student_user = context["student_user"]
        if not student_user:
            logger.warning("Placement application shortlisted skipped - student user missing")
            return None

        title = f"Shortlisted: {context['drive_title']}"
        message = (
            f"Good news! You have been shortlisted for {context['drive_title']} at "
            f"{context['company_name']}."
        )

        metadata = {
            "application_id": application.id,
            "drive_id": context["drive"].id if context["drive"] else None,
            "drive_title": context["drive_title"],
            "company_id": context["company"].id if context["company"] else None,
            "company_name": context["company_name"],
            "status": getattr(application, "status", None),
        }

        notification = create_notification(
            recipient=student_user,
            notification_type=NotificationType.PLACEMENT_APPLICATION_SHORTLISTED,
            title=title,
            message=message,
            action_url="/student/placements",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.HIGH,
        )

        broadcast_notification(student_user.id, {
            "id": notification.id,
            "notification_type": NotificationType.PLACEMENT_APPLICATION_SHORTLISTED,
            "title": title,
            "message": message,
            "category": "PLACEMENT",
            "priority": NotificationPriority.HIGH,
            "action_url": "/student/placements",
            "metadata": metadata,
        })

        logger.info("Placement application shortlisted notification sent to user %s", student_user.id)
        return notification
    except Exception as exc:
        logger.error("Failed to notify placement application shortlisted: %s", str(exc))
        raise


def notify_application_selected(application, actor: Optional[User] = None) -> Optional[Notification]:
    """
    Notify a student when they are selected for a placement drive.
    """
    try:
        context = _get_application_context(application)
        student_user = context["student_user"]
        if not student_user:
            logger.warning("Placement application selected skipped - student user missing")
            return None

        title = f"Selected: {context['drive_title']}"
        message = (
            f"Congratulations! You have been selected for {context['drive_title']} at "
            f"{context['company_name']}."
        )

        metadata = {
            "application_id": application.id,
            "drive_id": context["drive"].id if context["drive"] else None,
            "drive_title": context["drive_title"],
            "company_id": context["company"].id if context["company"] else None,
            "company_name": context["company_name"],
            "status": getattr(application, "status", None),
        }

        notification = create_notification(
            recipient=student_user,
            notification_type=NotificationType.PLACEMENT_APPLICATION_SELECTED,
            title=title,
            message=message,
            action_url="/student/placements",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.HIGH,
        )

        broadcast_notification(student_user.id, {
            "id": notification.id,
            "notification_type": NotificationType.PLACEMENT_APPLICATION_SELECTED,
            "title": title,
            "message": message,
            "category": "PLACEMENT",
            "priority": NotificationPriority.HIGH,
            "action_url": "/student/placements",
            "metadata": metadata,
        })

        logger.info("Placement application selected notification sent to user %s", student_user.id)
        return notification
    except Exception as exc:
        logger.error("Failed to notify placement application selected: %s", str(exc))
        raise


def notify_application_rejected(application, actor: Optional[User] = None) -> Optional[Notification]:
    """
    Notify a student when their placement application is rejected.
    """
    try:
        context = _get_application_context(application)
        student_user = context["student_user"]
        if not student_user:
            logger.warning("Placement application rejected skipped - student user missing")
            return None

        title = f"Application update: {context['drive_title']}"
        message = (
            f"Your application for {context['drive_title']} at {context['company_name']} "
            f"was not selected. Keep applying to other drives."
        )

        metadata = {
            "application_id": application.id,
            "drive_id": context["drive"].id if context["drive"] else None,
            "drive_title": context["drive_title"],
            "company_id": context["company"].id if context["company"] else None,
            "company_name": context["company_name"],
            "status": getattr(application, "status", None),
        }

        notification = create_notification(
            recipient=student_user,
            notification_type=NotificationType.PLACEMENT_APPLICATION_REJECTED,
            title=title,
            message=message,
            action_url="/student/placements",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.MEDIUM,
        )

        broadcast_notification(student_user.id, {
            "id": notification.id,
            "notification_type": NotificationType.PLACEMENT_APPLICATION_REJECTED,
            "title": title,
            "message": message,
            "category": "PLACEMENT",
            "priority": NotificationPriority.MEDIUM,
            "action_url": "/student/placements",
            "metadata": metadata,
        })

        logger.info("Placement application rejected notification sent to user %s", student_user.id)
        return notification
    except Exception as exc:
        logger.error("Failed to notify placement application rejected: %s", str(exc))
        raise


def notify_offer_uploaded(offer, actor: Optional[User] = None) -> Optional[Notification]:
    """
    Notify a student when their placement offer letter is uploaded.
    """
    try:
        application = getattr(offer, "application", None)
        if not application:
            logger.warning("Placement offer uploaded skipped - application missing")
            return None

        context = _get_application_context(application)
        student_user = context["student_user"]
        if not student_user:
            logger.warning("Placement offer uploaded skipped - student user missing")
            return None

        title = f"Offer available: {context['drive_title']}"
        message = (
            f"An offer letter for {context['drive_title']} at {context['company_name']} "
            f"is now available. Please review your offer details."
        )

        metadata = {
            "offer_id": offer.id,
            "application_id": application.id,
            "drive_id": context["drive"].id if context["drive"] else None,
            "drive_title": context["drive_title"],
            "company_id": context["company"].id if context["company"] else None,
            "company_name": context["company_name"],
            "ctc": float(getattr(offer, "ctc", 0)) if getattr(offer, "ctc", None) is not None else None,
            "joining_date": getattr(offer, "joining_date", None).isoformat()
            if getattr(offer, "joining_date", None)
            else None,
        }

        notification = create_notification(
            recipient=student_user,
            notification_type=NotificationType.PLACEMENT_OFFER_UPLOADED,
            title=title,
            message=message,
            action_url="/student/placements",
            metadata=metadata,
            actor=actor,
            priority=NotificationPriority.HIGH,
        )

        broadcast_notification(student_user.id, {
            "id": notification.id,
            "notification_type": NotificationType.PLACEMENT_OFFER_UPLOADED,
            "title": title,
            "message": message,
            "category": "PLACEMENT",
            "priority": NotificationPriority.HIGH,
            "action_url": "/student/placements",
            "metadata": metadata,
        })

        logger.info("Placement offer uploaded notification sent to user %s", student_user.id)
        return notification
    except Exception as exc:
        logger.error("Failed to notify placement offer uploaded: %s", str(exc))
        raise
