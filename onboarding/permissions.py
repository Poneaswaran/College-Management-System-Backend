from django.utils import timezone
from rest_framework import permissions

from onboarding.models import TemporaryOnboardingAccess


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return hasattr(user, "role") and user.role and user.role.code in ["ADMIN", "SUPER_ADMIN"]


class OnboardingAccessPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if IsAdminRole().has_permission(request, view):
            return True

        role_code = getattr(getattr(user, "role", None), "code", None)
        if role_code not in {"FACULTY", "HOD"}:
            return False

        required_scope = getattr(view, "onboarding_entity_type", None)
        action = getattr(view, "onboarding_action", "bulk_upload")
        now = timezone.now()

        grant = (
            TemporaryOnboardingAccess.objects.filter(
                faculty_user=user,
                is_active=True,
                expires_at__gt=now,
            )
            .order_by("-created_at")
            .first()
        )
        if not grant:
            return False

        if required_scope and grant.scope not in {required_scope, TemporaryOnboardingAccess.SCOPE_ALL}:
            return False

        if action == "retry" and not grant.can_retry:
            return False

        if action == "bulk_upload" and not grant.can_bulk_upload:
            return False

        return True
