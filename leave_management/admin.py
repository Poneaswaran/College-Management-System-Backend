from django.contrib import admin
from .models import LeaveType, WeekendSetting, HolidayCalendar, FacultyLeaveBalance, FacultyLeaveRequest, LeaveApprovalAction, LeavePolicy

@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'annual_quota', 'is_active']
    search_fields = ['name', 'code']

@admin.register(WeekendSetting)
class WeekendSettingAdmin(admin.ModelAdmin):
    list_display = ['department', 'day', 'is_weekend']
    list_filter = ['department', 'is_weekend']

@admin.register(HolidayCalendar)
class HolidayCalendarAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'is_restricted']
    list_filter = ['is_restricted']
    search_fields = ['name']

@admin.register(FacultyLeaveBalance)
class FacultyLeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ['faculty', 'leave_type', 'total_granted', 'used', 'pending', 'year']
    list_filter = ['leave_type', 'year']
    search_fields = ['faculty__user__email', 'faculty__first_name', 'faculty__last_name']

@admin.register(FacultyLeaveRequest)
class FacultyLeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['faculty', 'leave_type', 'start_date', 'end_date', 'status', 'created_at']
    list_filter = ['status', 'leave_type']
    search_fields = ['faculty__user__email', 'reason']

@admin.register(LeaveApprovalAction)
class LeaveApprovalActionAdmin(admin.ModelAdmin):
    list_display = ['request', 'action_by', 'previous_status', 'new_status', 'timestamp']
    list_filter = ['new_status']

@admin.register(LeavePolicy)
class LeavePolicyAdmin(admin.ModelAdmin):
    list_display  = ['scope', 'tenant', 'school', 'department', 'leave_type',
                     'annual_quota', 'carry_forward', 'effective_from', 'is_active']
    list_filter   = ['scope', 'is_active', 'leave_type', 'school']
    search_fields = ['tenant__name', 'school__name', 'department__name', 'leave_type__code']
    ordering      = ['scope', 'leave_type']
