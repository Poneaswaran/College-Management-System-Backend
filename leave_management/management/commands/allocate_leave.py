from django.core.management.base import BaseCommand
from django.utils import timezone
from leave_management.models import LeaveType, FacultyLeaveBalance
from profile_management.models import FacultyProfile
from leave_management.policy_resolver import resolve_policy

class Command(BaseCommand):
    help = 'Allocates leave balances for all faculty based on resolved policies for the given year'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Academic year for allocation (e.g. 2025)')
        parser.add_argument('--force', action='store_true', help='Overwrite existing balances')

    def handle(self, *args, **options):
        year = options['year'] or timezone.now().year
        force = options['force']
        
        faculties = FacultyProfile.objects.filter(is_active=True)
        leave_types = LeaveType.objects.filter(is_active=True)
        
        count = 0
        for faculty in faculties:
            for lt in leave_types:
                # Resolve policy for this faculty and leave type
                resolved = resolve_policy(faculty, lt)
                
                # Get or create balance
                balance, created = FacultyLeaveBalance.objects.get_or_create(
                    faculty=faculty,
                    leave_type=lt,
                    year=year,
                    defaults={'total_granted': resolved.annual_quota}
                )
                
                if not created and force:
                    balance.total_granted = resolved.annual_quota
                    balance.save()
                    
                if created or force:
                    count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully allocated {count} leave balances for year {year}'))
