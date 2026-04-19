"""Asynchronous task handlers for AI document ingestion and cleanup."""

from __future__ import annotations

import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from onboarding.async_queue import async_task
from study_materials.ai_client_service import (
    AIClientPermanentError,
    AIClientService,
    AIClientTemporaryError,
)
from study_materials.models import StudyMaterial

import logging


logger = logging.getLogger("ai_integration")


def enqueue_ingestion_task(material_id: int) -> str | None:
    """Schedule ingestion task asynchronously.

    Args:
        material_id: Target study material id.

    Returns:
        Background task id when available.
    """
    return async_task("study_materials.tasks.ingest_study_material_task", material_id)


def enqueue_vector_deletion_task(
    *,
    vector_document_id: str,
    material_id: int | None = None,
) -> str | None:
    """Schedule vector deletion task asynchronously.

    Args:
        vector_document_id: External vector document id.
        material_id: Optional local material id for logging.

    Returns:
        Background task id when available.
    """
    if not vector_document_id:
        return None
    return async_task(
        "study_materials.tasks.delete_material_vector_task",
        vector_document_id,
        material_id,
    )


def ingest_study_material_task(material_id: int) -> None:
    """Send study material file to AI ingestion endpoint with retries.

    Args:
        material_id: StudyMaterial primary key.
    """
    logger.info("ai_ingestion_started material_id=%s", material_id)

    material = (
        StudyMaterial.objects.select_related("subject", "section", "faculty")
        .filter(id=material_id)
        .first()
    )
    if not material:
        logger.warning("ai_ingestion_skipped material_id=%s reason=material_not_found", material_id)
        return

    if not material.file:
        _mark_failed(material_id, "Study material file is missing.")
        return

    if not material.file.storage.exists(material.file.name):
        _mark_failed(material_id, "Study material file is not accessible in storage.")
        return

    _update_vector_state(
        material_id=material_id,
        vectorization_status="PROCESSING",
        vector_document_id="",
        vector_error_message="",
    )

    max_attempts = max(int(getattr(settings, "AI_INGEST_MAX_RETRIES", 3)), 1)
    backoff_seconds = max(int(getattr(settings, "AI_INGEST_BACKOFF_SECONDS", 2)), 1)
    client = AIClientService()

    for attempt in range(1, max_attempts + 1):
        try:
            with material.file.open("rb") as file_obj:
                file_bytes = file_obj.read()

            response = client.ingest_document(
                file_name=Path(material.file.name).name,
                file_bytes=file_bytes,
                metadata={
                    "material_id": material.id,
                    "subject_id": material.subject_id,
                    "section_id": material.section_id,
                    "faculty_id": material.faculty_id,
                },
            )

            _update_vector_state(
                material_id=material_id,
                vectorization_status="INDEXED",
                vector_document_id=response.document_id,
                last_indexed_at=timezone.now(),
                vector_error_message="",
            )
            logger.info(
                "ai_ingestion_completed material_id=%s vector_document_id=%s",
                material_id,
                response.document_id,
            )
            return

        except AIClientTemporaryError as exc:
            if attempt >= max_attempts:
                _mark_failed(material_id, str(exc))
                return
            sleep_seconds = backoff_seconds * (2 ** (attempt - 1))
            time.sleep(sleep_seconds)

        except AIClientPermanentError as exc:
            _mark_failed(material_id, str(exc))
            return

        except Exception as exc:  # pragma: no cover - safety net for unknown failures
            _mark_failed(material_id, str(exc))
            return


def delete_material_vector_task(vector_document_id: str, material_id: int | None = None) -> None:
    """Delete a vector document from the AI service.

    Args:
        vector_document_id: External vector document id.
        material_id: Optional local StudyMaterial id for logs.
    """
    if not vector_document_id:
        return

    try:
        AIClientService().delete_document_vectors(vector_document_id=vector_document_id)
        logger.info(
            "ai_vector_delete_completed material_id=%s vector_document_id=%s",
            material_id,
            vector_document_id,
        )
    except AIClientTemporaryError as exc:
        logger.warning(
            "ai_vector_delete_temporary_failure material_id=%s vector_document_id=%s error=%s",
            material_id,
            vector_document_id,
            str(exc),
        )
    except AIClientPermanentError as exc:
        logger.warning(
            "ai_vector_delete_permanent_failure material_id=%s vector_document_id=%s error=%s",
            material_id,
            vector_document_id,
            str(exc),
        )


def _mark_failed(material_id: int, error_message: str) -> None:
    """Persist terminal failure state for ingestion workflow."""
    truncated_error = (error_message or "Unknown ingestion error")[:2000]
    _update_vector_state(
        material_id=material_id,
        vectorization_status="FAILED",
        vector_error_message=truncated_error,
    )
    logger.error("ai_ingestion_failed material_id=%s error=%s", material_id, truncated_error)


def _update_vector_state(
    *,
    material_id: int,
    vectorization_status: str,
    vector_document_id: str | None = None,
    last_indexed_at=None,
    vector_error_message: str | None = None,
) -> None:
    """Apply vector state updates in a single database query."""
    updates: dict[str, object] = {
        "vectorization_status": vectorization_status,
    }
    if vector_document_id is not None:
        updates["vector_document_id"] = vector_document_id
    if last_indexed_at is not None:
        updates["last_indexed_at"] = last_indexed_at
    if vector_error_message is not None:
        updates["vector_error_message"] = vector_error_message

    StudyMaterial.objects.filter(id=material_id).update(**updates)
