"""
Admin interface for Assignment System
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from assignment.models import Assignment, AssignmentSubmission, AssignmentGrade
from assignment.utils import get_assignment_statistics


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    """Admin interface for Assignment"""
    
    list_display = [
        'id',
        'title',
        'subject_display',
        'section_display',
        'assignment_type',
        'status_badge',
        'due_date_display',
        'submission_stats',
        'created_by_display',
        'created_at',
    ]
    
    list_filter = [
        'status',
        'assignment_type',
        'subject',
        'section',
        'semester',
        'created_at',
        'due_date',
    ]
    
    search_fields = [
        'title',
        'description',
        'subject__name',
        'section__name',
        'created_by__email',
        'created_by__first_name',
        'created_by__last_name',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'published_date',
        'is_overdue',
        'can_submit',
        'total_submissions',
        'graded_submissions',
        'pending_submissions',
        'statistics_display',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'title',
                'description',
                'assignment_type',
                'status',
            )
        }),
        ('References', {
            'fields': (
                'subject',
                'section',
                'semester',
                'created_by',
            )
        }),
        ('Dates & Deadlines', {
            'fields': (
                'published_date',
                'due_date',
                'allow_late_submission',
                'late_submission_deadline',
            )
        }),
        ('Grading', {
            'fields': (
                'max_marks',
                'weightage',
            )
        }),
        ('Files', {
            'fields': (
                'attachment',
            )
        }),
        ('Status & Statistics', {
            'fields': (
                'is_overdue',
                'can_submit',
                'total_submissions',
                'graded_submissions',
                'pending_submissions',
                'statistics_display',
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def subject_display(self, obj):
        """Display subject name"""
        return obj.subject.name
    subject_display.short_description = 'Subject'
    
    def section_display(self, obj):
        """Display section name"""
        return obj.section.name
    section_display.short_description = 'Section'
    
    def created_by_display(self, obj):
        """Display creator name"""
        return obj.created_by.email or obj.created_by.register_number
    created_by_display.short_description = 'Created By'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'DRAFT': 'gray',
            'PUBLISHED': 'green',
            'CLOSED': 'orange',
            'GRADED': 'blue',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'
    
    def due_date_display(self, obj):
        """Display due date with overdue indicator"""
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">{} (OVERDUE)</span>',
                obj.due_date.strftime('%Y-%m-%d %H:%M')
            )
        return obj.due_date.strftime('%Y-%m-%d %H:%M')
    due_date_display.short_description = 'Due Date'
    
    def submission_stats(self, obj):
        """Display submission statistics"""
        return format_html(
            '{} / {} ({:.1f}%)',
            obj.total_submissions,
            obj.total_submissions + obj.pending_submissions,
            (obj.total_submissions / (obj.total_submissions + obj.pending_submissions) * 100) 
            if (obj.total_submissions + obj.pending_submissions) > 0 else 0
        )
    submission_stats.short_description = 'Submissions'
    
    def statistics_display(self, obj):
        """Display detailed statistics"""
        if not obj.pk:
            return "Save assignment first to see statistics"
        
        stats = get_assignment_statistics(obj)
        
        html = f"""
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background-color: #f0f0f0;">
                <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Metric</th>
                <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Value</th>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Total Students</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{stats['total_students']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Submissions</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{stats['total_submissions']} ({stats['submission_percentage']:.1f}%)</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Not Submitted</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{stats['not_submitted']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Graded</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{stats['graded_count']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Pending Grading</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{stats['pending_grading']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Late Submissions</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{stats['late_submissions']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Average Marks</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{stats['average_marks']} / {obj.max_marks} ({stats['average_percentage']:.1f}%)</td>
            </tr>
        </table>
        """
        
        return format_html(html)
    statistics_display.short_description = 'Statistics'
    
    actions = ['publish_assignments', 'close_assignments']
    
    def publish_assignments(self, request, queryset):
        """Bulk publish assignments"""
        count = 0
        for assignment in queryset.filter(status='DRAFT'):
            if assignment.due_date > timezone.now():
                assignment.status = 'PUBLISHED'
                assignment.published_date = timezone.now()
                assignment.save()
                count += 1
        
        self.message_user(request, f'{count} assignment(s) published successfully.')
    publish_assignments.short_description = 'Publish selected assignments'
    
    def close_assignments(self, request, queryset):
        """Bulk close assignments"""
        count = queryset.filter(status='PUBLISHED').update(status='CLOSED')
        self.message_user(request, f'{count} assignment(s) closed successfully.')
    close_assignments.short_description = 'Close selected assignments'


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    """Admin interface for AssignmentSubmission"""
    
    list_display = [
        'id',
        'assignment_display',
        'student_display',
        'status_badge',
        'submitted_at',
        'is_late_badge',
        'graded_display',
        'marks_display',
    ]
    
    list_filter = [
        'status',
        'is_late',
        'submitted_at',
        'assignment__subject',
        'assignment__section',
    ]
    
    search_fields = [
        'assignment__title',
        'student__user__email',
        'student__user__first_name',
        'student__user__last_name',
        'student__register_number',
        'submission_text',
    ]
    
    readonly_fields = [
        'submitted_at',
        'created_at',
        'updated_at',
        'is_late',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'assignment',
                'student',
                'status',
            )
        }),
        ('Submission', {
            'fields': (
                'submission_text',
                'attachment',
                'submitted_at',
                'is_late',
            )
        }),
        ('Grading', {
            'fields': (
                'graded_by',
                'graded_at',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def assignment_display(self, obj):
        """Display assignment title"""
        return obj.assignment.title
    assignment_display.short_description = 'Assignment'
    
    def student_display(self, obj):
        """Display student name"""
        return f"{obj.student.user.first_name} {obj.student.user.last_name} ({obj.student.register_number})"
    student_display.short_description = 'Student'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'SUBMITTED': 'blue',
            'GRADED': 'green',
            'RETURNED': 'orange',
            'RESUBMITTED': 'purple',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'
    
    def is_late_badge(self, obj):
        """Display late submission badge"""
        if obj.is_late:
            return format_html(
                '<span style="background-color: red; color: white; padding: 3px 10px; border-radius: 3px;">LATE</span>'
            )
        return format_html(
            '<span style="background-color: green; color: white; padding: 3px 10px; border-radius: 3px;">ON TIME</span>'
        )
    is_late_badge.short_description = 'Timeliness'
    
    def graded_display(self, obj):
        """Display if graded"""
        if obj.status == 'GRADED':
            return format_html('<span style="color: {};">✓</span>', 'green')
        return format_html('<span style="color: {};">✗</span>', 'gray')
    graded_display.short_description = 'Graded'
    
    def marks_display(self, obj):
        """Display marks if graded"""
        if hasattr(obj, 'grade'):
            return f"{obj.grade.marks_obtained} / {obj.assignment.max_marks} ({obj.grade.grade_letter})"
        return "-"
    marks_display.short_description = 'Marks'


@admin.register(AssignmentGrade)
class AssignmentGradeAdmin(admin.ModelAdmin):
    """Admin interface for AssignmentGrade"""
    
    list_display = [
        'id',
        'submission_display',
        'student_display',
        'marks_display',
        'percentage_display',
        'grade_letter_badge',
        'graded_by_display',
        'graded_at',
    ]
    
    list_filter = [
        'graded_at',
        'submission__assignment__subject',
        'submission__assignment__section',
    ]
    
    search_fields = [
        'submission__assignment__title',
        'submission__student__user__email',
        'submission__student__user__first_name',
        'submission__student__user__last_name',
        'feedback',
    ]
    
    readonly_fields = [
        'graded_at',
        'updated_at',
        'percentage',
        'grade_letter',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'submission',
                'graded_by',
            )
        }),
        ('Grading', {
            'fields': (
                'marks_obtained',
                'percentage',
                'grade_letter',
                'feedback',
                'grading_rubric',
            )
        }),
        ('Metadata', {
            'fields': (
                'graded_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def submission_display(self, obj):
        """Display submission info"""
        return f"{obj.submission.assignment.title}"
    submission_display.short_description = 'Assignment'
    
    def student_display(self, obj):
        """Display student name"""
        return f"{obj.submission.student.user.first_name} {obj.submission.student.user.last_name}"
    student_display.short_description = 'Student'
    
    def marks_display(self, obj):
        """Display marks"""
        return f"{obj.marks_obtained} / {obj.submission.assignment.max_marks}"
    marks_display.short_description = 'Marks'
    
    def percentage_display(self, obj):
        """Display percentage"""
        return f"{obj.percentage:.1f}%"
    percentage_display.short_description = 'Percentage'
    
    def grade_letter_badge(self, obj):
        """Display grade letter as badge"""
        colors = {
            'A+': '#2ecc71',
            'A': '#27ae60',
            'B+': '#3498db',
            'B': '#2980b9',
            'C': '#f39c12',
            'D': '#e67e22',
            'F': '#e74c3c',
        }
        color = colors.get(obj.grade_letter, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 15px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.grade_letter
        )
    grade_letter_badge.short_description = 'Grade'
    
    def graded_by_display(self, obj):
        """Display grader name"""
        return obj.graded_by.email or obj.graded_by.register_number
    graded_by_display.short_description = 'Graded By'
