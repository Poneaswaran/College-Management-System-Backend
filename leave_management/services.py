from datetime import timedelta
from django.db.models import Q
from .models import WeekendSetting, HolidayCalendar, FacultyLeaveBalance, LeaveType

class LeaveService:
    @staticmethod
    def calculate_leave_days(faculty, start_date, end_date, duration_type):
        """
        Calculates total leave days excluding weekends and holidays based on settings.
        """
        if duration_type != 'FULL':
            return 0.5
        
        # Get weekends for the faculty's department (or global if department not set)
        department = faculty.department
        weekends = WeekendSetting.objects.filter(
            Q(department=department) | Q(department__isnull=True),
            is_weekend=True
        ).values_list('day', flat=True)
        
        # Get holidays
        holidays = HolidayCalendar.objects.filter(
            date__range=[start_date, end_date]
        ).values_list('date', flat=True)
        
        total_days = 0
        current_date = start_date
        while current_date <= end_date:
            # weekday() returns 0 for Monday, 6 for Sunday
            if current_date.weekday() not in weekends:
                if current_date not in holidays:
                    total_days += 1
            current_date += timedelta(days=1)
            
        return float(total_days)

    @staticmethod
    def check_balance(faculty, leave_type, days):
        """
        Checks if faculty has enough balance.
        """
        try:
            balance = FacultyLeaveBalance.objects.get(faculty=faculty, leave_type=leave_type)
            return float(balance.remaining) >= float(days)
        except FacultyLeaveBalance.DoesNotExist:
            return False

    @staticmethod
    def validate_request(faculty, leave_type, start_date, end_date, duration_type):
        """
        Validates leave request for overlapping and other rules.
        """
        from .models import FacultyLeaveRequest
        from .policy_resolver import resolve_policy
        from datetime import date
        
        resolved = resolve_policy(faculty, leave_type, start_date)
        
        if start_date > end_date:
            return False, "Start date cannot be after end date."

        # 1. Policy Validations
        # Min notice check
        days_notice = (start_date - date.today()).days
        if days_notice < resolved.min_notice_days:
            return False, f"At least {resolved.min_notice_days} days notice is required for this leave type."
            
        # Half day check
        if duration_type != 'FULL' and not resolved.allows_half_day:
            return False, f"Half-day leaves are not allowed for {leave_type.name} per current policy."

        # 2. Overlapping requests
        overlapping = FacultyLeaveRequest.objects.filter(
            faculty=faculty,
            status__in=['SUBMITTED', 'APPROVED'],
            start_date__lte=end_date,
            end_date__gte=start_date
        ).exists()
        
        if overlapping:
            return False, "You already have a pending or approved leave request for these dates."
        
        # 3. Balance check
        days = LeaveService.calculate_leave_days(faculty, start_date, end_date, duration_type)
        if days == 0:
            return False, "The selected period consists only of weekends or holidays."
            
        # Max consecutive check
        if resolved.max_consecutive_days and days > resolved.max_consecutive_days:
            return False, f"Maximum consecutive days allowed for {leave_type.name} is {resolved.max_consecutive_days}."

        if not LeaveService.check_balance(faculty, leave_type, days):
            return False, f"Insufficient balance for {leave_type.name} (Required: {days})."
        
        return True, ""
