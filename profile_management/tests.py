from django.test import TestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from configuration.models import Configuration, FeatureFlag
from configuration.services.config_service import ConfigService, FeatureFlagService
from profile_management.profile.etag_mixin import ETagMixin


class ProfileConfigServiceTests(TestCase):
	def test_tenant_specific_config_overrides_global(self):
		Configuration.objects.create(
			sub_app="profile",
			key="student.allowed_edit_fields",
			value=["first_name"],
			tenant_key=None,
			is_active=True,
		)
		Configuration.objects.create(
			sub_app="profile",
			key="student.allowed_edit_fields",
			value=["first_name", "phone"],
			tenant_key="CSE",
			is_active=True,
		)

		value = ConfigService.get(
			key="student.allowed_edit_fields",
			tenant_key="CSE",
			sub_app="profile",
		)
		self.assertEqual(value, ["first_name", "phone"])

	def test_config_falls_back_to_global(self):
		Configuration.objects.create(
			sub_app="profile",
			key="student.allowed_edit_fields",
			value=["first_name"],
			tenant_key=None,
			is_active=True,
		)

		value = ConfigService.get(
			key="student.allowed_edit_fields",
			tenant_key="EEE",
			sub_app="profile",
		)
		self.assertEqual(value, ["first_name"])

	def test_feature_flag_tenant_override(self):
		FeatureFlag.objects.create(
			sub_app="profile",
			key="enable_student_profile_edit",
			is_enabled=False,
			tenant_key=None,
			is_active=True,
		)
		FeatureFlag.objects.create(
			sub_app="profile",
			key="enable_student_profile_edit",
			is_enabled=True,
			tenant_key="CSE",
			is_active=True,
		)

		self.assertTrue(
			FeatureFlagService.is_enabled(
				key="enable_student_profile_edit",
				tenant_key="CSE",
				sub_app="profile",
			)
		)
		self.assertFalse(
			FeatureFlagService.is_enabled(
				key="enable_student_profile_edit",
				tenant_key="ECE",
				sub_app="profile",
			)
		)


class ProfileETagTests(TestCase):
	def test_etag_returns_304_when_if_none_match_matches(self):
		factory = APIRequestFactory()

		class DummyView(ETagMixin, APIView):
			authentication_classes = []
			permission_classes = []

			def get(self, request):
				return Response({"value": 1})

		first_request = factory.get("/dummy")
		first_response = DummyView.as_view()(first_request)
		etag = first_response["ETag"]

		second_request = factory.get("/dummy", HTTP_IF_NONE_MATCH=etag)
		second_response = DummyView.as_view()(second_request)

		self.assertEqual(second_response.status_code, 304)
