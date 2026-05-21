from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Avg, Count, Max, Q
from django.utils import timezone

from core.models import Department
from profile_management.models import StudentProfile

from .models import (
    Company,
    PlacementDrive,
    PlacementOffer,
    StudentApplication,
    StudentPlacementProfile,
)
from .tasks import (
    notify_application_confirmed,
    notify_offer_uploaded,
    notify_rejected,
    notify_selected,
    notify_shortlisted,
)


class PlacementService:
    @staticmethod
    def _apply_tenant_filter(queryset, tenant=None):
        if tenant is None:
            return queryset
        if any(field.name == "tenant" for field in queryset.model._meta.fields):
            return queryset.filter(tenant=tenant)
        return queryset

    @staticmethod
    def _get_student_batch_year(student_profile):
        batch_year = getattr(student_profile, "batch_year", None)
        if batch_year is None:
            admission_date = getattr(student_profile, "admission_date", None)
            if admission_date:
                batch_year = admission_date.year
        if batch_year is None:
            batch_year = getattr(student_profile, "year", None)
        return batch_year

    @staticmethod
    def _get_student_cgpa(student_profile):
        cgpa = getattr(student_profile, "cgpa", None)
        if cgpa is None:
            cgpa_record = getattr(student_profile, "cgpa_record", None)
            if cgpa_record is not None:
                cgpa = getattr(cgpa_record, "cgpa", None)
        if cgpa is None:
            cgpa = getattr(student_profile, "current_gpa", None)
        return cgpa

    @staticmethod
    def get_eligible_drives(student_profile: StudentProfile):
        try:
            if student_profile.placement_profile.is_placed:
                return PlacementDrive.objects.none()
        except StudentPlacementProfile.DoesNotExist:
            pass

        batch_year = PlacementService._get_student_batch_year(student_profile)
        cgpa = PlacementService._get_student_cgpa(student_profile)

        drives = PlacementDrive.objects.select_related("company").prefetch_related(
            "eligible_branches"
        ).filter(
            is_active=True,
            status__in=["upcoming", "ongoing"],
            eligible_batch_year=batch_year,
            eligible_branches=student_profile.department,
            application_deadline__gt=timezone.now(),
        )

        if cgpa is None:
            return drives.filter(min_cgpa__isnull=True)

        return drives.filter(Q(min_cgpa__isnull=True) | Q(min_cgpa__lte=cgpa))

    @staticmethod
    def apply_to_drive(student_profile, drive, resume=None, cover_letter=""):
        eligible_drives = PlacementService.get_eligible_drives(student_profile)
        if not eligible_drives.filter(id=drive.id).exists():
            raise ValidationError("Not eligible for this drive")

        if StudentApplication.objects.filter(
            student=student_profile, drive=drive, is_active=True
        ).exists():
            raise ValidationError("Already applied to this drive")

        application = StudentApplication.objects.create(
            student=student_profile,
            drive=drive,
            resume=resume,
            cover_letter=cover_letter,
            status="applied",
        )
        StudentPlacementProfile.objects.get_or_create(student=student_profile)
        notify_application_confirmed.delay(str(application.id))
        return application

    @staticmethod
    def update_application_status(application, new_status, updated_by):
        valid_statuses = {choice[0] for choice in StudentApplication.STATUS_CHOICES}
        if new_status not in valid_statuses:
            raise ValidationError("Invalid status")

        application.status = new_status
        application.save()

        if new_status == "shortlisted":
            notify_shortlisted.delay(str(application.id))
        elif new_status == "selected":
            notify_selected.delay(str(application.id))
        elif new_status == "rejected":
            notify_rejected.delay(str(application.id))

        if new_status == "selected":
            profile, _ = StudentPlacementProfile.objects.get_or_create(student=application.student)
            profile.is_placed = True
            profile.placed_company = application.drive.company
            profile.save()

        return application

    @staticmethod
    def withdraw_application(application, student_profile):
        if application.student != student_profile:
            raise PermissionDenied("Not your application")

        if application.status in ["selected", "withdrawn"]:
            raise ValidationError("Cannot withdraw a selected or already withdrawn application")

        application.status = "withdrawn"
        application.save()
        return application

    @staticmethod
    def bulk_shortlist(drive, student_ids):
        applications = StudentApplication.objects.select_related(
            "student",
            "drive",
            "drive__company",
        ).filter(
            drive=drive,
            student_id__in=student_ids,
            status="applied",
            is_active=True,
        )
        application_ids = list(applications.values_list("id", flat=True))
        updated_count = applications.update(status="shortlisted")

        for app_id in application_ids:
            notify_shortlisted.delay(str(app_id))

        return updated_count

    @staticmethod
    def create_offer(application, ctc, joining_date, location, offer_letter=None):
        if application.status != "selected":
            raise ValidationError("Offer can only be created for selected applications")

        if PlacementOffer.objects.filter(application=application).exists():
            raise ValidationError("Offer already exists for this application")

        offer = PlacementOffer.objects.create(
            application=application,
            ctc=ctc,
            joining_date=joining_date,
            location=location,
            offer_letter=offer_letter,
        )
        notify_offer_uploaded.delay(str(offer.id))
        return offer

    @staticmethod
    def accept_offer(offer, student_profile):
        if offer.application.student != student_profile:
            raise PermissionDenied("Not your offer")

        if offer.is_accepted:
            raise ValidationError("Offer already accepted")

        offer.is_accepted = True
        offer.accepted_at = timezone.now()
        offer.save()

        profile, _ = StudentPlacementProfile.objects.get_or_create(student=student_profile)
        profile.is_placed = True
        profile.placed_company = offer.application.drive.company
        profile.placed_package = offer.ctc
        profile.save()
        return offer

    @staticmethod
    def get_analytics(tenant=None):
        drive_qs = PlacementService._apply_tenant_filter(
            PlacementDrive.objects.select_related("company").filter(is_active=True),
            tenant=tenant,
        )
        company_qs = PlacementService._apply_tenant_filter(
            Company.objects.filter(is_active=True),
            tenant=tenant,
        )
        application_qs = PlacementService._apply_tenant_filter(
            StudentApplication.objects.select_related("student", "drive").filter(is_active=True),
            tenant=tenant,
        )
        placement_profile_qs = PlacementService._apply_tenant_filter(
            StudentPlacementProfile.objects.select_related("student").filter(is_active=True),
            tenant=tenant,
        )

        students_eligible_qs = StudentProfile.objects.select_related("department").filter(is_active=True)
        students_eligible = students_eligible_qs.filter(
            Q(placement_profile__isnull=True) | Q(placement_profile__is_placed=False)
        ).count()
        students_applied = application_qs.values("student").distinct().count()
        students_placed = placement_profile_qs.filter(is_placed=True).count()
        placement_percentage = (students_placed / students_eligible * 100) if students_eligible else 0.0

        avg_package = placement_profile_qs.filter(is_placed=True).aggregate(
            Avg("placed_package")
        )["placed_package__avg"] or 0.0
        highest_package = placement_profile_qs.filter(is_placed=True).aggregate(
            Max("placed_package")
        )["placed_package__max"] or 0.0

        branch_wise = []
        for department in Department.objects.filter(is_active=True):
            total_students = students_eligible_qs.filter(department=department).count()
            placed_students = placement_profile_qs.filter(
                is_placed=True,
                student__department=department,
                student__is_active=True,
            ).count()
            branch_wise.append(
                {"branch": department.name, "placed": placed_students, "total": total_students}
            )

        drive_wise = []
        for drive in drive_qs:
            applied_count = application_qs.filter(drive=drive).count()
            selected_count = application_qs.filter(drive=drive, status="selected").count()
            drive_wise.append(
                {
                    "drive": drive.title,
                    "applied": applied_count,
                    "selected": selected_count,
                }
            )

        top_companies_qs = company_qs.annotate(
            hired=Count(
                "placed_students",
                filter=Q(placed_students__is_placed=True, placed_students__is_active=True),
            )
        ).order_by("-hired", "name")[:5]
        top_companies = [{"company": company.name, "hired": company.hired} for company in top_companies_qs]

        return {
            "total_drives": drive_qs.count(),
            "total_companies": company_qs.count(),
            "students_eligible": students_eligible,
            "students_applied": students_applied,
            "students_placed": students_placed,
            "placement_percentage": placement_percentage,
            "avg_package": float(avg_package),
            "highest_package": float(highest_package),
            "branch_wise": branch_wise,
            "drive_wise": drive_wise,
            "top_companies": top_companies,
        }
