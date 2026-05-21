import logging

from onboarding.async_queue import async_task
from notifications.placement import services as placement_notifications

from .models import PlacementOffer, StudentApplication


logger = logging.getLogger(__name__)


class AsyncTaskWrapper:
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def delay(self, *args, **kwargs):
        return async_task(self.func, *args, **kwargs)


def _get_application(application_id):
    try:
        app_id = int(application_id)
    except (TypeError, ValueError):
        logger.warning("Invalid application id for placement notification: %s", application_id)
        return None

    return (
        StudentApplication.objects.select_related(
            "student",
            "student__user",
            "drive",
            "drive__company",
        )
        .filter(id=app_id)
        .first()
    )


def _get_offer(offer_id):
    try:
        offer_pk = int(offer_id)
    except (TypeError, ValueError):
        logger.warning("Invalid offer id for placement notification: %s", offer_id)
        return None

    return (
        PlacementOffer.objects.select_related(
            "application",
            "application__student",
            "application__student__user",
            "application__drive",
            "application__drive__company",
        )
        .filter(id=offer_pk)
        .first()
    )


def notify_application_confirmed_task(application_id):
    application = _get_application(application_id)
    if not application:
        return None
    return placement_notifications.notify_application_confirmed(application)


def notify_shortlisted_task(application_id):
    application = _get_application(application_id)
    if not application:
        return None
    return placement_notifications.notify_application_shortlisted(application)


def notify_selected_task(application_id):
    application = _get_application(application_id)
    if not application:
        return None
    return placement_notifications.notify_application_selected(application)


def notify_rejected_task(application_id):
    application = _get_application(application_id)
    if not application:
        return None
    return placement_notifications.notify_application_rejected(application)


def notify_offer_uploaded_task(offer_id):
    offer = _get_offer(offer_id)
    if not offer:
        return None
    return placement_notifications.notify_offer_uploaded(offer)


notify_application_confirmed = AsyncTaskWrapper(notify_application_confirmed_task)
notify_shortlisted = AsyncTaskWrapper(notify_shortlisted_task)
notify_selected = AsyncTaskWrapper(notify_selected_task)
notify_rejected = AsyncTaskWrapper(notify_rejected_task)
notify_offer_uploaded = AsyncTaskWrapper(notify_offer_uploaded_task)
