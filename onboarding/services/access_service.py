from django.contrib.auth import get_user_model
from django.db import transaction

from onboarding.models import TemporaryOnboardingAccess
from onboarding.services.audit_service import OnboardingAuditService

User = get_user_model()


class TemporaryAccessService:
    @staticmethod
    @transaction.atomic
    def grant(*, faculty_user_id, granted_by, scope, expires_at, can_bulk_upload=True, can_retry=True):
        faculty_user = User.objects.get(id=faculty_user_id)

        role_code = getattr(getattr(faculty_user, "role", None), "code", None)
        if role_code not in {"FACULTY", "HOD"}:
            raise ValueError("Temporary onboarding access can be granted only to FACULTY or HOD users")

        access = TemporaryOnboardingAccess.objects.create(
            faculty_user=faculty_user,
            granted_by=granted_by,
            scope=scope,
            expires_at=expires_at,
            can_bulk_upload=can_bulk_upload,
            can_retry=can_retry,
            is_active=True,
        )

        OnboardingAuditService.log(
            action="TEMP_ACCESS_GRANTED",
            entity_type="FACULTY",
            entity_id=faculty_user.id,
            actor=granted_by,
            metadata={
                "scope": scope,
                "expires_at": expires_at.isoformat(),
                "can_bulk_upload": can_bulk_upload,
                "can_retry": can_retry,
            },
        )
        return access

    @staticmethod
    @transaction.atomic
    def revoke(*, access_id, revoked_by):
        access = TemporaryOnboardingAccess.objects.select_related("faculty_user").get(id=access_id)
        access.is_active = False
        access.save(update_fields=["is_active", "updated_at"])

        OnboardingAuditService.log(
            action="TEMP_ACCESS_REVOKED",
            entity_type="FACULTY",
            entity_id=access.faculty_user_id,
            actor=revoked_by,
            metadata={"access_id": access_id},
        )
        return access
