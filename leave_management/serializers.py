from rest_framework import serializers
from .models import LeaveType, WeekendSetting, HolidayCalendar, FacultyLeaveBalance, FacultyLeaveRequest, LeaveApprovalAction, LeavePolicy
from core.models import User
from profile_management.models import FacultyProfile

class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = '__all__'

class WeekendSettingSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(source='get_day_display', read_only=True)
    class Meta:
        model = WeekendSetting
        fields = '__all__'

class HolidayCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidayCalendar
        fields = '__all__'

class FacultyLeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    leave_type_code = serializers.CharField(source='leave_type.code', read_only=True)
    remaining = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    
    class Meta:
        model = FacultyLeaveBalance
        fields = '__all__'

class LeaveApprovalActionSerializer(serializers.ModelSerializer):
    action_by_name = serializers.CharField(source='action_by.get_full_name', read_only=True)
    class Meta:
        model = LeaveApprovalAction
        fields = '__all__'

class FacultyLeaveRequestSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    actions = LeaveApprovalActionSerializer(many=True, read_only=True)
    total_days = serializers.SerializerMethodField()

    class Meta:
        model = FacultyLeaveRequest
        fields = '__all__'
        read_only_fields = ['faculty', 'status', 'approved_by', 'hod_remarks']

    def get_total_days(self, obj) -> float:
        from .services import LeaveService
        return LeaveService.calculate_leave_days(obj.faculty, obj.start_date, obj.end_date, obj.duration_type)

class LeaveApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacultyLeaveRequest
        fields = [
            'leave_type', 'start_date', 'end_date', 'duration_type', 
            'reason', 'attachment', 'substitution_note', 'is_emergency'
        ]

class LeavePolicySerializer(serializers.ModelSerializer):
    leave_type_detail  = LeaveTypeSerializer(source='leave_type', read_only=True)
    scope_display      = serializers.CharField(source='get_scope_display', read_only=True)
    tenant_name        = serializers.CharField(source='tenant.name', read_only=True)
    school_name        = serializers.CharField(source='school.name', read_only=True)
    department_name    = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model  = LeavePolicy
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def validate(self, data):
        # Run model-level clean()
        # Create a temporary instance to run clean()
        instance = LeavePolicy(**data)
        try:
            instance.clean()
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return data


class ResolvedPolicySerializer(serializers.Serializer):
    """Read-only serializer for the resolved effective policy of a faculty member."""
    annual_quota         = serializers.DecimalField(max_digits=5, decimal_places=2)
    carry_forward        = serializers.BooleanField()
    max_carry_forward    = serializers.DecimalField(max_digits=5, decimal_places=2)
    allows_half_day      = serializers.BooleanField()
    requires_attachment  = serializers.BooleanField()
    min_notice_days      = serializers.IntegerField()
    max_consecutive_days = serializers.IntegerField(allow_null=True)
    source_scope         = serializers.CharField()
