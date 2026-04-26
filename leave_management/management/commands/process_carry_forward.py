from django.core.management.base import BaseCommand
from django.db import transaction
from leave_management.models import LeaveType, FacultyLeaveBalance
from profile_management.models import FacultyProfile
from leave_management.policy_resolver import resolve_policy
from decimal import Decimal

class Command(BaseCommand):
    help = 'Processes leave carry-forward from one year to the next'

    def add_arguments(self, parser):
        parser.add_argument('--from_year', type=int, required=True, help='Year to carry from')
        parser.add_argument('--to_year', type=int, required=True, help='Year to carry to')

    def handle(self, *args, **options):
        from_yr = options['from_year']
        to_yr = options['to_year']
        
        faculties = FacultyProfile.objects.filter(is_active=True)
        leave_types = LeaveType.objects.filter(is_active=True)
        
        processed_count = 0
        
        with transaction.atomic():
            for faculty in faculties:
                for lt in leave_types:
                    # Resolve policy for the target year (to_yr)
                    resolved = resolve_policy(faculty, lt)
                    
                    if not resolved.carry_forward:
                        continue
                        
                    # Get balance from last year
                    try:
                        old_balance = FacultyLeaveBalance.objects.get(
                            faculty=faculty, leave_type=lt, year=from_yr
                        )
                        remaining = old_balance.remaining
                        
                        if remaining <= 0:
                            continue
                            
                        # Apply cap
                        carry_amount = min(remaining, resolved.max_carry_forward)
                        
                        # Add to new year balance
                        new_balance, created = FacultyLeaveBalance.objects.get_or_create(
                            faculty=faculty,
                            leave_type=lt,
                            year=to_yr,
                            defaults={'total_granted': resolved.annual_quota}
                        )
                        
                        # Add carry amount to total_granted for the new year
                        # (or handle as a separate field if model supported it, but here we add to total)
                        new_balance.total_granted = Decimal(str(new_balance.total_granted)) + Decimal(str(carry_amount))
                        new_balance.save()
                        
                        processed_count += 1
                        
                    except FacultyLeaveBalance.DoesNotExist:
                        continue
        
        self.stdout.write(self.style.SUCCESS(f'Successfully processed carry-forward for {processed_count} records from {from_yr} to {to_yr}'))
