import os
import sys
import django
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

# Load .env file
env_path = project_root / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CMS.settings')
django.setup()

from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate
from profile_management.profile.views import StudentDashboardView, resolve_register_number
from profile_management.models import StudentProfile, FacultyProfile
from core.models import User

def run_tests():
    print("============================================================")
    print("Testing 'me' Student Dashboard API & Security Rules")
    print("============================================================")

    factory = APIRequestFactory()

    with schema_context('vels'):
        # 1. Find a Student user and profile
        student_profile = StudentProfile.objects.first()
        if not student_profile:
            print("❌ No student profile found to test with.")
            return

        student_user = student_profile.user
        print(f"Testing with Student: {student_profile.full_name} ({student_profile.register_number})")

        # Test A: resolve_register_number for "me"
        resolved_reg, err = resolve_register_number(
            request=type('Request', (), {'user': student_user})(),
            register_number="me"
        )
        assert err is None, f"Expected no error resolving 'me' for student, got: {err}"
        assert resolved_reg == student_profile.register_number, f"Expected {student_profile.register_number}, got {resolved_reg}"
        print("✓ Test A: Successfully resolved 'me' to student's register number.")

        # Test B: resolve_register_number for own register number
        resolved_reg, err = resolve_register_number(
            request=type('Request', (), {'user': student_user})(),
            register_number=student_profile.register_number
        )
        assert err is None, f"Expected no error, got: {err}"
        assert resolved_reg == student_profile.register_number
        print("✓ Test B: Successfully allowed student accessing own register number.")

        # Test C: resolve_register_number for other student's register number (Should fail)
        other_student = StudentProfile.objects.exclude(id=student_profile.id).first()
        if other_student:
            resolved_reg, err = resolve_register_number(
                request=type('Request', (), {'user': student_user})(),
                register_number=other_student.register_number
            )
            assert err is not None, "Expected error when student accesses other student profile"
            assert "authorized" in err
            print("✓ Test C: Successfully blocked student from accessing another student's profile.")
        else:
            print("⚠ Test C: Skipped (no other student profile found).")

        # Test D: API View GET for "me"
        request = factory.get(f'/api/profile/students/me/dashboard/')
        force_authenticate(request, user=student_user)
        view = StudentDashboardView.as_view()
        response = view(request, register_number="me")

        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}. Response: {response.data}"
        print("✓ Test D: StudentDashboardView GET '/students/me/dashboard/' returned 200 OK.")
        print(f"   Keys returned in dashboard: {list(response.data.keys())}")

        # Test E: API View GET for another student (Should return 403)
        if other_student:
            request = factory.get(f'/api/profile/students/{other_student.register_number}/dashboard/')
            force_authenticate(request, user=student_user)
            response = view(request, register_number=other_student.register_number)
            assert response.status_code == 403, f"Expected 403 Forbidden, got {response.status_code}"
            print("✓ Test E: StudentDashboardView GET other student's dashboard blocked with 403 Forbidden.")

        # Test F: Non-student user requesting "me" (Should return 403/404)
        faculty_profile = FacultyProfile.objects.first()
        if faculty_profile:
            faculty_user = faculty_profile.user
            request = factory.get('/api/profile/students/me/dashboard/')
            force_authenticate(request, user=faculty_user)
            response = view(request, register_number="me")
            assert response.status_code in (403, 404), f"Expected 403 or 404, got {response.status_code}"
            print("✓ Test F: Faculty user requesting 'me' blocked successfully.")
        else:
            # Test with an Admin user (usually role code is ADMIN, let's find one or create mock)
            admin_user = User.objects.filter(role__code="ADMIN").first()
            if admin_user:
                request = factory.get('/api/profile/students/me/dashboard/')
                force_authenticate(request, user=admin_user)
                response = view(request, register_number="me")
                assert response.status_code in (403, 404), f"Expected 403/404 for admin using 'me', got {response.status_code}"
                print("✓ Test F: Admin user requesting 'me' blocked successfully.")

    print()
    print("🎉 All test assertions passed successfully!")
    print("============================================================")

if __name__ == "__main__":
    run_tests()
