"""
Admin interface for Study Materials System
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from study_materials.models import StudyMaterial, StudyMaterialDownload, StudyMaterialView


@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    """Admin interface for Study Material"""
    
    list_display = [
        'id',
        'title',
        'subject_display',
        'section_display',
        'faculty_display',
        'material_type',
        'status_badge',
        'file_size_display',
        'downloads_display',
        'views_display',
        'uploaded_at',
    ]
    
    list_filter = [
        'status',
        'material_type',
        'uploaded_at',
        'subject',
        'section',
    ]
    
    search_fields = [
        'title',
        'description',
        'subject__name',
        'subject__code',
        'section__name',
        'faculty__first_name',
        'faculty__last_name',
    ]
    
    readonly_fields = [
        'uploaded_at',
        'updated_at',
        'published_at',
        'file_size',
        'view_count',
        'download_count',
    ]
    
    fieldsets = [
        ('Basic Information', {
            'fields': ('title', 'description', 'material_type', 'status')
        }),
        ('Assignment', {
            'fields': ('subject', 'section', 'faculty')
        }),
        ('File', {
            'fields': ('file', 'file_size')
        }),
        ('Statistics', {
            'fields': ('view_count', 'download_count')
        }),
        ('Timestamps', {
            'fields': ('uploaded_at', 'updated_at', 'published_at')
        }),
    ]
    
    def subject_display(self, obj):
        """Display subject with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:timetable_subject_change', args=[obj.subject.id]),
            f"{obj.subject.code} - {obj.subject.name}"
        )
    subject_display.short_description = 'Subject'
    
    def section_display(self, obj):
        """Display section with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:core_section_change', args=[obj.section.id]),
            obj.section.name
        )
    section_display.short_description = 'Section'
    
    def faculty_display(self, obj):
        """Display faculty with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:core_user_change', args=[obj.faculty.id]),
            obj.faculty.get_full_name()
        )
    faculty_display.short_description = 'Faculty'
    
    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            'DRAFT': 'gray',
            'PUBLISHED': 'green',
            'ARCHIVED': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        return f"{obj.file_size_mb} MB"
    file_size_display.short_description = 'File Size'
    
    def downloads_display(self, obj):
        """Display download count with link to downloads"""
        return format_html(
            '<a href="{}?study_material__id__exact={}">{}</a>',
            reverse('admin:study_materials_studymaterialdownload_changelist'),
            obj.id,
            obj.download_count
        )
    downloads_display.short_description = 'Downloads'
    
    def views_display(self, obj):
        """Display view count with link to views"""
        return format_html(
            '<a href="{}?study_material__id__exact={}">{}</a>',
            reverse('admin:study_materials_studymaterialview_changelist'),
            obj.id,
            obj.view_count
        )
    views_display.short_description = 'Views'


@admin.register(StudyMaterialDownload)
class StudyMaterialDownloadAdmin(admin.ModelAdmin):
    """Admin interface for Study Material Downloads"""
    
    list_display = [
        'id',
        'material_display',
        'student_display',
        'downloaded_at',
        'ip_address',
    ]
    
    list_filter = [
        'downloaded_at',
        'study_material__subject',
        'study_material__section',
    ]
    
    search_fields = [
        'study_material__title',
        'student__first_name',
        'student__last_name',
        'student__email',
    ]
    
    readonly_fields = [
        'study_material',
        'student',
        'downloaded_at',
        'ip_address',
    ]
    
    def material_display(self, obj):
        """Display material with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:study_materials_studymaterial_change', args=[obj.study_material.id]),
            obj.study_material.title
        )
    material_display.short_description = 'Material'
    
    def student_display(self, obj):
        """Display student with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:core_user_change', args=[obj.student.id]),
            obj.student.get_full_name()
        )
    student_display.short_description = 'Student'
    
    def has_add_permission(self, request):
        """Prevent manual addition - downloads are recorded via API"""
        return False


@admin.register(StudyMaterialView)
class StudyMaterialViewAdmin(admin.ModelAdmin):
    """Admin interface for Study Material Views"""
    
    list_display = [
        'id',
        'material_display',
        'student_display',
        'viewed_at',
    ]
    
    list_filter = [
        'viewed_at',
        'study_material__subject',
        'study_material__section',
    ]
    
    search_fields = [
        'study_material__title',
        'student__first_name',
        'student__last_name',
        'student__email',
    ]
    
    readonly_fields = [
        'study_material',
        'student',
        'viewed_at',
    ]
    
    def material_display(self, obj):
        """Display material with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:study_materials_studymaterial_change', args=[obj.study_material.id]),
            obj.study_material.title
        )
    material_display.short_description = 'Material'
    
    def student_display(self, obj):
        """Display student with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:core_user_change', args=[obj.student.id]),
            obj.student.get_full_name()
        )
    student_display.short_description = 'Student'
    
    def has_add_permission(self, request):
        """Prevent manual addition - views are recorded via API"""
        return False
