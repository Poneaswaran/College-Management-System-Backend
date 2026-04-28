
import os
import django
from django_tenants.utils import tenant_context

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CMS.settings')
django.setup()

from tenants.models import Client
from profile_management.models import StudentProfile
from timetable.models import TimetableEntry

try:
    tenant = Client.objects.get(schema_name='vels')
    with tenant_context(tenant):
        total_students = StudentProfile.objects.count()
        # Sections that have at least one timetable entry with a room
        sections_with_rooms = TimetableEntry.objects.filter(room__isnull=False).values_list('section_id', flat=True).distinct()
        students_with_rooms = StudentProfile.objects.filter(section_id__in=sections_with_rooms).count()
        
        print(f"Total Students: {total_students}")
        print(f"Students with assigned Classrooms (via Timetable): {students_with_rooms}")
        print(f"Students without Classrooms: {total_students - students_with_rooms}")
except Exception as e:
    print(f"Error: {e}")
