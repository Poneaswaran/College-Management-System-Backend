"""
Admin interface for Attendance System
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.utils import timezone
from datetime import date
from django.shortcuts import render
from django.db.models import Count, Q
from attendance.models import AttendanceSession, StudentAttendance, AttendanceReport
from attendance.utils import auto_mark_absent_students


class TodaySessionFilter(admin.SimpleListFilter):
    """Filter for today's sessions"""
    title = 'Today Sessions'
    parameter_name = 'today'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Today Only'),
            ('upcoming', 'Upcoming'),
            ('past', 'Past'),
        )
    
    def queryset(self, request, queryset):
        today = date.today()
        if self.value() == 'yes':
            return queryset.filter(date=today)
        if self.value() == 'upcoming':
            return queryset.filter(date__gte=today)
        if self.value() == 'past':
            return queryset.filter(date__lt=today)


class ActiveSessionFilter(admin.SimpleListFilter):
    """Filter for active sessions"""
    title = 'Active Status'
    parameter_name = 'is_active'
    
    def lookups(self, request, model_admin):
        return (
            ('active', 'Currently Active'),
            ('can_mark', 'Can Mark Attendance'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(status='ACTIVE')
        if self.value() == 'can_mark':
            return queryset.filter(status='ACTIVE', 
                                   opened_at__isnull=False)


class StudentAttendanceInline(admin.TabularInline):
    """Inline display of student attendances in session admin"""
    model = StudentAttendance
    extra = 0
    can_delete = False
    
    fields = ['student', 'status', 'marked_at', 'is_manually_marked']
    readonly_fields = ['marked_at']
    autocomplete_fields = ['student']
    
    def get_queryset(self, request):
        """Optimize inline queries"""
        return super().get_queryset(request).select_related('student', 'marked_by')


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    """Admin interface for AttendanceSession"""
    
    change_list_template = 'admin/attendance/attendancesession_changelist.html'
    
    list_display = [
        'id',
        'get_subject',
        'get_section',
        'get_faculty',
        'date',
        'status_badge',
        'present_count',
        'total_students',
        'attendance_percentage_display',
        'time_remaining_display',
        'opened_at',
    ]
    
    list_filter = [
        'status',
        TodaySessionFilter,
        ActiveSessionFilter,
        'date',
        'timetable_entry__subject',
        'timetable_entry__section',
        'timetable_entry__semester',
        'timetable_entry__faculty',
    ]
    
    search_fields = [
        'timetable_entry__subject__name',
        'timetable_entry__section__name',
        'timetable_entry__faculty__user__first_name',
        'timetable_entry__faculty__user__last_name',
        'cancellation_reason',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'is_active',
        'can_mark_attendance',
        'time_remaining',
        'total_students',
        'present_count',
        'attendance_percentage',
    ]
    
    autocomplete_fields = [
        'timetable_entry',
        'opened_by',
        'blocked_by',
    ]
    
    inlines = [StudentAttendanceInline]
    
    fieldsets = (
        ('Session Information', {
            'fields': (
                'timetable_entry',
                'date',
                'status',
                'attendance_window_minutes',
            )
        }),
        ('Session Control', {
            'fields': (
                'opened_by',
                'opened_at',
                'closed_at',
            )
        }),
        ('Blocking/Cancellation', {
            'fields': (
                'cancellation_reason',
                'blocked_by',
                'blocked_at',
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': (
                'notes',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'date'
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related(
            'timetable_entry__subject',
            'timetable_entry__section',
            'timetable_entry__faculty',
            'timetable_entry__semester',
            'opened_by',
            'blocked_by'
        )
    
    def get_subject(self, obj):
        """Get subject name"""
        return obj.timetable_entry.subject.name
    get_subject.short_description = 'Subject'
    get_subject.admin_order_field = 'timetable_entry__subject__name'
    
    def get_section(self, obj):
        """Get section name"""
        return obj.timetable_entry.section.name
    get_section.short_description = 'Section'
    get_section.admin_order_field = 'timetable_entry__section__name'
    
    def get_faculty(self, obj):
        """Get faculty name"""
        return obj.timetable_entry.faculty.email or obj.timetable_entry.faculty.register_number
    get_faculty.short_description = 'Faculty'
    get_faculty.admin_order_field = 'timetable_entry__faculty__email'
    
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'SCHEDULED': 'gray',
            'ACTIVE': 'green',
            'CLOSED': 'blue',
            'BLOCKED': 'red',
            'CANCELLED': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def attendance_percentage_display(self, obj):
        """Display attendance percentage"""
        percentage = obj.attendance_percentage
        color = 'green' if percentage >= 75 else 'orange' if percentage >= 50 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            f'{percentage:.2f}'
        )
    attendance_percentage_display.short_description = 'Attendance %'
    
    def time_remaining_display(self, obj):
        """Display time remaining"""
        if obj.status == 'ACTIVE' and obj.can_mark_attendance:
            minutes = obj.time_remaining
            return format_html(
                '<span style="color: green; font-weight: bold;">{} min</span>',
                minutes
            )
        return '-'
    time_remaining_display.short_description = 'Time Left'
    
    actions = ['close_sessions', 'block_sessions', 'open_sessions', 'reopen_blocked_sessions']
    
    def open_sessions(self, request, queryset):
        """Open selected scheduled sessions"""
        opened = 0
        for session in queryset.filter(status='SCHEDULED'):
            session.status = 'ACTIVE'
            session.opened_by = request.user
            session.opened_at = timezone.now()
            session.save()
            opened += 1
        
        self.message_user(request, f'Opened {opened} session(s)')
    open_sessions.short_description = 'Open selected sessions'
    
    def reopen_blocked_sessions(self, request, queryset):
        """Reopen blocked/cancelled sessions"""
        reopened = 0
        for session in queryset.filter(status__in=['BLOCKED', 'CANCELLED']):
            session.status = 'SCHEDULED'
            session.cancellation_reason = ''
            session.blocked_by = None
            session.blocked_at = None
            session.save()
            reopened += 1
        
        self.message_user(request, f'Reopened {reopened} session(s)')
    reopen_blocked_sessions.short_description = 'Reopen blocked sessions'
    
    def close_sessions(self, request, queryset):
        """Close selected active sessions"""
        closed = 0
        for session in queryset.filter(status='ACTIVE'):
            session.status = 'CLOSED'
            session.closed_at = timezone.now()
            session.save()
            # Auto-mark absent students
            auto_mark_absent_students(session)
            closed += 1
        
        self.message_user(request, f'Closed {closed} session(s) and marked absent students')
    close_sessions.short_description = 'Close selected sessions'
    
    def block_sessions(self, request, queryset):
        """Block selected sessions"""
        blocked = 0
        for session in queryset:
            if session.status not in ['BLOCKED', 'CANCELLED']:
                session.status = 'BLOCKED'
                session.blocked_by = request.user
                session.blocked_at = timezone.now()
                if not session.cancellation_reason:
                    session.cancellation_reason = 'Blocked by admin'
                session.save()
                blocked += 1
        
        self.message_user(request, f'Blocked {blocked} session(s)')
    block_sessions.short_description = 'Block selected sessions'
    
    def get_urls(self):
        """Add custom URLs for faculty sessions view"""
        urls = super().get_urls()
        custom_urls = [
            path('faculty-sessions/', 
                 self.admin_site.admin_view(self.faculty_sessions_view),
                 name='attendance_faculty_sessions'),
        ]
        return custom_urls + urls
    
    def faculty_sessions_view(self, request):
        """Custom view for faculty sessions dashboard"""
        today = date.today()
        selected_date = request.GET.get('date', str(today))
        
        try:
            selected_date = date.fromisoformat(selected_date)
        except ValueError:
            selected_date = today
        
        # Get all sessions for the selected date
        sessions = AttendanceSession.objects.filter(
            date=selected_date
        ).select_related(
            'timetable_entry__subject',
            'timetable_entry__section',
            'timetable_entry__faculty',
            'timetable_entry__period_definition',
            'opened_by',
            'blocked_by'
        ).order_by(
            'timetable_entry__faculty__email',
            'timetable_entry__period_definition__start_time'
        )
        
        # Group sessions by faculty
        from itertools import groupby
        sessions_by_faculty = {}
        for faculty_email, group in groupby(sessions, key=lambda s: s.timetable_entry.faculty):
            session_list = list(group)
            faculty_stats = {
                'faculty': faculty_email,
                'sessions': session_list,
                'total': len(session_list),
                'active': sum(1 for s in session_list if s.status == 'ACTIVE'),
                'closed': sum(1 for s in session_list if s.status == 'CLOSED'),
                'scheduled': sum(1 for s in session_list if s.status == 'SCHEDULED'),
                'blocked': sum(1 for s in session_list if s.status in ['BLOCKED', 'CANCELLED']),
            }
            sessions_by_faculty[faculty_email.email or faculty_email.register_number] = faculty_stats
        
        context = {
            **self.admin_site.each_context(request),
            'title': f'Faculty Sessions - {selected_date.strftime("%B %d, %Y")}',
            'selected_date': selected_date,
            'today': today,
            'sessions_by_faculty': sessions_by_faculty,
            'total_sessions': sessions.count(),
            'total_faculty': len(sessions_by_faculty),
        }
        
        return render(request, 'admin/attendance/faculty_sessions.html', context)


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    """Admin interface for StudentAttendance"""
    
    list_display = [
        'id',
        'get_student_name',
        'get_register_number',
        'get_subject',
        'get_date',
        'status_badge',
        'marked_at',
        'has_image',
        'is_manually_marked',
        'get_location',
    ]
    
    list_filter = [
        'status',
        'is_manually_marked',
        'session__date',
        'session__timetable_entry__subject',
        'session__timetable_entry__section',
    ]
    
    search_fields = [
        'student__first_name',
        'student__last_name',
        'student__register_number',
        'session__timetable_entry__subject__name',
        'notes',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'marked_at',
        'attendance_image_preview',
    ]
    
    autocomplete_fields = [
        'session',
        'student',
        'marked_by',
    ]
    
    fieldsets = (
        ('Attendance Information', {
            'fields': (
                'session',
                'student',
                'status',
            )
        }),
        ('Capture Details', {
            'fields': (
                'attendance_image',
                'attendance_image_preview',
                'marked_at',
                'latitude',
                'longitude',
                'device_info',
            )
        }),
        ('Manual Marking', {
            'fields': (
                'is_manually_marked',
                'marked_by',
            )
        }),
        ('Additional Information', {
            'fields': (
                'notes',
                'created_at',
                'updated_at',
            )
        }),
    )
    
    date_hierarchy = 'session__date'
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related(
            'session__timetable_entry__subject',
            'session__timetable_entry__section',
            'student',
            'marked_by'
        )
    
    def get_student_name(self, obj):
        """Get student full name"""
        return obj.student.full_name
    get_student_name.short_description = 'Student'
    get_student_name.admin_order_field = 'student__first_name'
    
    def get_register_number(self, obj):
        """Get student register number"""
        return obj.student.register_number
    get_register_number.short_description = 'Register No.'
    get_register_number.admin_order_field = 'student__register_number'
    
    def get_subject(self, obj):
        """Get subject name"""
        return obj.session.timetable_entry.subject.name
    get_subject.short_description = 'Subject'
    get_subject.admin_order_field = 'session__timetable_entry__subject__name'
    
    def get_date(self, obj):
        """Get session date"""
        return obj.session.date
    get_date.short_description = 'Date'
    get_date.admin_order_field = 'session__date'
    
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'PRESENT': 'green',
            'ABSENT': 'red',
            'LATE': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def has_image(self, obj):
        """Check if attendance image exists"""
        if obj.attendance_image:
            return format_html('<span style="color: {};">✓ Yes</span>', 'green')
        return format_html('<span style="color: {};">✗ No</span>', 'red')
    has_image.short_description = 'Image'
    
    def get_location(self, obj):
        """Get location coordinates"""
        if obj.latitude and obj.longitude:
            return f"{obj.latitude}, {obj.longitude}"
        return '-'
    get_location.short_description = 'Location'
    
    def attendance_image_preview(self, obj):
        """Display attendance image preview"""
        if obj.attendance_image:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;" />',
                obj.attendance_image.url
            )
        return 'No image'
    attendance_image_preview.short_description = 'Image Preview'


@admin.register(AttendanceReport)
class AttendanceReportAdmin(admin.ModelAdmin):
    """Admin interface for AttendanceReport"""
    
    list_display = [
        'id',
        'get_student_name',
        'get_register_number',
        'get_subject',
        'get_semester',
        'total_classes',
        'present_count',
        'absent_count',
        'late_count',
        'percentage_display',
        'threshold_badge',
        'last_calculated',
    ]
    
    list_filter = [
        'is_below_threshold',
        'semester',
        'subject',
        'student__section',
    ]
    
    search_fields = [
        'student__first_name',
        'student__last_name',
        'student__register_number',
        'subject__name',
    ]
    
    readonly_fields = [
        'total_classes',
        'present_count',
        'absent_count',
        'late_count',
        'attendance_percentage',
        'is_below_threshold',
        'last_calculated',
        'created_at',
    ]
    
    autocomplete_fields = [
        'student',
        'subject',
        'semester',
    ]
    
    fieldsets = (
        ('Report Information', {
            'fields': (
                'student',
                'subject',
                'semester',
            )
        }),
        ('Attendance Statistics', {
            'fields': (
                'total_classes',
                'present_count',
                'absent_count',
                'late_count',
                'attendance_percentage',
                'is_below_threshold',
            )
        }),
        ('Metadata', {
            'fields': (
                'last_calculated',
                'created_at',
            )
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related(
            'student',
            'subject',
            'semester'
        )
    
    def get_student_name(self, obj):
        """Get student full name"""
        return obj.student.full_name
    get_student_name.short_description = 'Student'
    get_student_name.admin_order_field = 'student__first_name'
    
    def get_register_number(self, obj):
        """Get student register number"""
        return obj.student.register_number
    get_register_number.short_description = 'Register No.'
    get_register_number.admin_order_field = 'student__register_number'
    
    def get_subject(self, obj):
        """Get subject name"""
        return obj.subject.name
    get_subject.short_description = 'Subject'
    get_subject.admin_order_field = 'subject__name'
    
    def get_semester(self, obj):
        """Get semester info"""
        return f"{obj.semester.academic_year.year_code} - Sem {obj.semester.number}"
    get_semester.short_description = 'Semester'
    
    def percentage_display(self, obj):
        """Display attendance percentage with color"""
        percentage = float(obj.attendance_percentage)
        color = 'green' if percentage >= 75 else 'orange' if percentage >= 50 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 14px;">{}%</span>',
            color,
            f'{percentage:.2f}'
        )
    percentage_display.short_description = 'Attendance %'
    percentage_display.admin_order_field = 'attendance_percentage'
    
    def threshold_badge(self, obj):
        """Display threshold status"""
        if obj.is_below_threshold:
            return format_html(
                '<span style="background-color: red; color: white; padding: 3px 10px; border-radius: 3px;">⚠ Below 75%</span>'
            )
        return format_html(
            '<span style="background-color: green; color: white; padding: 3px 10px; border-radius: 3px;">✓ Above 75%</span>'
        )
    threshold_badge.short_description = 'Threshold'
    threshold_badge.admin_order_field = 'is_below_threshold'
    
    actions = ['recalculate_reports']
    
    def recalculate_reports(self, request, queryset):
        """Recalculate selected attendance reports"""
        count = 0
        for report in queryset:
            report.calculate()
            count += 1
        
        self.message_user(request, f'Recalculated {count} report(s)')
    recalculate_reports.short_description = 'Recalculate selected reports'
