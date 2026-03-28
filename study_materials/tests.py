"""Comprehensive tests for study materials AI integration."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIClient

from core.models import Course, Department, Role, Section, User
from profile_management.models import StudentProfile
from study_materials.ai_chat_service import StudyMaterialChatService
from study_materials.ai_client_service import (
	AIClientPermanentError,
	AIClientService,
	AIClientTemporaryError,
	AIIngestResponse,
)
from study_materials.exceptions import AIServiceUnavailableError
from study_materials.models import StudyMaterial
from study_materials.tasks import (
	delete_material_vector_task,
	ingest_study_material_task,
)
from timetable.models import Subject


class StudyMaterialAITestMixin:
	"""Shared fixtures and object builders for AI integration tests."""

	password = "TestPass123!"

	def setUp(self) -> None:
		super().setUp()
		self.department = Department.objects.create(name="Computer Science", code="CSE")
		self.course = Course.objects.create(
			department=self.department,
			name="B.Tech",
			code="BTECH",
			duration_years=4,
		)
		self.section_a = Section.objects.create(
			course=self.course,
			code="A",
			name="Section A",
			year=1,
		)
		self.section_b = Section.objects.create(
			course=self.course,
			code="B",
			name="Section B",
			year=1,
		)

		self.student_role = Role.objects.create(name="Student", code="STUDENT", is_global=True)
		self.faculty_role = Role.objects.create(name="Faculty", code="FACULTY", is_global=True)
		self.admin_role = Role.objects.create(name="Admin", code="ADMIN", is_global=True)

		self.subject = Subject.objects.create(
			code="CS101",
			name="Introduction to Programming",
			department=self.department,
			semester_number=1,
			credits=3.0,
			subject_type="THEORY",
		)

		self.faculty_user = self._create_user("faculty@example.com", self.faculty_role)
		self.student_a_user = self._create_user("student.a@example.com", self.student_role)
		self.student_b_user = self._create_user("student.b@example.com", self.student_role)
		self.admin_user = self._create_user("admin@example.com", self.admin_role)

		self._create_student_profile(self.student_a_user, self.section_a, "REG001")
		self._create_student_profile(self.student_b_user, self.section_b, "REG002")

	def _create_user(self, email: str, role: Role) -> User:
		return User.objects.create_user(
			email=email,
			password=self.password,
			role=role,
			department=self.department,
		)

	def _create_student_profile(self, user: User, section: Section, register_number: str) -> StudentProfile:
		return StudentProfile.objects.create(
			user=user,
			first_name=register_number,
			phone="9999999999",
			register_number=register_number,
			department=self.department,
			course=self.course,
			section=section,
			year=1,
			semester=1,
		)

	def create_material(
		self,
		*,
		section: Section | None = None,
		status: str = "PUBLISHED",
		vectorization_status: str = "INDEXED",
		vector_document_id: str = "vec-001",
	) -> StudyMaterial:
		file_obj = SimpleUploadedFile(
			"material.pdf",
			b"%PDF-1.4 sample content",
			content_type="application/pdf",
		)
		return StudyMaterial.objects.create(
			subject=self.subject,
			section=section or self.section_a,
			faculty=self.faculty_user,
			title="Test Material",
			description="Material for AI tests",
			material_type="NOTES",
			file=file_obj,
			status=status,
			vectorization_status=vectorization_status,
			vector_document_id=vector_document_id,
		)


class AIClientServiceTests(TestCase):
	"""Unit tests for AIClientService HTTP behavior."""

	@override_settings(AI_SERVICE_BASE_URL="http://ai.local", AI_SERVICE_API_SECRET="secret-token")
	def test_ingest_document_success(self) -> None:
		session = Mock(spec=requests.Session)
		response = Mock()
		response.status_code = 200
		response.content = b'{"document_id":"vec-123"}'
		response.json.return_value = {"document_id": "vec-123"}
		response.text = '{"document_id":"vec-123"}'
		session.request.return_value = response

		client = AIClientService(session=session)
		result = client.ingest_document(
			file_name="material.pdf",
			file_bytes=b"content",
			metadata={"material_id": 1},
		)

		self.assertEqual(result.document_id, "vec-123")
		self.assertEqual(result.payload["document_id"], "vec-123")
		headers = session.request.call_args.kwargs["headers"]
		self.assertEqual(headers["X-Internal-Secret"], "secret-token")
		self.assertEqual(headers["X-Internal-Source"], "django-cms-backend")

	@override_settings(AI_SERVICE_BASE_URL="http://ai.local")
	def test_timeout_raises_temporary_error(self) -> None:
		session = Mock(spec=requests.Session)
		session.request.side_effect = requests.Timeout("timed out")

		client = AIClientService(session=session)
		with self.assertRaises(AIClientTemporaryError):
			client.query_document(message="Hello", material_id=1)

	@override_settings(AI_SERVICE_BASE_URL="http://ai.local")
	def test_server_error_raises_temporary_error(self) -> None:
		session = Mock(spec=requests.Session)
		response = Mock()
		response.status_code = 503
		response.text = "Service unavailable"
		response.content = b"Service unavailable"
		session.request.return_value = response

		client = AIClientService(session=session)
		with self.assertRaises(AIClientTemporaryError):
			client.query_document(message="Hello", material_id=1)

	@override_settings(AI_SERVICE_BASE_URL="http://ai.local")
	def test_client_error_raises_permanent_error(self) -> None:
		session = Mock(spec=requests.Session)
		response = Mock()
		response.status_code = 400
		response.text = "Bad request"
		response.content = b"Bad request"
		session.request.return_value = response

		client = AIClientService(session=session)
		with self.assertRaises(AIClientPermanentError):
			client.query_document(message="Hello", material_id=1)


class AITaskTests(StudyMaterialAITestMixin, TestCase):
	"""Unit tests for asynchronous AI ingestion and cleanup tasks."""

	def test_ingest_task_marks_material_indexed_on_success(self) -> None:
		material = self.create_material(
			status="PUBLISHED",
			vectorization_status="PENDING",
			vector_document_id="",
		)

		with patch("study_materials.tasks.AIClientService") as mock_client_cls:
			mock_client = mock_client_cls.return_value
			mock_client.ingest_document.return_value = AIIngestResponse(
				document_id="vec-999",
				payload={"document_id": "vec-999"},
			)

			ingest_study_material_task(material.id)

		material.refresh_from_db()
		self.assertEqual(material.vectorization_status, "INDEXED")
		self.assertEqual(material.vector_document_id, "vec-999")
		self.assertIsNotNone(material.last_indexed_at)

	@override_settings(AI_INGEST_MAX_RETRIES=2, AI_INGEST_BACKOFF_SECONDS=1)
	def test_ingest_task_retries_and_marks_failed_on_transient_failures(self) -> None:
		material = self.create_material(
			status="PUBLISHED",
			vectorization_status="PENDING",
			vector_document_id="",
		)

		with patch("study_materials.tasks.AIClientService") as mock_client_cls, patch(
			"study_materials.tasks.time.sleep"
		) as mock_sleep:
			mock_client = mock_client_cls.return_value
			mock_client.ingest_document.side_effect = [
				AIClientTemporaryError("timeout-1"),
				AIClientTemporaryError("timeout-2"),
			]

			ingest_study_material_task(material.id)

		material.refresh_from_db()
		self.assertEqual(material.vectorization_status, "FAILED")
		self.assertIn("timeout-2", material.vector_error_message)
		self.assertEqual(mock_sleep.call_count, 1)

	def test_delete_vector_task_calls_client(self) -> None:
		material = self.create_material()
		with patch("study_materials.tasks.AIClientService") as mock_client_cls:
			delete_material_vector_task("vec-001", material.id)

		mock_client_cls.return_value.delete_document_vectors.assert_called_once_with(
			vector_document_id="vec-001"
		)


class StudyMaterialSignalTests(StudyMaterialAITestMixin, TestCase):
	"""Tests for post-save and post-delete AI orchestration signals."""

	def test_publish_transition_enqueues_ingestion(self) -> None:
		material = self.create_material(
			status="DRAFT",
			vectorization_status="PENDING",
			vector_document_id="",
		)

		with patch("study_materials.signals.enqueue_ingestion_task") as mock_enqueue:
			material.status = "PUBLISHED"
			material.save()

		mock_enqueue.assert_called_once_with(material.id)

	def test_archive_transition_enqueues_vector_deletion(self) -> None:
		material = self.create_material(
			status="PUBLISHED",
			vectorization_status="INDEXED",
			vector_document_id="vec-archive",
		)

		with patch("study_materials.signals.enqueue_vector_deletion_task") as mock_delete:
			material.status = "ARCHIVED"
			material.save()

		mock_delete.assert_called_once_with(
			vector_document_id="vec-archive",
			material_id=material.id,
		)

	def test_delete_enqueues_vector_cleanup(self) -> None:
		material = self.create_material(
			status="PUBLISHED",
			vectorization_status="INDEXED",
			vector_document_id="vec-delete",
		)

		with patch("study_materials.signals.enqueue_vector_deletion_task") as mock_delete:
			material.delete()

		mock_delete.assert_called_once_with(
			vector_document_id="vec-delete",
			material_id=material.id,
		)


class StudyMaterialChatServiceTests(StudyMaterialAITestMixin, TestCase):
	"""Unit tests for the AI chat business logic service."""

	def test_student_same_section_can_query_indexed_material(self) -> None:
		material = self.create_material(section=self.section_a)

		with patch("study_materials.ai_chat_service.AIClientService") as mock_client_cls:
			mock_client_cls.return_value.query_document.return_value = {
				"answer": "The answer",
				"sources": ["chunk-1"],
			}

			result = StudyMaterialChatService.ask_question(
				user=self.student_a_user,
				material_id=material.id,
				message="Explain chapter 1",
			)

		self.assertEqual(result["answer"], "The answer")
		self.assertEqual(result["sources"], ["chunk-1"])

	def test_student_other_section_is_denied(self) -> None:
		material = self.create_material(section=self.section_a)
		with self.assertRaises(PermissionDenied):
			StudyMaterialChatService.ask_question(
				user=self.student_b_user,
				material_id=material.id,
				message="Can I access this?",
			)

	def test_not_indexed_material_raises_validation_error(self) -> None:
		material = self.create_material(vectorization_status="PROCESSING")
		with self.assertRaises(ValidationError):
			StudyMaterialChatService.ask_question(
				user=self.student_a_user,
				material_id=material.id,
				message="Any update?",
			)

	def test_missing_material_raises_not_found(self) -> None:
		with self.assertRaises(NotFound):
			StudyMaterialChatService.ask_question(
				user=self.student_a_user,
				material_id=99999,
				message="Unknown material",
			)

	def test_temporary_ai_failure_raises_service_unavailable(self) -> None:
		material = self.create_material(section=self.section_a)

		with patch("study_materials.ai_chat_service.AIClientService") as mock_client_cls:
			mock_client_cls.return_value.query_document.side_effect = AIClientTemporaryError(
				"timeout"
			)

			with self.assertRaises(AIServiceUnavailableError):
				StudyMaterialChatService.ask_question(
					user=self.student_a_user,
					material_id=material.id,
					message="Explain chapter 1",
				)


class StudyMaterialAIChatAPITests(StudyMaterialAITestMixin, TestCase):
	"""Integration tests for DRF AI chat endpoint."""

	def setUp(self) -> None:
		super().setUp()
		self.api_client = APIClient()
		self.url = "/api/study-materials/ai/chat/"

	def test_chat_endpoint_success(self) -> None:
		material = self.create_material(section=self.section_a)
		self.api_client.force_authenticate(user=self.student_a_user)

		with patch("study_materials.views.StudyMaterialChatService.ask_question") as mock_ask:
			mock_ask.return_value = {"answer": "Success", "sources": ["chunk"]}
			response = self.api_client.post(
				self.url,
				{"material_id": material.id, "message": "What is this?"},
				format="json",
			)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["answer"], "Success")
		self.assertEqual(response.data["sources"], ["chunk"])

	def test_chat_endpoint_validation_error(self) -> None:
		material = self.create_material(section=self.section_a)
		self.api_client.force_authenticate(user=self.student_a_user)

		response = self.api_client.post(
			self.url,
			{"material_id": material.id, "message": "   "},
			format="json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("message", response.data)

	def test_chat_endpoint_requires_authentication(self) -> None:
		material = self.create_material(section=self.section_a)
		response = self.api_client.post(
			self.url,
			{"material_id": material.id, "message": "What is this?"},
			format="json",
		)
		self.assertEqual(response.status_code, 401)

	def test_chat_endpoint_rejects_non_student_non_faculty(self) -> None:
		material = self.create_material(section=self.section_a)
		self.api_client.force_authenticate(user=self.admin_user)

		response = self.api_client.post(
			self.url,
			{"material_id": material.id, "message": "What is this?"},
			format="json",
		)
		self.assertEqual(response.status_code, 403)

	def test_chat_endpoint_returns_503_when_ai_is_unavailable(self) -> None:
		material = self.create_material(section=self.section_a)
		self.api_client.force_authenticate(user=self.student_a_user)

		with patch("study_materials.views.StudyMaterialChatService.ask_question") as mock_ask:
			mock_ask.side_effect = AIServiceUnavailableError()
			response = self.api_client.post(
				self.url,
				{"material_id": material.id, "message": "What is this?"},
				format="json",
			)

		self.assertEqual(response.status_code, 503)

	def test_chat_endpoint_rate_limit_returns_429(self) -> None:
		material = self.create_material(section=self.section_a)
		self.api_client.force_authenticate(user=self.student_a_user)

		rest_framework_settings = dict(settings.REST_FRAMEWORK)
		rest_framework_settings["DEFAULT_THROTTLE_RATES"] = {"ai_chat": "2/hour"}

		with override_settings(REST_FRAMEWORK=rest_framework_settings):
			cache.clear()
			with patch("study_materials.views.StudyMaterialChatService.ask_question") as mock_ask:
				mock_ask.return_value = {"answer": "ok", "sources": []}

				first = self.api_client.post(
					self.url,
					{"material_id": material.id, "message": "Q1"},
					format="json",
				)
				second = self.api_client.post(
					self.url,
					{"material_id": material.id, "message": "Q2"},
					format="json",
				)
				third = self.api_client.post(
					self.url,
					{"material_id": material.id, "message": "Q3"},
					format="json",
				)

		self.assertEqual(first.status_code, 200)
		self.assertEqual(second.status_code, 200)
		self.assertEqual(third.status_code, 429)


class StudyMaterialAIGraphQLTests(StudyMaterialAITestMixin, TestCase):
	"""Integration tests for GraphQL AI tutor mutation."""

	def setUp(self) -> None:
		super().setUp()
		self.client = Client()

	def test_graphql_ask_ai_tutor_success(self) -> None:
		material = self.create_material(section=self.section_a)
		self.client.force_login(self.student_a_user)

		mutation = """
		mutation AskAiTutor($materialId: ID!, $message: String!) {
		  askAiTutor(materialId: $materialId, message: $message) {
			answer
			sources
			error
		  }
		}
		"""

		with patch("study_materials.ai_chat_service.AIClientService") as mock_client_cls:
			mock_client_cls.return_value.query_document.return_value = {
				"answer": "GraphQL answer",
				"sources": ["chunk-1"],
			}

			response = self.client.post(
				"/graphql/",
				data=json.dumps(
					{
						"query": mutation,
						"variables": {
							"materialId": str(material.id),
							"message": "Explain this material",
						},
					}
				),
				content_type="application/json",
			)

		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertNotIn("errors", body)
		payload = body["data"]["askAiTutor"]
		self.assertEqual(payload["answer"], "GraphQL answer")
		self.assertEqual(payload["sources"], ["chunk-1"])
		self.assertIsNone(payload["error"])

	def test_graphql_ask_ai_tutor_returns_error_without_crashing(self) -> None:
		material = self.create_material(section=self.section_a)
		self.client.force_login(self.student_b_user)

		mutation = """
		mutation AskAiTutor($materialId: ID!, $message: String!) {
		  askAiTutor(materialId: $materialId, message: $message) {
			answer
			sources
			error
		  }
		}
		"""

		response = self.client.post(
			"/graphql/",
			data=json.dumps(
				{
					"query": mutation,
					"variables": {
						"materialId": str(material.id),
						"message": "Can I access this?",
					},
				}
			),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertNotIn("errors", body)
		payload = body["data"]["askAiTutor"]
		self.assertEqual(payload["answer"], "")
		self.assertTrue(payload["error"])


class StudyMaterialMutationParityAPITests(StudyMaterialAITestMixin, TestCase):
	"""Integration tests for REST endpoints mirroring GraphQL mutations."""

	def setUp(self) -> None:
		super().setUp()
		self.api_client = APIClient()

	def test_update_material_as_owner_faculty(self) -> None:
		material = self.create_material(status="DRAFT")
		self.api_client.force_authenticate(user=self.faculty_user)

		response = self.api_client.patch(
			f"/api/study-materials/{material.id}/",
			{"title": "Updated Title", "status": "PUBLISHED"},
			format="json",
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.data["success"])
		material.refresh_from_db()
		self.assertEqual(material.title, "Updated Title")
		self.assertEqual(material.status, "PUBLISHED")

	def test_update_material_forbidden_for_non_owner_faculty(self) -> None:
		material = self.create_material()
		other_faculty = self._create_user("other.faculty@example.com", self.faculty_role)
		self.api_client.force_authenticate(user=other_faculty)

		response = self.api_client.patch(
			f"/api/study-materials/{material.id}/",
			{"title": "Forbidden Update"},
			format="json",
		)

		self.assertEqual(response.status_code, 403)

	def test_delete_material_as_admin(self) -> None:
		material = self.create_material()
		self.api_client.force_authenticate(user=self.admin_user)

		response = self.api_client.delete(f"/api/study-materials/{material.id}/")

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.data["success"])
		self.assertFalse(StudyMaterial.objects.filter(id=material.id).exists())

	def test_record_download_student_success(self) -> None:
		material = self.create_material(section=self.section_a)
		self.api_client.force_authenticate(user=self.student_a_user)

		response = self.api_client.post(f"/api/study-materials/{material.id}/record-download/")

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.data["success"])
		material.refresh_from_db()
		self.assertEqual(material.download_count, 1)

	def test_record_view_denied_for_wrong_section(self) -> None:
		material = self.create_material(section=self.section_a)
		self.api_client.force_authenticate(user=self.student_b_user)

		response = self.api_client.post(f"/api/study-materials/{material.id}/record-view/")

		self.assertEqual(response.status_code, 403)

	def test_record_download_denied_for_non_student(self) -> None:
		material = self.create_material(section=self.section_a)
		self.api_client.force_authenticate(user=self.faculty_user)

		response = self.api_client.post(f"/api/study-materials/{material.id}/record-download/")

		self.assertEqual(response.status_code, 403)


class StudyMaterialMyUploadedAPITests(StudyMaterialAITestMixin, TestCase):
	"""Integration tests for faculty-only uploaded materials REST endpoint."""

	def setUp(self) -> None:
		super().setUp()
		self.api_client = APIClient()
		self.url = "/api/study-materials/my-uploaded/"

	def test_my_uploaded_returns_only_authenticated_faculty_materials(self) -> None:
		my_material = self.create_material(status="DRAFT")
		other_faculty = self._create_user("other.faculty@example.com", self.faculty_role)
		StudyMaterial.objects.create(
			subject=self.subject,
			section=self.section_a,
			faculty=other_faculty,
			title="Other Faculty Material",
			description="Should not appear",
			material_type="NOTES",
			file=SimpleUploadedFile("other.pdf", b"%PDF-1.4 other", content_type="application/pdf"),
			status="DRAFT",
		)

		self.api_client.force_authenticate(user=self.faculty_user)
		response = self.api_client.get(self.url)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["count"], 1)
		self.assertEqual(response.data["results"][0]["id"], my_material.id)
		self.assertEqual(response.data["results"][0]["faculty"], self.faculty_user.id)

	def test_my_uploaded_supports_status_filter(self) -> None:
		draft_material = self.create_material(status="DRAFT")
		self.create_material(
			status="ARCHIVED",
			vectorization_status="PENDING",
			vector_document_id="",
		)

		self.api_client.force_authenticate(user=self.faculty_user)
		response = self.api_client.get(self.url, {"status": "draft"})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["count"], 1)
		self.assertEqual(response.data["results"][0]["id"], draft_material.id)
		self.assertEqual(response.data["results"][0]["status"], "DRAFT")

	def test_my_uploaded_rejects_invalid_status_filter(self) -> None:
		self.create_material(status="DRAFT")
		self.api_client.force_authenticate(user=self.faculty_user)

		response = self.api_client.get(self.url, {"status": "invalid-status"})

		self.assertEqual(response.status_code, 400)
		self.assertIn("Invalid status filter", response.data["detail"])

	def test_my_uploaded_denies_student_role(self) -> None:
		self.create_material(status="DRAFT")
		self.api_client.force_authenticate(user=self.student_a_user)

		response = self.api_client.get(self.url)

		self.assertEqual(response.status_code, 403)


class StudyMaterialAvailableForStudentAPITests(StudyMaterialAITestMixin, TestCase):
	"""Integration tests for student available materials REST endpoint."""

	def setUp(self) -> None:
		super().setUp()
		self.api_client = APIClient()
		self.url = "/api/study-materials/available-for-student/"

	def test_available_for_student_returns_only_published_materials_for_student_section(self) -> None:
		published_same_section = self.create_material(
			section=self.section_a,
			status="DRAFT",
		)
		StudyMaterial.objects.filter(id=published_same_section.id).update(status="PUBLISHED")
		self.create_material(
			section=self.section_a,
			status="DRAFT",
			vectorization_status="PENDING",
			vector_document_id="",
		)
		other_section_published = self.create_material(
			section=self.section_b,
			status="DRAFT",
		)
		StudyMaterial.objects.filter(id=other_section_published.id).update(status="PUBLISHED")

		self.api_client.force_authenticate(user=self.student_a_user)
		response = self.api_client.get(self.url)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["count"], 1)
		self.assertEqual(response.data["results"][0]["id"], published_same_section.id)
		self.assertEqual(response.data["results"][0]["section"], self.section_a.id)
		self.assertEqual(response.data["results"][0]["status"], "PUBLISHED")

	def test_available_for_student_supports_material_type_filter(self) -> None:
		notes_material = self.create_material(
			section=self.section_a,
			status="DRAFT",
		)
		StudyMaterial.objects.filter(id=notes_material.id).update(
			status="PUBLISHED",
			material_type="NOTES",
		)
		book_material = self.create_material(
			section=self.section_a,
			status="DRAFT",
		)
		StudyMaterial.objects.filter(id=book_material.id).update(
			status="PUBLISHED",
			material_type="BOOK",
		)

		self.api_client.force_authenticate(user=self.student_a_user)
		response = self.api_client.get(self.url, {"material_type": "notes"})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["count"], 1)
		self.assertEqual(response.data["results"][0]["id"], notes_material.id)
		self.assertEqual(response.data["results"][0]["material_type"], "NOTES")

	def test_available_for_student_rejects_invalid_material_type_filter(self) -> None:
		material = self.create_material(section=self.section_a, status="DRAFT")
		StudyMaterial.objects.filter(id=material.id).update(status="PUBLISHED")
		self.api_client.force_authenticate(user=self.student_a_user)

		response = self.api_client.get(self.url, {"material_type": "INVALID"})

		self.assertEqual(response.status_code, 400)
		self.assertIn("Invalid material_type filter", response.data["detail"])

	def test_available_for_student_denies_non_student(self) -> None:
		material = self.create_material(section=self.section_a, status="DRAFT")
		StudyMaterial.objects.filter(id=material.id).update(status="PUBLISHED")
		self.api_client.force_authenticate(user=self.faculty_user)

		response = self.api_client.get(self.url)

		self.assertEqual(response.status_code, 403)
