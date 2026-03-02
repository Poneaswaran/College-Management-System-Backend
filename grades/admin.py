from django.contrib import admin
from .models import (
    CourseGrade, SemesterGPA, StudentCGPA,
    ExamConfig, CourseSectionAssignment, GradeBatch, GradeEntry
)


@admin.register(CourseGrade)
class CourseGradeAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'semester', 'grade', 'grade_points', 'percentage', 'is_published']
    list_filter = ['semester', 'grade', 'is_published', 'subject__department']
    search_fields = ['student__register_number', 'student__first_name', 'subject__code', 'subject__name']
    readonly_fields = ['total_marks', 'total_max_marks', 'percentage', 'grade', 'grade_points']
    
    fieldsets = (
        ('Student & Course', {
            'fields': ('student', 'subject', 'semester')
        }),
        ('Marks', {
            'fields': ('internal_marks', 'internal_max_marks', 'exam_marks', 'exam_max_marks', 'exam_type', 'exam_date')
        }),
        ('Calculated Fields', {
            'fields': ('total_marks', 'total_max_marks', 'percentage', 'grade', 'grade_points', 'credits')
        }),
        ('Additional Info', {
            'fields': ('remarks', 'is_published', 'graded_by')
        }),
    )


@admin.register(SemesterGPA)
class SemesterGPAAdmin(admin.ModelAdmin):
    list_display = ['student', 'semester', 'gpa', 'total_credits', 'credits_earned']
    list_filter = ['semester']
    search_fields = ['student__register_number', 'student__first_name']


@admin.register(StudentCGPA)
class StudentCGPAAdmin(admin.ModelAdmin):
    list_display = ['student', 'cgpa', 'total_credits', 'credits_earned', 'performance_trend']
    list_filter = ['performance_trend']
    search_fields = ['student__register_number', 'student__first_name']

# ==================================================
# FACULTY GRADE SUBMISSION ADMIN
# ==================================================

@admin.register(ExamConfig)
class ExamConfigAdmin(admin.ModelAdmin):
    list_display = ['exam_type', 'exam_date', 'internal_max_mark', 'external_max_mark', 'pass_mark', 'total_max_mark']
    list_filter = ['exam_type', 'exam_date']
    search_fields = ['exam_type']
    
    def total_max_mark(self, obj):
        return obj.total_max_mark
    total_max_mark.short_description = 'Total Max Marks'


@admin.register(CourseSectionAssignment)
class CourseSectionAssignmentAdmin(admin.ModelAdmin):
    list_display = ['faculty', 'subject', 'section', 'semester', 'is_active']
    list_filter = ['semester', 'is_active', 'subject__department']
    search_fields = ['faculty__first_name', 'faculty__last_name', 'subject__name', 'section__name']
    raw_id_fields = ['faculty', 'subject', 'section', 'semester', 'exam_config']


@admin.register(GradeBatch)
class GradeBatchAdmin(admin.ModelAdmin):
    list_display = ['course_section_assignment', 'status', 'submitted_at', 'approved_by', 'approved_at']
    list_filter = ['status', 'submitted_at']
    search_fields = ['course_section_assignment__subject__name', 'course_section_assignment__faculty__first_name']
    readonly_fields = ['submitted_at', 'updated_at', 'created_at']
    raw_id_fields = ['course_section_assignment', 'approved_by']
    
    fieldsets = (
        ('Course Section', {
            'fields': ('course_section_assignment',)
        }),
        ('Status', {
            'fields': ('status', 'submitted_at', 'rejection_reason')
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(GradeEntry)
class GradeEntryAdmin(admin.ModelAdmin):
    list_display = ['student', 'grade_batch', 'internal_mark', 'external_mark', 'total_mark', 'letter_grade', 'is_pass', 'is_absent']
    list_filter = ['letter_grade', 'is_pass', 'is_absent', 'grade_batch__status']
    search_fields = ['student__register_number', 'student__first_name', 'grade_batch__course_section_assignment__subject__name']
    readonly_fields = ['total_mark', 'percentage', 'letter_grade', 'grade_point', 'is_pass']
    raw_id_fields = ['grade_batch', 'student']
    
    fieldsets = (
        ('Student & Batch', {
            'fields': ('grade_batch', 'student')
        }),
        ('Marks', {
            'fields': ('internal_mark', 'external_mark', 'is_absent')
        }),
        ('Computed Fields', {
            'fields': ('total_mark', 'percentage', 'letter_grade', 'grade_point', 'is_pass')
        }),
    )