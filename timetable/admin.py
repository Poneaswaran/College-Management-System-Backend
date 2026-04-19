"""
timetable/admin.py

Admin configuration for all timetable models.

New registrations:
    SectionSubjectRequirementAdmin — Item 2
    RoomMaintenanceBlockAdmin      — Item 4 (with trigger_reschedule action)

Updated:
    TimetableConfigurationAdmin in configuration/admin.py gets
    generate_periods action — Item 7 (see configuration/admin.py).
"""
from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages

from .models import (
    Subject,
    PeriodDefinition,
    Room,
    TimetableEntry,
    NonRoomPeriod,
    OverflowLog,
    LabRotationSchedule,
    SectionSubjectRequirement,
    RoomMaintenanceBlock,
    DepartmentSectionCombinePolicy,
    CombinedClassSession,
    CombinedClassSessionSection,
)


# ==================================================
# SUBJECT
# ==================================================

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
    search_fields = ['code', 'name', 'department__name']
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


# ==================================================
# PERIOD DEFINITION
# ==================================================

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
    search_fields = ['semester__academic_year__year_code', 'day_of_week', 'period_number']
    ordering = ['semester', 'day_of_week', 'period_number']
    fieldsets = (
        ('Semester & Day', {
            'fields': ('semester', 'day_of_week', 'period_number')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'duration_minutes')
        }),
    )


# ==================================================
# ROOM
# ==================================================

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


# ==================================================
# TIMETABLE ENTRY
# ==================================================

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
    autocomplete_fields = [
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


# ==================================================
# NON-ROOM PERIOD
# ==================================================

@admin.register(NonRoomPeriod)
class NonRoomPeriodAdmin(admin.ModelAdmin):
    list_display  = ['section', 'period_type_badge', 'period_definition', 'semester', 'notes']
    list_filter   = ['period_type', 'semester', 'period_definition__day_of_week']
    search_fields = ['section__name', 'section__code']
    ordering      = ['semester', 'section', 'period_definition__day_of_week']
    autocomplete_fields = ['section', 'period_definition']

    def period_type_badge(self, obj):
        colours = {
            'LAB':     '#2563eb',
            'PT':      '#16a34a',
            'LIBRARY': '#9333ea',
            'FREE':    '#d97706',
        }
        colour = colours.get(obj.period_type, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:0.8em">{}</span>',
            colour,
            obj.get_period_type_display(),
        )
    period_type_badge.short_description = 'Type'


# ==================================================
# OVERFLOW LOG
# ==================================================

@admin.register(OverflowLog)
class OverflowLogAdmin(admin.ModelAdmin):
    list_display   = [
        'section',
        'overflow_date',
        'period_definition',
        'reason',
        'compensated_badge',
        'section_overflow_total',
    ]
    list_filter    = ['semester', 'compensated', 'reason', 'overflow_date']
    search_fields  = ['section__name', 'section__code']
    readonly_fields= [
        'section', 'period_definition', 'semester',
        'overflow_date', 'reason', 'created_at'
    ]
    ordering       = ['-overflow_date', 'section']
    actions        = ['mark_compensated', 'mark_uncompensated']

    def compensated_badge(self, obj):
        if obj.compensated:
            return format_html(
                '<span style="color:#16a34a;font-weight:bold">✔ Compensated</span>'
            )
        return format_html(
            '<span style="color:#dc2626;font-weight:bold">✘ Pending</span>'
        )
    compensated_badge.short_description = 'Compensation'

    def section_overflow_total(self, obj):
        count = OverflowLog.objects.filter(
            section=obj.section,
            semester=obj.semester,
            compensated=False,
        ).count()
        colour = '#dc2626' if count >= 4 else '#d97706' if count >= 2 else '#16a34a'
        return format_html(
            '<b style="color:{}">{}</b>',
            colour, count
        )
    section_overflow_total.short_description = 'Uncompensated Total'

    @admin.action(description='✔ Mark selected as compensated')
    def mark_compensated(self, request, queryset):
        updated = queryset.update(compensated=True)
        self.message_user(
            request,
            f"{updated} overflow log(s) marked as compensated.",
            messages.SUCCESS,
        )

    @admin.action(description='✘ Revert to uncompensated')
    def mark_uncompensated(self, request, queryset):
        updated = queryset.update(compensated=False)
        self.message_user(
            request,
            f"{updated} overflow log(s) reverted to uncompensated.",
            messages.WARNING,
        )


# ==================================================
# LAB ROTATION SCHEDULE
# ==================================================

@admin.register(LabRotationSchedule)
class LabRotationScheduleAdmin(admin.ModelAdmin):
    list_display  = ['section_priority_display', 'section', 'lab', 'period_definition',
                     'semester', 'is_active']
    list_filter   = ['semester', 'lab', 'is_active', 'section__priority']
    search_fields = ['section__name', 'section__code', 'lab__room_number']
    ordering      = ['semester', 'section__priority', 'period_definition__day_of_week']
    autocomplete_fields = ['section', 'lab', 'period_definition']
    readonly_fields = ['created_at']
    actions = ['generate_rotation', 'deactivate_selected', 'activate_selected']

    def section_priority_display(self, obj):
        labels = {1: ('Final Year', '#dc2626'), 2: ('2nd Year', '#d97706'), 3: ('1st Year', '#2563eb')}
        label, colour = labels.get(obj.section.priority, ('Unknown', '#6b7280'))
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            colour, label,
        )
    section_priority_display.short_description = 'Year Group'

    @admin.action(description='🔄 Regenerate lab rotation for these semesters')
    def generate_rotation(self, request, queryset):
        from timetable.scheduler import LabRotationGenerator
        from django.core.exceptions import ValidationError

        semester_ids = queryset.values_list('semester_id', flat=True).distinct()
        results = []
        for sid in semester_ids:
            try:
                result = LabRotationGenerator.generate(sid)
                results.append(f"Semester {sid}: {result['created']} rotations created.")
            except ValidationError as e:
                results.append(f"Semester {sid}: ERROR — {e}")

        self.message_user(request, " | ".join(results), messages.SUCCESS)

    @admin.action(description='Deactivate selected rotations')
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} rotation(s) deactivated.", messages.WARNING)

    @admin.action(description='Activate selected rotations')
    def activate_selected(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} rotation(s) activated.", messages.SUCCESS)


# ==================================================
# SECTION SUBJECT REQUIREMENT  (Item 2)
# ==================================================

@admin.register(SectionSubjectRequirement)
class SectionSubjectRequirementAdmin(admin.ModelAdmin):
    list_display = [
        'section',
        'semester',
        'subject',
        'faculty',
        'periods_per_week',
    ]
    list_filter = [
        'semester',
        'section__course__department',
        'subject__subject_type',
    ]
    search_fields = [
        'section__name',
        'section__code',
        'subject__code',
        'subject__name',
        'faculty__email',
    ]
    autocomplete_fields = ['section', 'subject', 'faculty']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['section', 'semester', 'subject']
    fieldsets = (
        ('Assignment', {
            'fields': ('section', 'semester', 'subject', 'faculty')
        }),
        ('Schedule', {
            'fields': ('periods_per_week',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ==================================================
# ROOM MAINTENANCE BLOCK  (Item 4)
# ==================================================

@admin.register(RoomMaintenanceBlock)
class RoomMaintenanceBlockAdmin(admin.ModelAdmin):
    list_display = [
        'room',
        'start_date',
        'end_date',
        'reason',
        'is_active',
        'created_at',
    ]
    list_filter = [
        'is_active',
        'room__building',
        'start_date',
    ]
    search_fields = [
        'room__room_number',
        'room__building',
        'reason',
    ]
    autocomplete_fields = ['room']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-start_date']
    actions = ['trigger_reschedule']
    fieldsets = (
        ('Room & Dates', {
            'fields': ('room', 'start_date', 'end_date')
        }),
        ('Details', {
            'fields': ('reason', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.action(description='🔧 Trigger reschedule for selected maintenance blocks')
    def trigger_reschedule(self, request, queryset):
        """
        For each selected active maintenance block, call RescheduleService
        to nullify affected room assignments and reallocate.
        """
        from timetable.services import RescheduleService
        from django.core.exceptions import ValidationError

        results = []
        for block in queryset.filter(is_active=True):
            try:
                summary = RescheduleService.reschedule_affected_periods(
                    room_id=block.room_id,
                    start_date=block.start_date,
                    end_date=block.end_date,
                )
                results.append(
                    f"Room {block.room.room_number} "
                    f"({block.start_date}→{block.end_date}): "
                    f"{summary['entries_nullified']} entries nullified, "
                    f"{summary['new_overflow_count']} new overflows, "
                    f"{len(summary['violations'])} violations."
                )
            except Exception as e:
                results.append(
                    f"Room {block.room.room_number}: ERROR — {e}"
                )

        if results:
            self.message_user(request, " | ".join(results), messages.SUCCESS)
        else:
            self.message_user(
                request,
                "No active maintenance blocks selected.",
                messages.WARNING,
            )

# ==================================================
# COMBINED CLASS SESSION
# ==================================================

@admin.register(CombinedClassSession)
class CombinedClassSessionAdmin(admin.ModelAdmin):
    """Admin interface for CombinedClassSession (needed for AttendanceSession autocomplete)."""

    list_display = [
        "id",
        "semester",
        "period_definition",
        "subject",
        "faculty",
        "room",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "is_active",
        "semester",
        "subject",
        "period_definition__day_of_week",
    ]
    search_fields = [
        "subject__code",
        "subject__name",
        "room__room_number",
        "faculty__email",
        "faculty__first_name",
        "faculty__last_name",
        "notes",
    ]
    autocomplete_fields = [
        "semester",
        "period_definition",
        "subject",
        "faculty",
        "room",
        "created_by",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(CombinedClassSessionSection)
class CombinedClassSessionSectionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "combined_session",
        "section",
    ]
    search_fields = [
        "combined_session__subject__code",
        "combined_session__subject__name",
        "section__name",
        "section__code",
    ]
    autocomplete_fields = [
        "combined_session",
        "section",
    ]
