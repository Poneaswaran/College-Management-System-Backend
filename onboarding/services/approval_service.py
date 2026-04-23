from django.db import transaction
from django.utils import timezone

from onboarding.models import StudentOnboardingApproval, FacultyOnboardingApproval
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

    @staticmethod
    @transaction.atomic
    def bulk_approve(student_ids, approved_by, remarks=""):
        from profile_management.models import StudentProfile
        profiles = StudentProfile.objects.select_related("user").filter(id__in=student_ids)
        results = []
        for profile in profiles:
            results.append(StudentApprovalService.approve(profile, approved_by, remarks))
        return results

    @staticmethod
    @transaction.atomic
    def bulk_reject(student_ids, rejected_by, remarks=""):
        from profile_management.models import StudentProfile
        profiles = StudentProfile.objects.select_related("user").filter(id__in=student_ids)
        results = []
        for profile in profiles:
            results.append(StudentApprovalService.reject(profile, rejected_by, remarks))
        return results


class FacultyApprovalService:
    @staticmethod
    @transaction.atomic
    def ensure_pending(faculty_profile, requested_by=None, remarks=""):
        approval, _ = FacultyOnboardingApproval.objects.get_or_create(
            faculty_profile=faculty_profile,
            defaults={
                "status": FacultyOnboardingApproval.STATUS_PENDING,
                "requested_by": requested_by,
                "remarks": remarks,
            },
        )

        approval.status = FacultyOnboardingApproval.STATUS_PENDING
        approval.requested_by = requested_by
        approval.approved_by = None
        approval.approved_at = None
        approval.rejected_at = None
        approval.remarks = remarks or approval.remarks
        approval.save()

        faculty_profile.is_active = False
        faculty_profile.save(update_fields=["is_active", "updated_at"])

        user = faculty_profile.user
        user.is_active = False
        user.save(update_fields=["is_active"])

        from onboarding.models import FacultyOnboardingRecord
        record = FacultyOnboardingRecord.objects.filter(faculty_profile=faculty_profile).first()
        employee_id = record.employee_id if record else "UNKNOWN"

        OnboardingAuditService.log(
            action="FACULTY_APPROVAL_PENDING",
            entity_type="FACULTY",
            entity_id=faculty_profile.id,
            actor=requested_by,
            metadata={"employee_id": employee_id},
        )
        return approval

    @staticmethod
    @transaction.atomic
    def approve(faculty_profile, approved_by, remarks=""):
        approval, _ = FacultyOnboardingApproval.objects.get_or_create(faculty_profile=faculty_profile)
        approval.status = FacultyOnboardingApproval.STATUS_APPROVED
        approval.approved_by = approved_by
        approval.approved_at = timezone.now()
        approval.rejected_at = None
        approval.remarks = remarks
        approval.save()

        faculty_profile.is_active = True
        faculty_profile.save(update_fields=["is_active", "updated_at"])

        user = faculty_profile.user
        user.is_active = True
        user.save(update_fields=["is_active"])

        from onboarding.models import FacultyOnboardingRecord
        record = FacultyOnboardingRecord.objects.filter(faculty_profile=faculty_profile).first()
        employee_id = record.employee_id if record else "UNKNOWN"

        OnboardingAuditService.log(
            action="FACULTY_APPROVED",
            entity_type="FACULTY",
            entity_id=faculty_profile.id,
            actor=approved_by,
            metadata={"employee_id": employee_id, "remarks": remarks},
        )
        return approval

    @staticmethod
    @transaction.atomic
    def reject(faculty_profile, rejected_by, remarks=""):
        approval, _ = FacultyOnboardingApproval.objects.get_or_create(faculty_profile=faculty_profile)
        approval.status = FacultyOnboardingApproval.STATUS_REJECTED
        approval.approved_by = rejected_by
        approval.rejected_at = timezone.now()
        approval.approved_at = None
        approval.remarks = remarks
        approval.save()

        faculty_profile.is_active = False
        faculty_profile.save(update_fields=["is_active", "updated_at"])

        user = faculty_profile.user
        user.is_active = False
        user.save(update_fields=["is_active"])

        from onboarding.models import FacultyOnboardingRecord
        record = FacultyOnboardingRecord.objects.filter(faculty_profile=faculty_profile).first()
        employee_id = record.employee_id if record else "UNKNOWN"

        OnboardingAuditService.log(
            action="FACULTY_REJECTED",
            entity_type="FACULTY",
            entity_id=faculty_profile.id,
            actor=rejected_by,
            metadata={"employee_id": employee_id, "remarks": remarks},
        )
        return approval

    @staticmethod
    @transaction.atomic
    def bulk_approve(faculty_ids, approved_by, remarks=""):
        from profile_management.models import FacultyProfile
        profiles = FacultyProfile.objects.select_related("user").filter(id__in=faculty_ids)
        results = []
        for profile in profiles:
            results.append(FacultyApprovalService.approve(profile, approved_by, remarks))
        return results

    @staticmethod
    @transaction.atomic
    def bulk_reject(faculty_ids, rejected_by, remarks=""):
        from profile_management.models import FacultyProfile
        profiles = FacultyProfile.objects.select_related("user").filter(id__in=faculty_ids)
        results = []
        for profile in profiles:
            results.append(FacultyApprovalService.reject(profile, rejected_by, remarks))
        return results
