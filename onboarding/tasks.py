from onboarding.services.faculty_onboarding_service import FacultyOnboardingService
from onboarding.services.student_onboarding_service import StudentOnboardingService
from onboarding.models import OnboardingTaskLog
from onboarding.constants import TASK_STATUS_FAILED
from onboarding.services.audit_service import OnboardingAuditService
from django.utils import timezone


def process_student_bulk_upload(task_log_id):
    StudentOnboardingService.process_bulk_upload(task_log_id)


def process_faculty_bulk_upload(task_log_id):
    FacultyOnboardingService.process_bulk_upload(task_log_id)


def process_student_retry_bulk_upload(task_log_id, failed_rows):
    StudentOnboardingService.process_bulk_upload(task_log_id=task_log_id, rows_override=failed_rows)


def process_faculty_retry_bulk_upload(task_log_id, failed_rows):
    FacultyOnboardingService.process_bulk_upload(task_log_id=task_log_id, rows_override=failed_rows)


def onboarding_task_hook(task):
    if task.success:
        return

    args = task.args or []
    if not args:
        return

    task_log_id = args[0]
    task_log = OnboardingTaskLog.objects.filter(id=task_log_id).first()
    if not task_log:
        return

    task_log.status = TASK_STATUS_FAILED
    task_log.error_log = list(task_log.error_log or []) + [
        {
            "row": 0,
            "type": "SYSTEM_ERROR",
            "field": "worker",
            "message": task.result or "Worker crashed or task failed",
        }
    ]
    task_log.completed_at = timezone.now()
    task_log.save(update_fields=["status", "error_log", "completed_at", "updated_at"])
    OnboardingAuditService.log(
        action="ONBOARDING_TASK_FAILED",
        entity_type=task_log.entity_type,
        entity_id=task_log.task_id,
        actor=task_log.uploaded_by,
        metadata={"error": task.result or "Worker crashed or task failed"},
    )
