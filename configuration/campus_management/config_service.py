from configuration.models import Configuration

class CampusManagementConfiguration:
    """
    Utility to manage campus management specific configurations.
    Stored in the 'configuration' app under sub_app='campus_management'.
    """
    SUB_APP = "campus_management"

    @staticmethod
    def get_setting(key, default_value):
        try:
            config = Configuration.objects.get(sub_app=CampusManagementConfiguration.SUB_APP, key=key, is_active=True)
            return config.value
        except Configuration.DoesNotExist:
            return default_value

    @staticmethod
    def set_setting(key, value, description=""):
        config, created = Configuration.objects.update_or_create(
            sub_app=CampusManagementConfiguration.SUB_APP,
            key=key,
            defaults={'value': value, 'description': description, 'is_active': True}
        )
        return config

    @classmethod
    def get_building_limit(cls):
        return cls.get_setting("building_creation_limit", 100) # Default 100

    @classmethod
    def get_venues_per_floor_limit(cls):
        return cls.get_setting("venues_per_floor_limit", 20) # Default 20

    @classmethod
    def get_floor_limit_per_building(cls):
        return cls.get_setting("floor_limit_per_building", 50) # Default 50
