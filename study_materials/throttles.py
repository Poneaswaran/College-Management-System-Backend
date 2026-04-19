"""Custom throttling rules for study materials APIs."""

from rest_framework.throttling import UserRateThrottle


class AIChatUserThrottle(UserRateThrottle):
    """Rate-limit AI chat calls by authenticated user id."""

    scope = "ai_chat"

    def get_cache_key(self, request, view):
        """Return per-user cache key and never fall back to IP throttling."""
        if not request.user or not request.user.is_authenticated:
            return None

        ident = f"user_{request.user.pk}"
        return self.cache_format % {"scope": self.scope, "ident": ident}
