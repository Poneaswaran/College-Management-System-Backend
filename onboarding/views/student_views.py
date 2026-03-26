from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import JWTAuthentication
from onboarding.constants import TASK_ENTITY_STUDENT
from onboarding.async_queue import async_task
from onboarding.exceptions import DuplicateUploadException
from onboarding.models import OnboardingTaskLog, StudentIDCard
from onboarding.serializers.student_serializers import (
    OnboardingTaskStatusSerializer,
    StudentBulkUploadSerializer,
    StudentIDCardSerializer,
)
from onboarding.services.id_card_service import IDCardService
from onboarding.services.student_onboarding_service import StudentOnboardingService
from onboarding.services.validation_service import ValidationService
from onboarding.tasks import process_student_bulk_upload
from onboarding.utils.file_parser import compute_file_hash
from onboarding.views.etag_mixin import ETagMixin


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return hasattr(user, "role") and user.role and user.role.code in ["ADMIN", "SUPER_ADMIN"]


class StudentBulkUploadView(generics.GenericAPIView):
    serializer_class = StudentBulkUploadSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = serializer.validated_data["file"]
        ValidationService.validate_upload_file_meta(file_obj)

        file_hash = compute_file_hash(file_obj)
        dry_run = str(request.query_params.get("dry_run", "false")).lower() in {"1", "true", "yes"}

        if dry_run:
            result = StudentOnboardingService.validate_bulk_upload(file_obj)
            return Response(
                {
                    "dry_run": True,
                    "message": "Validation completed",
                    **result,
                },
                status=status.HTTP_200_OK,
            )

        idempotency_key = f"{TASK_ENTITY_STUDENT}:{file_hash}"

        try:
            with transaction.atomic():
                task_log = OnboardingTaskLog.objects.create(
                    entity_type=TASK_ENTITY_STUDENT,
                    uploaded_by=request.user,
                    file=file_obj,
                    file_hash=file_hash,
                    idempotency_key=idempotency_key,
                    dry_run=False,
                )
        except IntegrityError:
            raise DuplicateUploadException()

        task_id = async_task(process_student_bulk_upload, task_log.id, hook="onboarding.tasks.onboarding_task_hook")
        task_log.task_id = str(task_id)
        task_log.save(update_fields=["task_id", "updated_at"])

        return Response(
            {
                "task_id": task_log.task_id,
                "status": task_log.status,
                "message": "Student bulk upload queued",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class StudentBulkUploadStatusView(ETagMixin, generics.RetrieveAPIView):
    serializer_class = OnboardingTaskStatusSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    lookup_field = "task_id"

    def get_queryset(self):
        return OnboardingTaskLog.objects.filter(entity_type=TASK_ENTITY_STUDENT)


class StudentMyIDCardView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not hasattr(request.user, "student_profile"):
            return Response({"detail": "Student profile not found"}, status=status.HTTP_404_NOT_FOUND)

        card = StudentIDCard.objects.select_related("student_profile").filter(
            student_profile=request.user.student_profile
        ).first()

        if not card:
            return Response({"detail": "ID card not generated"}, status=status.HTTP_404_NOT_FOUND)

        return Response(StudentIDCardSerializer(card).data)


class StudentGenerateIDCardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, id, *args, **kwargs):
        from profile_management.models import StudentProfile

        student_profile = get_object_or_404(
            StudentProfile.objects.select_related("department", "user"),
            id=id,
        )
        card = IDCardService.generate_student_id_card(student_profile, request.user)
        IDCardService.issue_card(card)
        return Response(StudentIDCardSerializer(card).data, status=status.HTTP_200_OK)


class StudentRevokeIDCardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, id, *args, **kwargs):
        from profile_management.models import StudentProfile

        student_profile = get_object_or_404(StudentProfile, id=id)
        card = IDCardService.revoke_student_id_card(student_profile)
        if not card:
            return Response({"detail": "ID card not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudentIDCardSerializer(card).data, status=status.HTTP_200_OK)
