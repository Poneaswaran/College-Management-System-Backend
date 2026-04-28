import os
import sys
import django

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CMS.settings')
django.setup()

from tenants.models import Client, Domain

def create_tenant():
    # Check if public tenant exists first (often required by django-tenants)
    if not Client.objects.filter(schema_name='public').exists():
        print("Creating public tenant...")
        public_tenant = Client(
            schema_name='public',
            name='Public Schema',
            short_name='Public'
        )
        public_tenant.save()
        
        Domain.objects.create(
            domain='localhost',
            tenant=public_tenant,
            is_primary=True
        )
        print("Public tenant created.")

    # Create the vels tenant
    if not Client.objects.filter(schema_name='vels').exists():
        print("Creating vels tenant...")
        tenant = Client(
            schema_name='vels',
            name='Vels Institute of Science, Technology & Advanced Studies (VISTAS)',
            short_name='VISTAS'
        )
        tenant.save()

        Domain.objects.create(
            domain='vels.localhost',
            tenant=tenant,
            is_primary=True
        )
        print("Vels tenant created successfully.")
    else:
        print("Vels tenant already exists.")

if __name__ == "__main__":
    create_tenant()
