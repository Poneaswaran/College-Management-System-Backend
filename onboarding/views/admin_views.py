import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import JWTAuthentication
from onboarding.async_queue import async_task
from onboarding.constants import TASK_ENTITY_FACULTY, TASK_ENTITY_STUDENT
from onboarding.models import OnboardingTaskLog
from onboarding.tasks import (
    process_faculty_retry_bulk_upload,
    process_student_retry_bulk_upload,
)


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return hasattr(user, "role") and user.role and user.role.code in ["ADMIN", "SUPER_ADMIN"]


class RetryFailedOnboardingTaskView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, task_id, *args, **kwargs):
        source_task = get_object_or_404(OnboardingTaskLog, task_id=task_id)
        failed_rows = []
        for item in source_task.error_log or []:
            row_data = item.get("row_data")
            if row_data:
                failed_rows.append(row_data)

        if not failed_rows:
            return Response(
                {"detail": "No failed rows available for retry"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        retry_key = f"{source_task.entity_type}:{source_task.file_hash}:retry:{uuid.uuid4().hex}"

        with transaction.atomic():
            retry_task = OnboardingTaskLog.objects.create(
                entity_type=source_task.entity_type,
                uploaded_by=request.user,
                file=source_task.file,
                file_hash=source_task.file_hash,
                idempotency_key=retry_key,
                source_task=source_task,
                is_retry=True,
                retry_attempt=(source_task.retry_attempt + 1),
                dry_run=False,
            )

        if source_task.entity_type == TASK_ENTITY_STUDENT:
            q_task_id = async_task(
                process_student_retry_bulk_upload,
                retry_task.id,
                failed_rows,
                hook="onboarding.tasks.onboarding_task_hook",
            )
        elif source_task.entity_type == TASK_ENTITY_FACULTY:
            q_task_id = async_task(
                process_faculty_retry_bulk_upload,
                retry_task.id,
                failed_rows,
                hook="onboarding.tasks.onboarding_task_hook",
            )
        else:
            return Response(
                {"detail": "Unsupported entity type for retry"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        retry_task.task_id = str(q_task_id)
        retry_task.save(update_fields=["task_id", "updated_at"])

        return Response(
            {
                "message": "Retry task queued",
                "task_id": retry_task.task_id,
                "source_task_id": source_task.task_id,
                "retry_attempt": retry_task.retry_attempt,
                "retry_rows": len(failed_rows),
            },
            status=status.HTTP_202_ACCEPTED,
        )
