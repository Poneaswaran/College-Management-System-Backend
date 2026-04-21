"""
Django management command to clean up old notifications.
Should be run as a daily cron job.

Usage: python manage.py cleanup_notifications
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context
from tenants.models import Client

from notifications.services.cleanup_service import (
    cleanup_old_notifications,
    auto_dismiss_expired_notifications,
    get_cleanup_statistics,
)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old and expired notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        """Execute the cleanup command across all tenant schemas."""
        dry_run = options['dry_run']
        verbose = options['verbose']

        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== Notification Cleanup Started at {timezone.now()} ===\n'
            )
        )

        tenants = Client.objects.exclude(schema_name='public')
        if not tenants.exists():
            self.stdout.write(self.style.WARNING('No tenant schemas found.'))
            return

        for tenant in tenants:
            self.stdout.write(
                self.style.MIGRATE_HEADING(f'\n--- Tenant: {tenant.schema_name} ({tenant.name}) ---')
            )
            with schema_context(tenant.schema_name):
                self._run_cleanup(dry_run, verbose)

        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== Notification Cleanup Finished at {timezone.now()} ===\n'
            )
        )

    def _run_cleanup(self, dry_run: bool, verbose: bool) -> None:
        """Run notification cleanup for the current schema context."""
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No notifications will be deleted\n')
            )

            stats = get_cleanup_statistics()

            self.stdout.write('Cleanup preview:')
            self.stdout.write(f"  Dismissed notifications to delete: {stats['dismissed_candidates']}")
            self.stdout.write(f"  Old read notifications to delete: {stats['read_candidates']}")
            self.stdout.write(f"  Expired notifications to delete: {stats['expired_candidates']}")
            self.stdout.write(
                self.style.WARNING(
                    f"\n  TOTAL that would be deleted: {stats['total_candidates']}\n"
                )
            )
            self.stdout.write(f"  Current total notifications: {stats['total_notifications']}")

        else:
            # Auto-dismiss expired notifications first
            try:
                self.stdout.write('Auto-dismissing expired notifications...')
                dismissed_count = auto_dismiss_expired_notifications()

                if verbose:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Auto-dismissed {dismissed_count} expired notifications'
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error auto-dismissing: {str(e)}')
                )
                logger.error(f"Error in auto-dismiss: {str(e)}")

            # Clean up old notifications
            try:
                self.stdout.write('\nCleaning up old notifications...')
                counts = cleanup_old_notifications()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ Cleanup completed successfully:\n'
                    )
                )
                self.stdout.write(f"  Dismissed notifications deleted: {counts['dismissed']}")
                self.stdout.write(f"  Old read notifications deleted: {counts['read']}")
                self.stdout.write(f"  Expired notifications deleted: {counts['expired']}")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n  TOTAL DELETED: {counts['total']}\n"
                    )
                )

                if counts['total'] > 0:
                    logger.info(f"Cleanup command deleted {counts['total']} notifications")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'\n✗ Cleanup failed: {str(e)}\n')
                )
                logger.error(f"Cleanup command failed: {str(e)}")
                raise
