import os
import sys
import django
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CMS.settings')
django.setup()

from profile_management.models import StudentProfile
from profile_management.profile.serializers import StudentProfileSerializer
from django_tenants.utils import schema_context

with schema_context('vels'):
    student = StudentProfile.objects.first()
    if student:
        serializer = StudentProfileSerializer(student)
        print(serializer.data)
    else:
        print("No student found")
