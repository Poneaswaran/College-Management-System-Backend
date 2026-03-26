from configuration.models import Configuration


class ConfigService:
    @staticmethod
    def get(key, default=None):
        config = Configuration.objects.filter(key=key, is_active=True).only("value").first()
        if not config:
            return default
        return config.value

    @staticmethod
    def get_bool(key, default=False):
        value = ConfigService.get(key, default)
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y"}
