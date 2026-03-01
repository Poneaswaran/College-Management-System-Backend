"""
Admin configuration for Exam Management module.
"""
from django.contrib import admin
from .models import Exam, ExamSchedule, ExamSeatingArrangement, ExamResult, HallTicket


# ==================================================
# INLINES
# ==================================================

class ExamScheduleInline(admin.TabularInline):
    model = ExamSchedule
    extra = 0
    fields = ['subject', 'section', 'date', 'start_time', 'end_time', 'shift', 'room', 'invigilator']
    autocomplete_fields = ['subject', 'section', 'room', 'invigilator']


class ExamSeatingInline(admin.TabularInline):
    model = ExamSeatingArrangement
    extra = 0
    fields = ['student', 'room', 'seat_number', 'is_present']
    autocomplete_fields = ['student', 'room']


class ExamResultInline(admin.TabularInline):
    model = ExamResult
    extra = 0
    fields = ['student', 'marks_obtained', 'is_absent', 'status', 'percentage', 'is_pass']
    readonly_fields = ['percentage', 'is_pass']
    autocomplete_fields = ['student']


# ==================================================
# MODEL ADMINS
# ==================================================

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'exam_type', 'semester', 'department',
        'status', 'start_date', 'end_date', 'total_subjects'
    ]
    list_filter = ['exam_type', 'status', 'semester', 'department']
    search_fields = ['name']
    date_hierarchy = 'start_date'
    inlines = [ExamScheduleInline]
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Exam Details', {
            'fields': ('name', 'exam_type', 'semester', 'department')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'status')
        }),
        ('Configuration', {
            'fields': ('max_marks', 'pass_marks_percentage', 'instructions')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ExamSchedule)
class ExamScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'exam', 'subject', 'section', 'date', 'shift',
        'start_time', 'end_time', 'room', 'invigilator',
        'student_count', 'results_entered_count'
    ]
    list_filter = ['exam__exam_type', 'shift', 'date', 'exam']
    search_fields = ['subject__name', 'subject__code']
    date_hierarchy = 'date'
    autocomplete_fields = ['exam', 'subject', 'section', 'room', 'invigilator']
    inlines = [ExamSeatingInline, ExamResultInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ExamSeatingArrangement)
class ExamSeatingAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'schedule', 'room', 'seat_number', 'is_present'
    ]
    list_filter = ['is_present', 'schedule__exam', 'room']
    search_fields = ['student__register_number', 'seat_number']
    autocomplete_fields = ['student', 'schedule', 'room']


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'schedule', 'marks_obtained', 'percentage',
        'is_pass', 'is_absent', 'status'
    ]
    list_filter = ['status', 'is_pass', 'is_absent', 'schedule__exam']
    search_fields = ['student__register_number']
    autocomplete_fields = ['student', 'schedule', 'entered_by', 'verified_by']
    readonly_fields = ['percentage', 'is_pass', 'created_at', 'updated_at']

    fieldsets = (
        ('References', {
            'fields': ('schedule', 'student')
        }),
        ('Marks', {
            'fields': ('marks_obtained', 'is_absent', 'percentage', 'is_pass')
        }),
        ('Status', {
            'fields': ('status', 'remarks')
        }),
        ('Audit', {
            'fields': ('entered_by', 'verified_by', 'published_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(HallTicket)
class HallTicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'student', 'exam', 'status',
        'is_eligible', 'generated_at'
    ]
    list_filter = ['status', 'is_eligible', 'exam']
    search_fields = ['ticket_number', 'student__register_number']
    autocomplete_fields = ['student', 'exam']
    readonly_fields = ['generated_at', 'downloaded_at']
