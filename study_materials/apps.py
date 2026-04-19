from django.apps import AppConfig


class StudyMaterialsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'study_materials'
    verbose_name = 'Study Materials'

    def ready(self):
        """Register signal handlers for study materials app."""
        from . import signals  # noqa: F401
