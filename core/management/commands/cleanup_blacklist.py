"""
Management command to clean up expired tokens from blacklist
Run periodically via cron job or task scheduler
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context
from tenants.models import Client
from core.models import TokenBlacklist


class Command(BaseCommand):
    help = 'Remove expired tokens from blacklist to keep database clean'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=0,
            help='Also remove tokens expired more than X days ago (optional)',
        )

    def handle(self, *args, **options):
        """Execute the command across all tenant schemas."""
        days = options['days']

        tenants = Client.objects.exclude(schema_name='public')
        total_deleted = 0
        total_old_deleted = 0

        for tenant in tenants:
            with schema_context(tenant.schema_name):
                deleted_count, _ = TokenBlacklist.cleanup_expired()
                total_deleted += deleted_count

                if days > 0:
                    cutoff_date = timezone.now() - timezone.timedelta(days=days)
                    old_deleted = TokenBlacklist.objects.filter(
                        expires_at__lt=cutoff_date
                    ).delete()[0]
                    total_old_deleted += old_deleted

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully removed {total_deleted} expired token(s) from blacklist'
            )
        )

        if days > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Also removed {total_old_deleted} token(s) expired more than {days} days ago'
                )
            )
