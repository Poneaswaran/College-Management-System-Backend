"""
LeavePolicy resolver — returns the most specific active policy for a
(faculty, leave_type, as_of_date) combination.

Resolution order: Department → School → Tenant → LeaveType global defaults
"""
from datetime import date
from typing import Optional
from dataclasses import dataclass
from decimal import Decimal
from django.db import models


@dataclass
class ResolvedPolicy:
    annual_quota:         Decimal
    carry_forward:        bool
    max_carry_forward:    Decimal
    allows_half_day:      bool
    requires_attachment:  bool
    min_notice_days:      int
    max_consecutive_days: Optional[int]
    source_scope:         str   # 'department' | 'school' | 'tenant' | 'global'


def resolve_policy(faculty_profile, leave_type, as_of: date = None) -> ResolvedPolicy:
    """
    Walk the hierarchy and merge fields top-down so the most specific
    non-null value wins.

    Args:
        faculty_profile: FacultyProfile instance (has .department, .department.school)
        leave_type:      LeaveType instance
        as_of:           Date to check policy effectivity (defaults to today)
    """
    from .models import LeavePolicy
    if as_of is None:
        as_of = date.today()

    department = faculty_profile.department
    school     = department.school if department else None
    
    # In django-tenants, the Client (Tenant) can be fetched from the connection
    # but the model allows per-tenant overrides if explicitly linked.
    # We will try to find policies linked to any tenant, or just the one linked.
    from django.db import connection
    current_tenant = getattr(connection, 'tenant', None)

    # Build candidate querysets per scope
    base_qs = LeavePolicy.objects.filter(
        leave_type=leave_type,
        is_active=True,
        effective_from__lte=as_of
    ).filter(
        models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=as_of)
    )

    dept_policy   = base_qs.filter(scope='department', department=department).order_by('-effective_from').first() if department else None
    school_policy = base_qs.filter(scope='school', school=school).order_by('-effective_from').first() if school else None
    
    # For tenant scope, we look for policies linked to the current tenant (Client)
    tenant_policy = None
    if current_tenant:
        tenant_policy = base_qs.filter(scope='tenant', tenant=current_tenant).order_by('-effective_from').first()

    # Collect sources in resolution order (most specific first)
    sources = [
        (dept_policy,   'department'),
        (school_policy, 'school'),
        (tenant_policy, 'tenant'),
    ]

    # Fields that can be overridden
    fields = [
        'annual_quota', 'carry_forward', 'max_carry_forward',
        'allows_half_day', 'requires_attachment', 'min_notice_days', 'max_consecutive_days'
    ]

    # Global defaults from LeaveType model
    global_defaults = {
        'annual_quota':         leave_type.annual_quota,
        'carry_forward':        False,
        'max_carry_forward':    Decimal('0'),
        'allows_half_day':      leave_type.allows_half_day,
        'requires_attachment':  leave_type.requires_attachment,
        'min_notice_days':      0,
        'max_consecutive_days': None,
    }

    resolved = dict(global_defaults)
    winning_scope = 'global'

    # Walk from least specific (tenant) to most specific (department)
    # so the most specific value overwrites
    for policy_obj, scope_name in reversed(sources):
        if policy_obj is None:
            continue
        for field in fields:
            val = getattr(policy_obj, field, None)
            if val is not None:
                resolved[field] = val
                winning_scope = scope_name

    return ResolvedPolicy(source_scope=winning_scope, **resolved)
