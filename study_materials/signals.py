"""Signal handlers for study material AI indexing lifecycle."""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from study_materials.models import StudyMaterial
from study_materials.tasks import enqueue_ingestion_task, enqueue_vector_deletion_task


logger = logging.getLogger("ai_integration")


@receiver(pre_save, sender=StudyMaterial)
def capture_study_material_previous_state(sender, instance: StudyMaterial, **kwargs) -> None:
    """Capture previous material state to detect file/status transitions."""
    if not instance.pk:
        return

    previous_instance = (
        StudyMaterial.objects.filter(pk=instance.pk)
        .only("file", "status", "vector_document_id")
        .first()
    )
    if not previous_instance:
        return

    instance._previous_file_name = previous_instance.file.name if previous_instance.file else ""
    instance._previous_status = previous_instance.status
    instance._previous_vector_document_id = previous_instance.vector_document_id


@receiver(post_save, sender=StudyMaterial)
def schedule_study_material_vector_sync(
    sender,
    instance: StudyMaterial,
    created: bool,
    **kwargs,
) -> None:
    """Trigger asynchronous ingestion/deletion based on material lifecycle changes."""
    previous_file_name = getattr(instance, "_previous_file_name", "")
    previous_status = getattr(instance, "_previous_status", None)
    previous_vector_document_id = getattr(instance, "_previous_vector_document_id", "")

    current_file_name = instance.file.name if instance.file else ""
    file_changed = bool(previous_status is not None and previous_file_name != current_file_name)

    became_published = previous_status != "PUBLISHED" and instance.status == "PUBLISHED"
    became_archived = previous_status != "ARCHIVED" and instance.status == "ARCHIVED"

    if became_archived:
        vector_document_id = previous_vector_document_id or instance.vector_document_id
        if vector_document_id:
            enqueue_vector_deletion_task(
                vector_document_id=vector_document_id,
                material_id=instance.id,
            )
        StudyMaterial.objects.filter(id=instance.id).update(
            vectorization_status="PENDING",
            vector_document_id="",
            last_indexed_at=None,
            vector_error_message="",
        )
        return

    should_ingest = (created and instance.status == "PUBLISHED") or file_changed or became_published
    if not should_ingest:
        return

    if file_changed and previous_vector_document_id:
        enqueue_vector_deletion_task(
            vector_document_id=previous_vector_document_id,
            material_id=instance.id,
        )

    StudyMaterial.objects.filter(id=instance.id).update(
        vectorization_status="PENDING",
        vector_document_id="",
        last_indexed_at=None,
        vector_error_message="",
    )
    enqueue_ingestion_task(instance.id)

    logger.info(
        "ai_ingestion_enqueued material_id=%s reason=%s",
        instance.id,
        "created_published" if created else "state_changed",
    )


@receiver(post_delete, sender=StudyMaterial)
def schedule_vector_cleanup_on_material_delete(
    sender,
    instance: StudyMaterial,
    **kwargs,
) -> None:
    """Ensure vector documents are removed when material is deleted."""
    if not instance.vector_document_id:
        return

    enqueue_vector_deletion_task(
        vector_document_id=instance.vector_document_id,
        material_id=instance.id,
    )
