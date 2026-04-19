import logging

from configuration.services.config_service import ConfigService
from notifications.services.delivery_service import NotificationService
from onboarding.async_queue import async_task

logger = logging.getLogger(__name__)


class EventDispatcher:
    @staticmethod
    def dispatch(event_name, payload):
        events_cfg = ConfigService.get("notifications.events", default={}) or {}
        flags = ConfigService.get("notifications.flags", default={}) or {}

        event_cfg = events_cfg.get(event_name, {}) if isinstance(events_cfg, dict) else {}
        email_enabled = bool(event_cfg.get("email", False)) and bool(flags.get("enable_email_notifications", True))
        sms_enabled = bool(event_cfg.get("sms", False)) and bool(flags.get("enable_sms_notifications", False))

        recipient_email = payload.get("email") if isinstance(payload, dict) else None
        recipient_phone = payload.get("phone") if isinstance(payload, dict) else None

        if event_name == "LEGACY_EMAIL" and recipient_email:
            email_enabled = bool(flags.get("enable_email_notifications", True))

        if email_enabled and recipient_email:
            subject = payload.get("subject", f"Onboarding Event: {event_name}") if isinstance(payload, dict) else f"Onboarding Event: {event_name}"
            message = payload.get("message", str(payload)) if isinstance(payload, dict) else str(payload)
            async_task(NotificationService.send_email, subject, message, [recipient_email])

        if sms_enabled and recipient_phone:
            message = f"{event_name}: {payload}"
            async_task(NotificationService.send_sms, recipient_phone, message)

        logger.info("event_dispatched name=%s payload=%s", event_name, payload)
