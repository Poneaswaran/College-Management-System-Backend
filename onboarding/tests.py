from unittest.mock import patch
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from configuration.models import Configuration
from configuration.services.config_service import ConfigService
from core.models import Course, Department, Role, Section
from onboarding.constants import TASK_ENTITY_STUDENT
from onboarding.permissions import OnboardingAccessPermission
from onboarding.services.approval_service import StudentApprovalService
from onboarding.services.id_card_service import IDCardService
from onboarding.models import TemporaryOnboardingAccess
from onboarding.views.etag_mixin import ETagMixin
from profile_management.models import StudentProfile

User = get_user_model()


class ConfigServiceTests(TestCase):
    def test_get_returns_default_when_missing(self):
        value = ConfigService.get("onboarding.id_card.qr_ttl", 2592000)
        self.assertEqual(value, 2592000)

    def test_get_returns_db_value_when_present(self):
        Configuration.objects.create(
            key="onboarding.id_card.qr_ttl",
            value=123,
            is_active=True,
        )
        value = ConfigService.get("onboarding.id_card.qr_ttl", 2592000)
        self.assertEqual(value, 123)


class IDCardConfigTests(TestCase):
    def test_qr_payload_respects_configured_fields(self):
        Configuration.objects.create(
            key="onboarding.id_card.qr_payload",
            value={"include_fields": ["entity_id", "card_id", "exp"]},
            is_active=True,
        )
        payload = IDCardService._build_payload("STUDENT", 1, 2, "ISSUED")
        self.assertIn("entity_id", payload)
        self.assertIn("card_id", payload)
        self.assertIn("exp", payload)
        self.assertNotIn("issued_at", payload)


class ETagMixinTests(TestCase):
    def test_etag_returns_304_when_if_none_match_matches(self):
        factory = APIRequestFactory()

        class DummyView(ETagMixin, APIView):
            authentication_classes = []
            permission_classes = []

            def get(self, request):
                return Response({"hello": "world", "updated_at": "2026-01-01T00:00:00Z"})

        first_response = DummyView.as_view()(factory.get("/dummy"))
        etag = first_response["ETag"]

        second_request = factory.get("/dummy", HTTP_IF_NONE_MATCH=etag)
        second_response = DummyView.as_view()(second_request)

        self.assertEqual(second_response.status_code, 304)


class TemporaryAccessPermissionTests(TestCase):
    def test_faculty_with_active_temp_access_can_bulk_upload(self):
        dept = Department.objects.create(name="Computer Science", code="CSE")
        faculty_role = Role.objects.create(name="Faculty", code="FACULTY", department=dept)
        admin_role = Role.objects.create(name="Admin", code="ADMIN", is_global=True)

        faculty_user = User.objects.create_user(
            email="faculty@test.com",
            password="pass",
            role=faculty_role,
            department=dept,
            is_active=True,
        )
        admin_user = User.objects.create_user(
            email="admin@test.com",
            password="pass",
            role=admin_role,
            is_active=True,
        )

        TemporaryOnboardingAccess.objects.create(
            faculty_user=faculty_user,
            granted_by=admin_user,
            scope=TASK_ENTITY_STUDENT,
            can_bulk_upload=True,
            can_retry=False,
            expires_at=timezone.now() + timedelta(hours=2),
            is_active=True,
        )

        request = APIRequestFactory().post("/api/admin/students/bulk-upload/")
        request.user = faculty_user

        class DummyView:
            onboarding_entity_type = TASK_ENTITY_STUDENT
            onboarding_action = "bulk_upload"

        self.assertTrue(OnboardingAccessPermission().has_permission(request, DummyView()))


class StudentApprovalServiceTests(TestCase):
    def test_pending_then_approve_enables_student(self):
        dept = Department.objects.create(name="Electronics", code="ECE")
        course = Course.objects.create(department=dept, name="BTech", code="BTECH", duration_years=4)
        section = Section.objects.create(course=course, name="A", year=1)
        student_role = Role.objects.create(name="Student", code="STUDENT", department=dept)
        admin_role = Role.objects.create(name="Admin", code="ADMIN", is_global=True)

        student_user = User.objects.create_user(
            email="student@test.com",
            password="pass",
            register_number="REG001",
            role=student_role,
            department=dept,
            is_active=True,
        )
        admin_user = User.objects.create_user(
            email="admin2@test.com",
            password="pass",
            role=admin_role,
            is_active=True,
        )

        profile = StudentProfile.objects.create(
            user=student_user,
            first_name="Test",
            last_name="Student",
            phone="9999999999",
            register_number="REG001",
            department=dept,
            course=course,
            section=section,
            year=1,
            semester=1,
            is_active=True,
            academic_status="ACTIVE",
        )

        pending = StudentApprovalService.ensure_pending(profile, requested_by=admin_user)
        self.assertEqual(pending.status, "PENDING")
        profile.refresh_from_db()
        student_user.refresh_from_db()
        self.assertFalse(profile.is_active)
        self.assertFalse(student_user.is_active)

        approved = StudentApprovalService.approve(profile, approved_by=admin_user, remarks="OK")
        self.assertEqual(approved.status, "APPROVED")
        profile.refresh_from_db()
        student_user.refresh_from_db()
        self.assertTrue(profile.is_active)
        self.assertTrue(student_user.is_active)
