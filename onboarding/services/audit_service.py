import logging

from onboarding.models import OnboardingAuditLog

logger = logging.getLogger(__name__)


class OnboardingAuditService:
    @staticmethod
    def log(action, entity_type, entity_id="", actor=None, metadata=None):
        payload = metadata or {}
        OnboardingAuditLog.objects.create(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id or ""),
            actor=actor,
            metadata=payload,
        )
        logger.info(
            "onboarding_audit action=%s entity_type=%s entity_id=%s actor_id=%s metadata=%s",
            action,
            entity_type,
            entity_id,
            getattr(actor, "id", None),
            payload,
        )
