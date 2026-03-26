from configuration.models import Configuration, FeatureFlag


class ConfigService:
    @staticmethod
    def get(key, default=None, tenant_key=None, sub_app="global"):
        # Prefer tenant-scoped config first, then global fallback.
        scoped_qs = Configuration.objects.filter(
            key=key,
            sub_app=sub_app,
            is_active=True,
        )

        if tenant_key:
            tenant_match = scoped_qs.filter(tenant_key=tenant_key).only("value").first()
            if tenant_match:
                return tenant_match.value

        global_match = scoped_qs.filter(tenant_key__isnull=True).only("value").first()
        if global_match:
            return global_match.value

        return default

    @staticmethod
    def get_bool(key, default=False, tenant_key=None, sub_app="global"):
        value = ConfigService.get(key, default, tenant_key=tenant_key, sub_app=sub_app)
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y"}


class FeatureFlagService:
    @staticmethod
    def is_enabled(key, default=False, tenant_key=None, sub_app="global"):
        scoped_qs = FeatureFlag.objects.filter(
            key=key,
            sub_app=sub_app,
            is_active=True,
        )

        if tenant_key:
            tenant_match = scoped_qs.filter(tenant_key=tenant_key).only("is_enabled").first()
            if tenant_match:
                return tenant_match.is_enabled

        global_match = scoped_qs.filter(tenant_key__isnull=True).only("is_enabled").first()
        if global_match:
            return global_match.is_enabled

        return default
