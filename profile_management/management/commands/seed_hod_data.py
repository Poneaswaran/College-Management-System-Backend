from django.core.management.base import BaseCommand
from configuration.models import FeatureFlag
from profile_management.models import FacultyProfile, FacultyPublication
from core.models import Role, User
import random

class Command(BaseCommand):
    help = "Seed HOD profile data and enable feature flag"

    def handle(self, *args, **options):
        # 1. Enable feature flag
        flag, created = FeatureFlag.objects.get_or_create(
            key="hod_profile",
            defaults={
                "description": "Enables detailed HOD profile page",
                "is_enabled_globally": True
            }
        )
        if not created:
            flag.is_enabled_globally = True
            flag.save()
        self.stdout.write(self.style.SUCCESS("Feature flag 'hod_profile' enabled globally."))

        # 1b. Enable hod_students flag
        flag_students, created = FeatureFlag.objects.get_or_create(
            key="hod_students",
            defaults={
                "description": "Enables HOD student list view",
                "is_enabled_globally": True
            }
        )
        if not created:
            flag_students.is_enabled_globally = True
            flag_students.save()
        self.stdout.write(self.style.SUCCESS("Feature flag 'hod_students' enabled globally."))

        # 2. Find HODs and seed some data if empty
        hod_role = Role.objects.filter(code="HOD").first()
        if not hod_role:
            self.stdout.write(self.style.ERROR("HOD role not found."))
            return

        hod_users = User.objects.filter(role=hod_role)
        if not hod_users.exists():
            # Try to find users with HOD in designation
            hod_profiles = FacultyProfile.objects.filter(designation__icontains="HOD")
            hod_users = [p.user for p in hod_profiles]
        
        if not hod_users:
            self.stdout.write(self.style.WARNING("No HOD users found to seed data for."))
            return

        for user in hod_users:
            profile = getattr(user, 'faculty_profile', None)
            if not profile:
                continue
            
            # Update profile with some data if missing
            updated = False
            if not profile.phone:
                profile.phone = "+91 9876543210"
                updated = True
            if not profile.experience:
                profile.experience = "20 Years"
                updated = True
            if not profile.research_interests:
                profile.research_interests = ["Cloud Computing", "Distributed Systems", "AI in Education"]
                updated = True
            if not profile.hod_since:
                from datetime import date
                profile.hod_since = date(2020, 1, 1)
                updated = True
            
            if updated:
                profile.save()
                self.stdout.write(f"Updated profile for {user.email}")

            # Seed publications if none exist
            if not profile.publications.exists():
                publications = [
                    ("Scalable Cloud Architectures", "IEEE Transactions", 2023, "JOURNAL"),
                    ("Edge Computing in Smart Cities", "ACM Conference", 2022, "CONFERENCE"),
                    ("Security in Distributed Systems", "Springer", 2021, "BOOK_CHAPTER"),
                ]
                for title, journal, year, p_type in publications:
                    FacultyPublication.objects.create(
                        faculty=profile,
                        title=title,
                        journal=journal,
                        year=year,
                        type=p_type
                    )
                self.stdout.write(f"Seeded publications for {user.email}")

        self.stdout.write(self.style.SUCCESS("HOD data seeding complete."))
