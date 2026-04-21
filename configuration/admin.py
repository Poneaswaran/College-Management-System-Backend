from django.contrib import admin
from django.contrib import messages

from configuration.models import Configuration, FeatureFlag, TimetableConfiguration


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ["tenant_key", "sub_app", "key", "is_active", "updated_at"]
    search_fields = ["tenant_key", "sub_app", "key", "description"]
    list_filter = ["sub_app", "is_active"]


from django.core.cache import cache
from configuration.models import FeatureFlag, TenantFeatureOverride
from configuration.services.feature_flag_service import KNOWN_FLAGS

class TenantFeatureOverrideInline(admin.TabularInline):
    model = TenantFeatureOverride
    extra = 1
    fields = ("schema_name", "is_enabled", "updated_at")
    readonly_fields = ("updated_at",)

@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "is_enabled_globally", "updated_at")
    list_editable = ("is_enabled_globally",)
    inlines = [TenantFeatureOverrideInline]
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Invalidate cache for all tenants when global flag changes
        from tenants.models import Client
        for tenant in Client.objects.exclude(schema_name="public"):
            cache.delete(f"ff:{tenant.schema_name}:{obj.key}")

@admin.register(TenantFeatureOverride)
class TenantFeatureOverrideAdmin(admin.ModelAdmin):
    list_display = ("schema_name", "flag", "is_enabled", "updated_at")
    list_filter = ("schema_name", "is_enabled")
    readonly_fields = ("updated_at",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete(f"ff:{obj.schema_name}:{obj.flag.key}")


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
    actions = ['generate_periods']
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

    # ── Item 7: Generate period definitions via admin action ───────────────

    @admin.action(description='📅 Generate PeriodDefinition rows for selected configs')
    def generate_periods(self, request, queryset):
        """
        Calls generate_periods_for_config() for each selected
        TimetableConfiguration and reports how many PeriodDefinition
        rows were created.
        """
        from timetable.utils import generate_periods_for_config

        total_created = 0
        summaries = []

        for config in queryset:
            try:
                created = generate_periods_for_config(config)
                count = len(created)
                total_created += count
                summaries.append(
                    f"Semester '{config.semester}': {count} period(s) created."
                )
            except Exception as exc:
                summaries.append(
                    f"Semester '{config.semester}': ERROR — {exc}"
                )

        level = messages.SUCCESS if total_created > 0 else messages.WARNING
        self.message_user(
            request,
            f"Total periods created: {total_created}. " + " | ".join(summaries),
            level,
        )
