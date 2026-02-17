"""
Management command to update all user passwords to use Argon2 hashing
Re-hashes all existing passwords with the new Argon2 algorithm
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import User


class Command(BaseCommand):
    help = 'Update all user passwords to use Argon2 hashing'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('Updating Passwords to Argon2...'))
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write('')
        
        # Default password for all users
        default_password = 'Test@123'
        
        with transaction.atomic():
            # Get all users
            users = User.objects.all()
            
            if not users.exists():
                self.stdout.write(self.style.ERROR('✗ No users found!'))
                return
            
            self.stdout.write(f'Found {users.count()} users to update...')
            self.stdout.write('')
            
            updated_count = 0
            
            for user in users:
                # Set password with Argon2 (Django will use the first hasher in PASSWORD_HASHERS)
                user.set_password(default_password)
                user.save(update_fields=['password'])
                
                updated_count += 1
                
                # Show progress
                identifier = user.email or user.register_number
                self.stdout.write(self.style.SUCCESS(f'  ✓ Updated: {identifier}'))
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS(f'✓ Successfully updated {updated_count} user passwords to Argon2!'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('All passwords are now hashed with Argon2 algorithm'))
            self.stdout.write(self.style.SUCCESS('Password for all users: Test@123'))
            self.stdout.write('')
