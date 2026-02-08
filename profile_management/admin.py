from django.contrib import admin
from .models import StudentProfile, ParentProfile
from .models import ParentLoginOTP


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['register_number', 'full_name', 'department', 'course', 'year', 'semester', 'academic_status', 'is_active']
    list_filter = ['department', 'course', 'year', 'semester', 'academic_status', 'gender']
    search_fields = ['register_number', 'first_name', 'last_name', 'phone', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'first_name', 'last_name', 'phone', 'date_of_birth', 'gender', 'address', 'profile_photo')
        }),
        ('Academic Information', {
            'fields': ('register_number', 'roll_number', 'department', 'course', 'section', 'year', 'semester', 'admission_date', 'academic_status')
        }),
        ('Guardian Information', {
            'fields': ('guardian_name', 'guardian_relationship', 'guardian_phone', 'guardian_email')
        }),
        ('Identification', {
            'fields': ('aadhar_number', 'id_proof_type', 'id_proof_number')
        }),
        ('System Information', {
            'fields': ('is_active', 'profile_completed', 'created_at', 'updated_at')
        }),
    )


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'student', 'relationship', 'phone_number']
    list_filter = ['relationship']
    search_fields = ['user__email', 'student__register_number', 'phone_number']


@admin.register(ParentLoginOTP)
class ParentLoginOTPAdmin(admin.ModelAdmin):
    list_display = ['student', 'code', 'contact', 'created_at', 'expires_at', 'used', 'attempts']
    list_filter = ['used']
    search_fields = ['student__register_number', 'code', 'contact']
