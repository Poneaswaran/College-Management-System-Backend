"""Business logic service for AI-powered study material chat."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from study_materials.ai_client_service import (
    AIClientPermanentError,
    AIClientService,
    AIClientTemporaryError,
)
from study_materials.exceptions import AIServiceUnavailableError
from study_materials.models import StudyMaterial
from study_materials.validators import StudyMaterialValidator


logger = logging.getLogger("ai_integration")


class StudyMaterialChatService:
    """Service that validates access and delegates question answering to AI."""

    @staticmethod
    def ask_question(*, user, material_id: int, message: str) -> dict[str, Any]:
        """Answer a user question using the indexed material context.

        Args:
            user: Authenticated Django user instance.
            material_id: Study material id to scope retrieval.
            message: User's non-empty question.

        Returns:
            A dictionary with answer and sources.

        Raises:
            NotFound: If the material does not exist.
            ValidationError: If material is unpublished or not indexed.
            PermissionDenied: If user has no section-level access.
            AIServiceUnavailableError: If upstream AI service is unavailable.
        """
        material = (
            StudyMaterial.objects.select_related("section", "faculty")
            .filter(id=material_id)
            .first()
        )
        if not material:
            raise NotFound("Study material not found.")

        if material.status != "PUBLISHED":
            raise ValidationError("Study material is not published.")

        can_access, error_message = StudyMaterialValidator.validate_material_access(material, user)
        if not can_access:
            logger.warning(
                "ai_access_denied user_id=%s material_id=%s",
                user.id,
                material_id,
            )
            raise PermissionDenied(error_message or "Access denied for this study material.")

        if material.vectorization_status != "INDEXED":
            raise ValidationError(
                "This document is still being processed by AI. Please try again in a few minutes."
            )

        try:
            ai_response = AIClientService().query_document(
                message=message,
                material_id=material.id,
            )
        except AIClientTemporaryError as exc:
            logger.error(
                "ai_query_timeout user_id=%s material_id=%s error=%s",
                user.id,
                material_id,
                str(exc),
            )
            raise AIServiceUnavailableError() from exc
        except AIClientPermanentError as exc:
            logger.error(
                "ai_query_failed user_id=%s material_id=%s error=%s",
                user.id,
                material_id,
                str(exc),
            )
            raise ValidationError("Unable to process AI query for this material.") from exc

        logger.info(
            "ai_query_success user_id=%s material_id=%s",
            user.id,
            material_id,
        )
        return ai_response
