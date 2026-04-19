import logging

from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def send_email(subject, message, recipient_list, from_email=None):
        if not recipient_list:
            return
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=True,
        )

    @staticmethod
    def send_sms(phone_number, message):
        # Placeholder for SMS integration. Kept intentionally lightweight.
        logger.info("sms_notification phone=%s message=%s", phone_number, message)
