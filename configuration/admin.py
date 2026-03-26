from django.contrib import admin

from configuration.models import Configuration, FeatureFlag


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ["tenant_key", "sub_app", "key", "is_active", "updated_at"]
    search_fields = ["tenant_key", "sub_app", "key", "description"]
    list_filter = ["sub_app", "is_active"]


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ["tenant_key", "sub_app", "key", "is_enabled", "is_active", "updated_at"]
    search_fields = ["tenant_key", "sub_app", "key", "description"]
    list_filter = ["sub_app", "is_enabled", "is_active"]
