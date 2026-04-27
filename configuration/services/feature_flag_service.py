from django.db import connection
from django.core.cache import cache
CACHE_TTL = 300  # 5 minutes
# All valid feature flag keys — single source of truth
KNOWN_FLAGS = [
    "timetable_assignment",
    "pdf_export",
    "ai_copilot",
    "schedule_audit",
    "exam_module",
    "attendance_analytics",
    "faculty_workload",
    "leave_approval",
    "grade_submission",
    "study_materials",
    "hod_courses",
    "hod_curriculum",
]
class FeatureFlagService:
    @staticmethod
    def is_enabled(key: str) -> bool:
        """
        Returns True if the feature is ON for the current tenant.
        Resolution order:
          1. TenantFeatureOverride for this schema → use it if exists
          2. FeatureFlag.is_enabled_globally → fallback
          3. False → if flag key doesn't exist at all
        Uses per-tenant cache to avoid repeated DB hits.
        """
        from configuration.models import FeatureFlag, TenantFeatureOverride
        schema = connection.tenant.schema_name
        cache_key = f"ff:{schema}:{key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            flag = FeatureFlag.objects.get(key=key)
        except FeatureFlag.DoesNotExist:
            return False
        override = TenantFeatureOverride.objects.filter(
            flag=flag, schema_name=schema
        ).first()
        result = override.is_enabled if override is not None else flag.is_enabled_globally
        cache.set(cache_key, result, timeout=CACHE_TTL)
        return result
    @staticmethod
    def get_all_flags() -> dict[str, bool]:
        """
        Returns all known flags and their resolved values for the current tenant.
        Used by the frontend flags API endpoint.
        """
        return {
            key: FeatureFlagService.is_enabled(key)
            for key in KNOWN_FLAGS
        }
    @staticmethod
    def invalidate_cache(schema_name: str, key: str):
        """Call this after any flag override is saved/deleted via admin or API."""
        cache.delete(f"ff:{schema_name}:{key}")
