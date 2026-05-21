from rest_framework.permissions import BasePermission


def _get_role_value(user):
    role = getattr(user, "role", None)
    if role is None:
        return None
    return getattr(role, "code", role)


class IsPlacementOfficer(BasePermission):
    def has_permission(self, request, view):
        role_value = _get_role_value(request.user)
        if isinstance(role_value, str):
            role_value = role_value.lower()
        return bool(
            request.user
            and request.user.is_authenticated
            and (role_value == "placement_officer" or request.user.is_staff)
        )


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        role_value = _get_role_value(request.user)
        if isinstance(role_value, str):
            role_value = role_value.lower()
        return bool(
            request.user
            and request.user.is_authenticated
            and role_value == "student"
        )


class IsPlacementOfficerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        role_value = _get_role_value(request.user)
        if isinstance(role_value, str):
            role_value = role_value.lower()
        return role_value in ("placement_officer", "admin") or request.user.is_staff
