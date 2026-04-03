import uuid

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import JWTAuthentication
from onboarding.async_queue import async_task
from onboarding.constants import TASK_ENTITY_FACULTY, TASK_ENTITY_STUDENT
from onboarding.models import OnboardingDraft, OnboardingTaskLog, StudentOnboardingApproval, TemporaryOnboardingAccess
from onboarding.permissions import IsAdminRole
from onboarding.serializers.admin_serializers import (
    FacultyManualOnboardingSerializer,
    OnboardingDraftCreateSerializer,
    OnboardingDraftSerializer,
    OnboardingDraftUpdateSerializer,
    StudentApprovalActionSerializer,
    StudentManualOnboardingSerializer,
    StudentOnboardingApprovalSerializer,
    TemporaryAccessGrantSerializer,
    TemporaryAccessRevokeSerializer,
)
from onboarding.services.access_service import TemporaryAccessService
from onboarding.services.approval_service import StudentApprovalService
from onboarding.services.audit_service import OnboardingAuditService
from onboarding.services.faculty_onboarding_service import FacultyOnboardingService
from onboarding.services.student_onboarding_service import StudentOnboardingService
from onboarding.tasks import (
    process_faculty_retry_bulk_upload,
    process_student_retry_bulk_upload,
)


class RetryFailedOnboardingTaskView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, task_id, *args, **kwargs):
        source_task = get_object_or_404(OnboardingTaskLog, task_id=task_id)

        is_admin = IsAdminRole().has_permission(request, self)
        if not is_admin:
            role_code = getattr(getattr(request.user, "role", None), "code", None)
            if role_code not in {"FACULTY", "HOD"}:
                return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

            grant = TemporaryOnboardingAccess.objects.filter(
                faculty_user=request.user,
                is_active=True,
                can_retry=True,
                expires_at__gt=timezone.now(),
            ).order_by("-created_at").first()

            if not grant:
                return Response({"detail": "Temporary onboarding access has expired or is not granted"}, status=status.HTTP_403_FORBIDDEN)

            if grant.scope not in {source_task.entity_type, TemporaryOnboardingAccess.SCOPE_ALL}:
                return Response({"detail": "Access scope does not permit retry for this entity"}, status=status.HTTP_403_FORBIDDEN)

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

        OnboardingAuditService.log(
            action="ONBOARDING_RETRY_QUEUED",
            entity_type=source_task.entity_type,
            entity_id=retry_task.task_id,
            actor=request.user,
            metadata={"source_task_id": source_task.task_id, "retry_rows": len(failed_rows)},
        )

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


class GrantTemporaryOnboardingAccessView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, *args, **kwargs):
        serializer = TemporaryAccessGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            access = TemporaryAccessService.grant(
                faculty_user_id=serializer.validated_data["faculty_user_id"],
                granted_by=request.user,
                scope=serializer.validated_data["scope"],
                expires_at=serializer.validated_data["expires_at"],
                can_bulk_upload=serializer.validated_data["can_bulk_upload"],
                can_retry=serializer.validated_data["can_retry"],
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "access_id": access.id,
                "faculty_user_id": access.faculty_user_id,
                "scope": access.scope,
                "expires_at": access.expires_at,
                "can_bulk_upload": access.can_bulk_upload,
                "can_retry": access.can_retry,
                "is_active": access.is_active,
            },
            status=status.HTTP_201_CREATED,
        )


class RevokeTemporaryOnboardingAccessView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, *args, **kwargs):
        serializer = TemporaryAccessRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            access = TemporaryAccessService.revoke(
                access_id=serializer.validated_data["access_id"],
                revoked_by=request.user,
            )
        except TemporaryOnboardingAccess.DoesNotExist:
            return Response({"detail": "Access record not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"access_id": access.id, "is_active": access.is_active}, status=status.HTTP_200_OK)


class PendingStudentApprovalsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request, *args, **kwargs):
        pending = StudentOnboardingApproval.objects.select_related("student_profile").filter(status="PENDING")
        return Response(StudentOnboardingApprovalSerializer(pending, many=True).data)


class ApproveStudentOnboardingView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, student_id, *args, **kwargs):
        serializer = StudentApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from profile_management.models import StudentProfile

        student_profile = get_object_or_404(StudentProfile.objects.select_related("user"), id=student_id)
        approval = StudentApprovalService.approve(
            student_profile=student_profile,
            approved_by=request.user,
            remarks=serializer.validated_data.get("remarks", ""),
        )
        return Response(StudentOnboardingApprovalSerializer(approval).data, status=status.HTTP_200_OK)


class RejectStudentOnboardingView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, student_id, *args, **kwargs):
        serializer = StudentApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from profile_management.models import StudentProfile

        student_profile = get_object_or_404(StudentProfile.objects.select_related("user"), id=student_id)
        approval = StudentApprovalService.reject(
            student_profile=student_profile,
            rejected_by=request.user,
            remarks=serializer.validated_data.get("remarks", ""),
        )
        return Response(StudentOnboardingApprovalSerializer(approval).data, status=status.HTTP_200_OK)


class StudentManualOnboardingView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, *args, **kwargs):
        serializer = StudentManualOnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = StudentOnboardingService.onboard_single(
                row_data=serializer.validated_data,
                actor=request.user,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        OnboardingAuditService.log(
            action="STUDENT_MANUAL_ONBOARDED",
            entity_type=TASK_ENTITY_STUDENT,
            entity_id=profile.id if profile else "",
            actor=request.user,
            metadata={"registration_number": serializer.validated_data.get("registration_number")},
        )

        return Response(
            {
                "message": "Student onboarded and marked pending admin approval",
                "student_id": profile.id if profile else None,
                "registration_number": serializer.validated_data.get("registration_number"),
            },
            status=status.HTTP_201_CREATED,
        )


class FacultyManualOnboardingView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, *args, **kwargs):
        serializer = FacultyManualOnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = dict(serializer.validated_data)
        subject_codes = payload.get("subject_codes", [])
        if isinstance(subject_codes, list):
            payload["subject_codes"] = ",".join(subject_codes)

        try:
            profile = FacultyOnboardingService.onboard_single(
                row_data=payload,
                actor=request.user,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        OnboardingAuditService.log(
            action="FACULTY_MANUAL_ONBOARDED",
            entity_type=TASK_ENTITY_FACULTY,
            entity_id=profile.id if profile else "",
            actor=request.user,
            metadata={"employee_id": serializer.validated_data.get("employee_id")},
        )

        return Response(
            {
                "message": "Faculty onboarded successfully",
                "faculty_id": profile.id if profile else None,
                "employee_id": serializer.validated_data.get("employee_id"),
            },
            status=status.HTTP_201_CREATED,
        )


class OnboardingDraftListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request, *args, **kwargs):
        qs = OnboardingDraft.objects.select_related("created_by", "updated_by", "submitted_by").all()
        entity_type = request.query_params.get("entity_type")
        status_filter = request.query_params.get("status")
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(OnboardingDraftSerializer(qs, many=True).data)

    def post(self, request, *args, **kwargs):
        serializer = OnboardingDraftCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        draft = OnboardingDraft.objects.create(
            entity_type=serializer.validated_data["entity_type"],
            payload=serializer.validated_data.get("payload", {}),
            status=OnboardingDraft.STATUS_DRAFT,
            created_by=request.user,
            updated_by=request.user,
        )

        OnboardingAuditService.log(
            action="ONBOARDING_DRAFT_CREATED",
            entity_type=draft.entity_type,
            entity_id=draft.id,
            actor=request.user,
            metadata={"status": draft.status},
        )
        return Response(OnboardingDraftSerializer(draft).data, status=status.HTTP_201_CREATED)


class OnboardingDraftDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request, draft_id, *args, **kwargs):
        draft = get_object_or_404(OnboardingDraft, id=draft_id)
        return Response(OnboardingDraftSerializer(draft).data)

    def patch(self, request, draft_id, *args, **kwargs):
        draft = get_object_or_404(OnboardingDraft, id=draft_id)
        serializer = OnboardingDraftUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if "payload" in serializer.validated_data:
            draft.payload = serializer.validated_data["payload"]
        draft.updated_by = request.user
        draft.save(update_fields=["payload", "updated_by", "updated_at"])

        OnboardingAuditService.log(
            action="ONBOARDING_DRAFT_UPDATED",
            entity_type=draft.entity_type,
            entity_id=draft.id,
            actor=request.user,
            metadata={"status": draft.status},
        )
        return Response(OnboardingDraftSerializer(draft).data)


class SubmitOnboardingDraftView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, draft_id, *args, **kwargs):
        draft = get_object_or_404(OnboardingDraft, id=draft_id)
        payload = dict(draft.payload or {})

        try:
            if draft.entity_type == TASK_ENTITY_STUDENT:
                profile = StudentOnboardingService.onboard_single(row_data=payload, actor=request.user)
                result_id = profile.id if profile else None
            elif draft.entity_type == TASK_ENTITY_FACULTY:
                subject_codes = payload.get("subject_codes", [])
                if isinstance(subject_codes, list):
                    payload["subject_codes"] = ",".join(subject_codes)
                profile = FacultyOnboardingService.onboard_single(row_data=payload, actor=request.user)
                result_id = profile.id if profile else None
            else:
                return Response({"detail": "Unsupported draft entity type"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        draft.status = OnboardingDraft.STATUS_SUBMITTED
        draft.submitted_by = request.user
        draft.submitted_at = timezone.now()
        draft.updated_by = request.user
        draft.save(update_fields=["status", "submitted_by", "submitted_at", "updated_by", "updated_at"])

        OnboardingAuditService.log(
            action="ONBOARDING_DRAFT_SUBMITTED",
            entity_type=draft.entity_type,
            entity_id=draft.id,
            actor=request.user,
            metadata={"result_entity_id": result_id},
        )

        return Response(
            {
                "message": "Draft submitted successfully",
                "draft_id": draft.id,
                "status": draft.status,
                "result_entity_id": result_id,
            },
            status=status.HTTP_200_OK,
        )
