from django.urls import path
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import JWTAuthentication
from onboarding.services.id_card_service import IDCardService
from onboarding.views.admin_views import (
    ApproveFacultyOnboardingView,
    ApproveStudentOnboardingView,
    BulkApproveFacultyOnboardingView,
    BulkApproveStudentOnboardingView,
    BulkRejectFacultyOnboardingView,
    BulkRejectStudentOnboardingView,
    FacultyManualOnboardingView,
    GrantTemporaryOnboardingAccessView,
    OnboardingDraftDetailView,
    OnboardingDraftListCreateView,
    PendingFacultyApprovalsView,
    PendingStudentApprovalsView,
    RejectFacultyOnboardingView,
    RejectStudentOnboardingView,
    RetryFailedOnboardingTaskView,
    RevokeTemporaryOnboardingAccessView,
    StudentManualOnboardingView,
    SubmitOnboardingDraftView,
)
from onboarding.views.faculty_views import (
    FacultyBulkUploadStatusView,
    FacultyBulkUploadView,
    FacultyGenerateIDCardView,
    FacultyMyIDCardView,
    FacultyRevokeIDCardView,
)
from onboarding.views.student_views import (
    StudentBulkUploadStatusView,
    StudentBulkUploadView,
    StudentGenerateIDCardView,
    StudentMyIDCardView,
    StudentRevokeIDCardView,
)


class QRVerifyView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        token = request.data.get("token")
        if not token:
            return Response({"detail": "token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = IDCardService.verify_qr_token(token)
            return Response(result, status=status.HTTP_200_OK if result.get("is_valid") else status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"is_valid": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


urlpatterns = [
    path("admin/students/bulk-upload/", StudentBulkUploadView.as_view(), name="student_bulk_upload"),
    path(
        "admin/students/bulk-upload/<str:task_id>/status/",
        StudentBulkUploadStatusView.as_view(),
        name="student_bulk_upload_status",
    ),
    path("students/me/id-card/", StudentMyIDCardView.as_view(), name="student_my_id_card"),
    path("admin/students/<int:id>/generate-id-card/", StudentGenerateIDCardView.as_view(), name="student_generate_id_card"),
    path("admin/students/<int:id>/revoke-id-card/", StudentRevokeIDCardView.as_view(), name="student_revoke_id_card"),

    path("admin/faculty/bulk-upload/", FacultyBulkUploadView.as_view(), name="faculty_bulk_upload"),
    path(
        "admin/faculty/bulk-upload/<str:task_id>/status/",
        FacultyBulkUploadStatusView.as_view(),
        name="faculty_bulk_upload_status",
    ),
    path("faculty/me/id-card/", FacultyMyIDCardView.as_view(), name="faculty_my_id_card"),
    path("admin/faculty/<int:id>/generate-id-card/", FacultyGenerateIDCardView.as_view(), name="faculty_generate_id_card"),
    path("admin/faculty/<int:id>/revoke-id-card/", FacultyRevokeIDCardView.as_view(), name="faculty_revoke_id_card"),

    path("qr/verify/", QRVerifyView.as_view(), name="qr_verify"),
    path(
        "admin/onboarding/retry-failed/<str:task_id>/",
        RetryFailedOnboardingTaskView.as_view(),
        name="onboarding_retry_failed",
    ),
    path(
        "admin/onboarding/access/grant/",
        GrantTemporaryOnboardingAccessView.as_view(),
        name="onboarding_access_grant",
    ),
    path(
        "admin/onboarding/access/revoke/",
        RevokeTemporaryOnboardingAccessView.as_view(),
        name="onboarding_access_revoke",
    ),
    path(
        "admin/students/pending-approvals/",
        PendingStudentApprovalsView.as_view(),
        name="student_pending_approvals",
    ),
    path(
        "admin/students/<int:student_id>/approve/",
        ApproveStudentOnboardingView.as_view(),
        name="student_approve_onboarding",
    ),
    path(
        "admin/students/<int:student_id>/reject/",
        RejectStudentOnboardingView.as_view(),
        name="student_reject_onboarding",
    ),
    path(
        "admin/students/bulk-approve/",
        BulkApproveStudentOnboardingView.as_view(),
        name="student_bulk_approve_onboarding",
    ),
    path(
        "admin/students/bulk-reject/",
        BulkRejectStudentOnboardingView.as_view(),
        name="student_bulk_reject_onboarding",
    ),
    path(
        "admin/faculty/pending-approvals/",
        PendingFacultyApprovalsView.as_view(),
        name="faculty_pending_approvals",
    ),
    path(
        "admin/faculty/<int:faculty_id>/approve/",
        ApproveFacultyOnboardingView.as_view(),
        name="faculty_approve_onboarding",
    ),
    path(
        "admin/faculty/<int:faculty_id>/reject/",
        RejectFacultyOnboardingView.as_view(),
        name="faculty_reject_onboarding",
    ),
    path(
        "admin/faculty/bulk-approve/",
        BulkApproveFacultyOnboardingView.as_view(),
        name="faculty_bulk_approve_onboarding",
    ),
    path(
        "admin/faculty/bulk-reject/",
        BulkRejectFacultyOnboardingView.as_view(),
        name="faculty_bulk_reject_onboarding",
    ),
    path(
        "admin/students/manual/",
        StudentManualOnboardingView.as_view(),
        name="student_manual_onboarding",
    ),
    path(
        "admin/faculty/manual/",
        FacultyManualOnboardingView.as_view(),
        name="faculty_manual_onboarding",
    ),
    path(
        "admin/onboarding/drafts/",
        OnboardingDraftListCreateView.as_view(),
        name="onboarding_draft_list_create",
    ),
    path(
        "admin/onboarding/drafts/<int:draft_id>/",
        OnboardingDraftDetailView.as_view(),
        name="onboarding_draft_detail",
    ),
    path(
        "admin/onboarding/drafts/<int:draft_id>/submit/",
        SubmitOnboardingDraftView.as_view(),
        name="onboarding_draft_submit",
    ),
]
