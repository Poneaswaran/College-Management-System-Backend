import logging

from notifications.services.event_dispatcher import EventDispatcher

from onboarding.constants import (
    ONBOARDING_EVENT_FACULTY_CREATED,
    ONBOARDING_EVENT_ID_CARD_GENERATED,
    ONBOARDING_EVENT_STUDENT_CREATED,
)

logger = logging.getLogger(__name__)


class EventService:
    @staticmethod
    def emit(event_name, payload):
        EventDispatcher.dispatch(event_name, payload)
        logger.info("onboarding_event name=%s payload=%s", event_name, payload)

    @staticmethod
    def emit_student_created(registration_number, user_email):
        EventService.emit(
            ONBOARDING_EVENT_STUDENT_CREATED,
            {"registration_number": registration_number, "email": user_email},
        )

    @staticmethod
    def emit_faculty_created(employee_id, user_email):
        EventService.emit(
            ONBOARDING_EVENT_FACULTY_CREATED,
            {"employee_id": employee_id, "email": user_email},
        )

    @staticmethod
    def emit_id_card_generated(entity_type, card_number, user_email):
        EventService.emit(
            ONBOARDING_EVENT_ID_CARD_GENERATED,
            {"entity_type": entity_type, "card_number": card_number, "email": user_email},
        )

    @staticmethod
    def enqueue_optional_email(subject, message, recipient_list, from_email=None):
        # Backward compatibility shim. Prefer event-dispatcher based notifications.
        EventDispatcher.dispatch(
            "LEGACY_EMAIL",
            {
                "subject": subject,
                "message": message,
                "email": recipient_list[0] if recipient_list else None,
            },
        )

    @staticmethod
    def _send_email(subject, message, recipient_list, from_email=None):
        EventDispatcher.dispatch(
            "LEGACY_EMAIL",
            {
                "subject": subject,
                "message": message,
                "email": recipient_list[0] if recipient_list else None,
            },
        )
