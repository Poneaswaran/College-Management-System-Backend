from django.contrib import admin

from configuration.models import Configuration, FeatureFlag, TimetableConfiguration


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


@admin.register(TimetableConfiguration)
class TimetableConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        'semester',
        'periods_per_day',
        'default_period_duration',
        'day_start_time',
        'day_end_time'
    ]
    list_filter = ['semester']
    search_fields = ['semester__academic_year__year_code']
    fieldsets = (
        ('Semester', {
            'fields': ('semester',)
        }),
        ('Period Settings', {
            'fields': (
                'periods_per_day',
                'default_period_duration',
                'day_start_time',
                'day_end_time'
            )
        }),
        ('Break Configuration', {
            'fields': (
                'lunch_break_after_period',
                'lunch_break_duration',
                'short_break_duration'
            )
        }),
        ('Working Days', {
            'fields': ('working_days',),
            'description': 'List of working day numbers: [1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun]'
        }),
    )
