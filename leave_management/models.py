from django.db import models
from django.conf import settings
from core.models import Department, User
from profile_management.models import FacultyProfile


def _build_check_constraint(*, expression, name):
    """Robustly create CheckConstraint supporting both 'check' and 'condition' arguments."""
    try:
        from django.db import models as db_models
        return db_models.CheckConstraint(check=expression, name=name)
    except TypeError:
        from django.db import models as db_models
        return db_models.CheckConstraint(condition=expression, name=name)


class LeaveType(models.Model):
    """
    Configurable leave types (e.g., Casual Leave, Sick Leave)
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True) # e.g. CL, SL, EL
    description = models.TextField(blank=True)
    is_paid = models.BooleanField(default=True)
    allows_half_day = models.BooleanField(default=True)
    allows_full_day = models.BooleanField(default=True)
    max_days_per_request = models.PositiveIntegerField(null=True, blank=True)
    annual_quota = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    requires_attachment = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class WeekendSetting(models.Model):
    """
    Configurable weekend settings per institution/department
    """
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='weekend_settings', null=True, blank=True)
    day = models.IntegerField(choices=DAY_CHOICES)
    is_weekend = models.BooleanField(default=True)

    class Meta:
        unique_together = ('department', 'day')

    def __str__(self):
        dept = self.department.code if self.department else "Global"
        return f"{dept} - {self.get_day_display()}"

class HolidayCalendar(models.Model):
    """
    Public holidays
    """
    name = models.CharField(max_length=200)
    date = models.DateField()
    description = models.TextField(blank=True)
    is_restricted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.date})"

class FacultyLeaveBalance(models.Model):
    """
    Tracks leave balance for a faculty per leave type
    """
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    total_granted = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    used = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    pending = models.DecimalField(max_digits=5, decimal_places=2, default=0.0) # Requested but not yet approved
    year = models.PositiveIntegerField(default=2024) # Added for annual tracking
    
    @property
    def remaining(self):
        return self.total_granted - self.used - self.pending

    class Meta:
        unique_together = ('faculty', 'leave_type')

    def __str__(self):
        return f"{self.faculty.full_name} - {self.leave_type.name} (Bal: {self.remaining})"

class FacultyLeaveRequest(models.Model):
    """
    Leave application request
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('WITHDRAWN', 'Withdrawn'),
    ]

    DURATION_CHOICES = [
        ('FULL', 'Full Day'),
        ('HALF_MORNING', 'Half Day (Morning)'),
        ('HALF_AFTERNOON', 'Half Day (Afternoon)'),
    ]

    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    duration_type = models.CharField(max_length=20, choices=DURATION_CHOICES, default='FULL')
    reason = models.TextField()
    attachment = models.FileField(upload_to='leave_attachments/', null=True, blank=True)
    substitution_note = models.TextField(blank=True, help_text="Note about class handover")
    is_emergency = models.BooleanField(default=False)
    ai_summary = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUBMITTED')
    hod_remarks = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.faculty.full_name} - {self.leave_type.name} ({self.start_date})"

    class Meta:
        constraints = [
            _build_check_constraint(
                expression=models.Q(start_date__lte=models.F('end_date')),
                name='leave_management_valid_date_range'
            )
        ]

class LeaveApprovalAction(models.Model):
    """
    Audit trail for leave approvals
    """
    request = models.ForeignKey(FacultyLeaveRequest, on_delete=models.CASCADE, related_name='actions')
    action_by = models.ForeignKey(User, on_delete=models.CASCADE)
    previous_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

class LeavePolicy(models.Model):
    """
    Hierarchical leave policy: Tenant > School > Department
    Resolution: most specific wins (Department > School > Tenant > LeaveType global defaults)
    """
    SCOPE_CHOICES = [
        ('tenant', 'Tenant-Wide'),
        ('school', 'School-Wide'),
        ('department', 'Department'),
    ]

    # Scope — only ONE of these should be set per record
    scope           = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    tenant          = models.ForeignKey(
                        'tenants.Client', on_delete=models.CASCADE,
                        related_name='leave_policies', null=True, blank=True
                      )
    school          = models.ForeignKey(
                        'core.School', on_delete=models.CASCADE,
                        related_name='leave_policies', null=True, blank=True
                      )
    department      = models.ForeignKey(
                        'core.Department', on_delete=models.CASCADE,
                        related_name='leave_policies', null=True, blank=True
                      )

    # Which leave type this policy governs
    leave_type      = models.ForeignKey(
                        'leave_management.LeaveType', on_delete=models.CASCADE,
                        related_name='policies'
                      )

    # Overridable fields — null means "inherit from parent scope"
    annual_quota         = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    carry_forward        = models.BooleanField(null=True, blank=True)
    max_carry_forward    = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    allows_half_day      = models.BooleanField(null=True, blank=True)
    requires_attachment  = models.BooleanField(null=True, blank=True)
    min_notice_days      = models.PositiveIntegerField(null=True, blank=True)
    max_consecutive_days = models.PositiveIntegerField(null=True, blank=True)

    effective_from  = models.DateField()
    effective_to    = models.DateField(null=True, blank=True)   # null = indefinitely active
    is_active       = models.BooleanField(default=True)

    created_by      = models.ForeignKey(
                        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                        null=True, related_name='created_leave_policies'
                      )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # A (scope, tenant/school/department, leave_type, effective_from) combo must be unique
            models.UniqueConstraint(
                condition=models.Q(scope='tenant'),
                fields=['scope', 'tenant', 'leave_type', 'effective_from'],
                name='leave_management_unique_tenant_policy_date'
            ),
            models.UniqueConstraint(
                condition=models.Q(scope='school'),
                fields=['scope', 'school', 'leave_type', 'effective_from'],
                name='leave_management_unique_school_policy_date'
            ),
            models.UniqueConstraint(
                condition=models.Q(scope='department'),
                fields=['scope', 'department', 'leave_type', 'effective_from'],
                name='leave_management_unique_dept_policy_date'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'leave_type', 'is_active']),
            models.Index(fields=['school', 'leave_type', 'is_active']),
            models.Index(fields=['department', 'leave_type', 'is_active']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        scope_field_map = {
            'tenant': ('tenant', 'school', 'department'),
            'school': ('school', 'tenant', 'department'),
            'department': ('department', 'tenant', 'school'),
        }
        required, *should_be_null = scope_field_map.get(self.scope, (None, None, None))
        if not required or not getattr(self, required):
            raise ValidationError(f"Scope '{self.scope}' requires '{required}' to be set.")
        for field in should_be_null:
            if getattr(self, field):
                raise ValidationError(
                    f"Scope '{self.scope}': field '{field}' must be null."
                )

    def __str__(self):
        scope_label = {
            'tenant': self.tenant.name if self.tenant else '?',
            'school': self.school.name if self.school else '?',
            'department': self.department.name if self.department else '?',
        }.get(self.scope, '?')
        return f"[{self.scope.upper()}] {scope_label} — {self.leave_type.code}"
