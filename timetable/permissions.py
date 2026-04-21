from rest_framework.permissions import BasePermission


class IsHOD(BasePermission):
    message = "Only HOD users can access this endpoint."

    def has_permission(self, request, view):
        user = request.user
        role_code = getattr(getattr(user, "role", None), "code", None)
        return bool(user and user.is_authenticated and role_code == "HOD")
