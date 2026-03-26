from django.contrib import admin

from configuration.models import Configuration


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ["key", "is_active", "updated_at"]
    search_fields = ["key", "description"]
    list_filter = ["is_active"]
