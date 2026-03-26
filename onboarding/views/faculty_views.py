from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import JWTAuthentication
from onboarding.constants import TASK_ENTITY_FACULTY
from onboarding.async_queue import async_task
from onboarding.exceptions import DuplicateUploadException
from onboarding.models import FacultyIDCard, OnboardingTaskLog
from onboarding.serializers.faculty_serializers import (
    FacultyBulkUploadSerializer,
    FacultyIDCardSerializer,
    OnboardingTaskStatusSerializer,
)
from onboarding.services.id_card_service import IDCardService
from onboarding.services.faculty_onboarding_service import FacultyOnboardingService
from onboarding.services.validation_service import ValidationService
from onboarding.tasks import process_faculty_bulk_upload
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


class FacultyBulkUploadView(generics.GenericAPIView):
    serializer_class = FacultyBulkUploadSerializer
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
            result = FacultyOnboardingService.validate_bulk_upload(file_obj)
            return Response(
                {
                    "dry_run": True,
                    "message": "Validation completed",
                    **result,
                },
                status=status.HTTP_200_OK,
            )

        idempotency_key = f"{TASK_ENTITY_FACULTY}:{file_hash}"

        try:
            with transaction.atomic():
                task_log = OnboardingTaskLog.objects.create(
                    entity_type=TASK_ENTITY_FACULTY,
                    uploaded_by=request.user,
                    file=file_obj,
                    file_hash=file_hash,
                    idempotency_key=idempotency_key,
                    dry_run=False,
                )
        except IntegrityError:
            raise DuplicateUploadException()

        task_id = async_task(process_faculty_bulk_upload, task_log.id, hook="onboarding.tasks.onboarding_task_hook")
        task_log.task_id = str(task_id)
        task_log.save(update_fields=["task_id", "updated_at"])

        return Response(
            {
                "task_id": task_log.task_id,
                "status": task_log.status,
                "message": "Faculty bulk upload queued",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class FacultyBulkUploadStatusView(ETagMixin, generics.RetrieveAPIView):
    serializer_class = OnboardingTaskStatusSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    lookup_field = "task_id"

    def get_queryset(self):
        return OnboardingTaskLog.objects.filter(entity_type=TASK_ENTITY_FACULTY)


class FacultyMyIDCardView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not hasattr(request.user, "faculty_profile"):
            return Response({"detail": "Faculty profile not found"}, status=status.HTTP_404_NOT_FOUND)

        card = FacultyIDCard.objects.select_related("faculty_profile").filter(
            faculty_profile=request.user.faculty_profile
        ).first()

        if not card:
            return Response({"detail": "ID card not generated"}, status=status.HTTP_404_NOT_FOUND)

        return Response(FacultyIDCardSerializer(card).data)


class FacultyGenerateIDCardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, id, *args, **kwargs):
        from profile_management.models import FacultyProfile

        faculty_profile = get_object_or_404(
            FacultyProfile.objects.select_related("department", "user"),
            id=id,
        )
        card = IDCardService.generate_faculty_id_card(faculty_profile, request.user)
        IDCardService.issue_card(card)
        return Response(FacultyIDCardSerializer(card).data, status=status.HTTP_200_OK)


class FacultyRevokeIDCardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, id, *args, **kwargs):
        from profile_management.models import FacultyProfile

        faculty_profile = get_object_or_404(FacultyProfile, id=id)
        card = IDCardService.revoke_faculty_id_card(faculty_profile)
        if not card:
            return Response({"detail": "ID card not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacultyIDCardSerializer(card).data, status=status.HTTP_200_OK)
