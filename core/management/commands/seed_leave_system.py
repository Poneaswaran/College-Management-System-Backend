import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import tenant_context
from decimal import Decimal

from tenants.models import Client
from profile_management.models import FacultyProfile
from leave_management.models import LeaveType, FacultyLeaveBalance

class Command(BaseCommand):
    help = "Seeds leave types and leave balances for all faculty."

    def add_arguments(self, parser):
        parser.add_argument('--schema', type=str, default='vels', help='Tenant schema name')

    def handle(self, *args, **options):
        schema_name = options['schema']
        
        try:
            tenant = Client.objects.get(schema_name=schema_name)
        except Client.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant '{schema_name}' does not exist."))
            return

        with tenant_context(tenant):
            self.stdout.write(self.style.MIGRATE_HEADING(f"--- Seeding Leave System for {schema_name} ---"))
            
            with transaction.atomic():
                # 1. Seed Leave Types
                leave_types_data = [
                    {'name': 'Casual Leave', 'code': 'CL', 'annual_quota': 12.0, 'allows_half_day': True},
                    {'name': 'Sick Leave', 'code': 'SL', 'annual_quota': 10.0, 'allows_half_day': True},
                    {'name': 'Earned Leave', 'code': 'EL', 'annual_quota': 15.0, 'allows_half_day': False},
                    {'name': 'On Duty', 'code': 'OD', 'annual_quota': 20.0, 'allows_half_day': True},
                    {'name': 'Maternity Leave', 'code': 'ML', 'annual_quota': 180.0, 'allows_half_day': False},
                    {'name': 'Paternity Leave', 'code': 'PL', 'annual_quota': 15.0, 'allows_half_day': False},
                ]
                
                leave_types_map = {}
                for lt_data in leave_types_data:
                    lt, created = LeaveType.objects.get_or_create(
                        code=lt_data['code'],
                        defaults={
                            'name': lt_data['name'],
                            'annual_quota': Decimal(str(lt_data['annual_quota'])),
                            'allows_half_day': lt_data['allows_half_day']
                        }
                    )
                    leave_types_map[lt_data['code']] = lt
                    if created:
                        self.stdout.write(f"Created Leave Type: {lt.name}")

                # 2. Seed Faculty Leave Balances
                faculties = FacultyProfile.objects.all()
                self.stdout.write(f"Seeding balances for {faculties.count()} faculty members...")
                
                balances_created = 0
                for faculty in faculties:
                    for code, lt in leave_types_map.items():
                        # Heuristic filtering for Maternity/Paternity
                        if code == 'ML' and faculty.gender == 'MALE':
                            continue
                        if code == 'PL' and faculty.gender == 'FEMALE':
                            continue
                        
                        balance, created = FacultyLeaveBalance.objects.get_or_create(
                            faculty=faculty,
                            leave_type=lt,
                            year=2024,
                            defaults={
                                'total_granted': lt.annual_quota,
                                'used': Decimal('0.0'),
                                'pending': Decimal('0.0')
                            }
                        )
                        if created:
                            balances_created += 1
                
                self.stdout.write(self.style.SUCCESS(f"Successfully seeded {balances_created} leave balance records."))
