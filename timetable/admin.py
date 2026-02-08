from django.contrib import admin
from .models import (
    TimetableConfiguration,
    Subject,
    PeriodDefinition,
    Room,
    TimetableEntry
)


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


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'name',
        'department',
        'semester_number',
        'credits',
        'subject_type',
        'is_active'
    ]
    list_filter = [
        'department',
        'semester_number',
        'subject_type',
        'is_active'
    ]
    search_fields = ['code', 'name']
    ordering = ['department', 'semester_number', 'code']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'department')
        }),
        ('Academic Details', {
            'fields': ('semester_number', 'credits', 'subject_type')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PeriodDefinition)
class PeriodDefinitionAdmin(admin.ModelAdmin):
    list_display = [
        'semester',
        'day_of_week',
        'period_number',
        'start_time',
        'end_time',
        'duration_minutes'
    ]
    list_filter = ['semester', 'day_of_week']
    search_fields = ['semester__academic_year__year_code']
    ordering = ['semester', 'day_of_week', 'period_number']
    fieldsets = (
        ('Semester & Day', {
            'fields': ('semester', 'day_of_week', 'period_number')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'duration_minutes')
        }),
    )


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = [
        'room_number',
        'building',
        'room_type',
        'capacity',
        'department',
        'is_active'
    ]
    list_filter = [
        'room_type',
        'department',
        'is_active',
        'building'
    ]
    search_fields = ['room_number', 'building']
    ordering = ['building', 'room_number']
    fieldsets = (
        ('Room Identification', {
            'fields': ('room_number', 'building', 'room_type')
        }),
        ('Capacity & Assignment', {
            'fields': ('capacity', 'department')
        }),
        ('Facilities', {
            'fields': ('facilities',),
            'description': 'JSON format: {"projector": true, "ac": true, "whiteboard": true}'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = [
        'section',
        'subject',
        'faculty',
        'period_definition',
        'room',
        'semester',
        'is_active'
    ]
    list_filter = [
        'semester',
        'section__course__department',
        'is_active',
        'period_definition__day_of_week'
    ]
    search_fields = [
        'section__name',
        'subject__code',
        'subject__name',
        'faculty__email',
        'faculty__register_number'
    ]
    raw_id_fields = [
        'section',
        'subject',
        'faculty',
        'room',
        'period_definition'
    ]
    readonly_fields = ['created_at', 'updated_at']
    ordering = [
        'semester',
        'section',
        'period_definition__day_of_week',
        'period_definition__period_number'
    ]
    fieldsets = (
        ('Class Details', {
            'fields': ('section', 'subject', 'faculty')
        }),
        ('Schedule', {
            'fields': ('period_definition', 'room', 'semester')
        }),
        ('Additional Information', {
            'fields': ('notes', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'section',
            'section__course',
            'section__course__department',
            'subject',
            'subject__department',
            'faculty',
            'faculty__role',
            'room',
            'period_definition',
            'semester',
            'semester__academic_year'
        )
