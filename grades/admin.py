from django.contrib import admin
from .models import CourseGrade, SemesterGPA, StudentCGPA


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
