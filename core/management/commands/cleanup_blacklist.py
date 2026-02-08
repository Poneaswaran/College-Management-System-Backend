"""
Management command to clean up expired tokens from blacklist
Run periodically via cron job or task scheduler
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
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
        """Execute the command"""
        days = options['days']
        
        # Clean up expired tokens
        deleted_count, _ = TokenBlacklist.cleanup_expired()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully removed {deleted_count} expired token(s) from blacklist'
            )
        )
        
        # If days specified, also clean up old expired tokens
        if days > 0:
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            old_deleted = TokenBlacklist.objects.filter(
                expires_at__lt=cutoff_date
            ).delete()[0]
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Also removed {old_deleted} token(s) expired more than {days} days ago'
                )
            )
        
        # Show statistics
        total_blacklisted = TokenBlacklist.objects.count()
        self.stdout.write(
            self.style.WARNING(
                f'Total blacklisted tokens in database: {total_blacklisted}'
            )
        )
