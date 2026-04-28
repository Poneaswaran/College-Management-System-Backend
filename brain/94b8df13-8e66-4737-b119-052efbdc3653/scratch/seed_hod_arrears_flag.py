import os
import django
from django.db import connection

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CMS.settings')
django.setup()

from tenants.models import Client
from configuration.models import FeatureFlag

def seed_feature_flag():
    tenants = Client.objects.all()
    if not tenants:
        print("No tenants found.")
        return

    for tenant in tenants:
        connection.set_tenant(tenant)
        flag, created = FeatureFlag.objects.get_or_create(
            key='hod_arrears',
            defaults={
                'description': 'Allows HOD to view students with arrears in their department.',
                'is_enabled_globally': True
            }
        )
        if created:
            print(f"[{tenant.schema_name}] Feature flag '{flag.key}' created and enabled globally.")
        else:
            # If it exists, ensure it's enabled globally for testing
            flag.is_enabled_globally = True
            flag.save()
            print(f"[{tenant.schema_name}] Feature flag '{flag.key}' already exists, updated to enabled.")

if __name__ == "__main__":
    seed_feature_flag()
