from django.db import transaction
from django.utils import timezone

from onboarding.models import StudentOnboardingApproval
from onboarding.services.audit_service import OnboardingAuditService


class StudentApprovalService:
    @staticmethod
    @transaction.atomic
    def ensure_pending(student_profile, requested_by=None, remarks=""):
        approval, _ = StudentOnboardingApproval.objects.get_or_create(
            student_profile=student_profile,
            defaults={
                "status": StudentOnboardingApproval.STATUS_PENDING,
                "requested_by": requested_by,
                "remarks": remarks,
            },
        )

        approval.status = StudentOnboardingApproval.STATUS_PENDING
        approval.requested_by = requested_by
        approval.approved_by = None
        approval.approved_at = None
        approval.rejected_at = None
        approval.remarks = remarks or approval.remarks
        approval.save()

        student_profile.is_active = False
        student_profile.academic_status = "INACTIVE"
        student_profile.save(update_fields=["is_active", "academic_status", "updated_at"])

        user = student_profile.user
        user.is_active = False
        user.save(update_fields=["is_active"])

        OnboardingAuditService.log(
            action="STUDENT_APPROVAL_PENDING",
            entity_type="STUDENT",
            entity_id=student_profile.id,
            actor=requested_by,
            metadata={"register_number": student_profile.register_number},
        )
        return approval

    @staticmethod
    @transaction.atomic
    def approve(student_profile, approved_by, remarks=""):
        approval, _ = StudentOnboardingApproval.objects.get_or_create(student_profile=student_profile)
        approval.status = StudentOnboardingApproval.STATUS_APPROVED
        approval.approved_by = approved_by
        approval.approved_at = timezone.now()
        approval.rejected_at = None
        approval.remarks = remarks
        approval.save()

        student_profile.is_active = True
        student_profile.academic_status = "ACTIVE"
        student_profile.save(update_fields=["is_active", "academic_status", "updated_at"])

        user = student_profile.user
        user.is_active = True
        user.save(update_fields=["is_active"])

        OnboardingAuditService.log(
            action="STUDENT_APPROVED",
            entity_type="STUDENT",
            entity_id=student_profile.id,
            actor=approved_by,
            metadata={"register_number": student_profile.register_number, "remarks": remarks},
        )
        return approval

    @staticmethod
    @transaction.atomic
    def reject(student_profile, rejected_by, remarks=""):
        approval, _ = StudentOnboardingApproval.objects.get_or_create(student_profile=student_profile)
        approval.status = StudentOnboardingApproval.STATUS_REJECTED
        approval.approved_by = rejected_by
        approval.rejected_at = timezone.now()
        approval.approved_at = None
        approval.remarks = remarks
        approval.save()

        student_profile.is_active = False
        student_profile.academic_status = "INACTIVE"
        student_profile.save(update_fields=["is_active", "academic_status", "updated_at"])

        user = student_profile.user
        user.is_active = False
        user.save(update_fields=["is_active"])

        OnboardingAuditService.log(
            action="STUDENT_REJECTED",
            entity_type="STUDENT",
            entity_id=student_profile.id,
            actor=rejected_by,
            metadata={"register_number": student_profile.register_number, "remarks": remarks},
        )
        return approval
