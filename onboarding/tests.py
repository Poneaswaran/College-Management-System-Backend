from unittest.mock import patch

from django.test import TestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from configuration.models import Configuration
from configuration.services.config_service import ConfigService
from onboarding.services.id_card_service import IDCardService
from onboarding.views.etag_mixin import ETagMixin


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
