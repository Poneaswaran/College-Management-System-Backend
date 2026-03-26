from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import DatabaseError, transaction
from django.utils import timezone

from onboarding.constants import (
    DEFAULT_CHUNK_SIZE,
    ERROR_TYPE_DB,
    ERROR_TYPE_SYSTEM,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PARTIAL,
    TASK_STATUS_PROCESSING,
)
from onboarding.models import OnboardingTaskLog
from onboarding.services.event_service import EventService
from onboarding.services.validation_service import ValidationService
from onboarding.exceptions import BulkValidationException
from onboarding.utils.file_parser import (
    get_extension,
    iter_chunked_rows,
    iter_upload_rows,
)

User = get_user_model()


class StudentOnboardingService:
    @staticmethod
    def process_bulk_upload(task_log_id, rows_override=None):
        task_log = OnboardingTaskLog.objects.select_related("uploaded_by").get(id=task_log_id)
        started_at = timezone.now()
        task_log.status = TASK_STATUS_PROCESSING
        task_log.processing_started_at = started_at
        task_log.error_log = []
        task_log.total_rows = 0
        task_log.processed = 0
        task_log.success_count = 0
        task_log.failure_count = 0
        task_log.save(
            update_fields=[
                "status",
                "processing_started_at",
                "error_log",
                "total_rows",
                "processed",
                "success_count",
                "failure_count",
                "updated_at",
            ]
        )

        reference_maps = ValidationService.get_reference_maps()

        if rows_override is None:
            extension = get_extension(task_log.file.name)
            row_iterator = iter_upload_rows(task_log.file, extension)
            chunk_source = iter_chunked_rows(row_iterator, DEFAULT_CHUNK_SIZE)
        else:
            normalized_rows = [
                (ValidationService_row, list(ValidationService_row.keys()))
                for ValidationService_row in rows_override
            ]
            chunk_source = iter_chunked_rows(iter(normalized_rows), DEFAULT_CHUNK_SIZE)

        headers_validated = False
        row_cursor = 2

        for chunk in chunk_source:
            rows_only = []
            headers = []
            for row_data, row_headers in chunk:
                rows_only.append(row_data)
                headers = row_headers

            if not headers_validated:
                ValidationService.validate_student_schema(headers)
                headers_validated = True

            task_log.total_rows += len(rows_only)
            task_log.save(update_fields=["total_rows", "updated_at"])

            success_count, errors_count, row_errors = StudentOnboardingService._process_chunk(
                chunk_rows=rows_only,
                reference_maps=reference_maps,
                row_start=row_cursor,
                dry_run=task_log.dry_run,
            )

            row_cursor += len(rows_only)

            task_log.processed += len(rows_only)
            task_log.success_count += success_count
            task_log.failure_count += errors_count
            if row_errors:
                task_log.error_log.extend(row_errors)
            task_log.save(
                update_fields=[
                    "processed",
                    "success_count",
                    "failure_count",
                    "error_log",
                    "updated_at",
                ]
            )

        if task_log.total_rows == 0:
            raise BulkValidationException("Uploaded file contains no data rows")

        StudentOnboardingService._finalize_task(task_log, started_at)

    @staticmethod
    def validate_bulk_upload(file_obj):
        reference_maps = ValidationService.get_reference_maps()
        extension = get_extension(file_obj.name)
        row_iterator = iter_upload_rows(file_obj, extension)

        errors = []
        total_rows = 0
        headers_validated = False
        row_cursor = 2

        for chunk in iter_chunked_rows(row_iterator, DEFAULT_CHUNK_SIZE):
            rows_only = []
            headers = []
            for row_data, row_headers in chunk:
                rows_only.append(row_data)
                headers = row_headers

            if not headers_validated:
                ValidationService.validate_student_schema(headers)
                headers_validated = True

            for idx, row in enumerate(rows_only):
                _, row_errors = ValidationService.validate_student_row(
                    row=row,
                    reference_maps=reference_maps,
                    row_no=row_cursor + idx,
                )
                if row_errors:
                    errors.extend(row_errors)

            row_cursor += len(rows_only)
            total_rows += len(rows_only)

        if total_rows == 0:
            raise BulkValidationException("Uploaded file contains no data rows")

        return {
            "total_rows": total_rows,
            "success_count": total_rows - len(errors),
            "failure_count": len(errors),
            "error_log": errors,
        }

    @staticmethod
    @transaction.atomic
    def _process_chunk(chunk_rows, reference_maps, row_start, dry_run=False):
        from profile_management.models import StudentProfile

        valid_rows = []
        row_errors = []

        for idx, row in enumerate(chunk_rows):
            normalized, errors = ValidationService.validate_student_row(
                row=row,
                reference_maps=reference_maps,
                row_no=row_start + idx,
            )
            if errors:
                row_errors.extend(errors)
            else:
                valid_rows.append((row_start + idx, normalized))

        if dry_run:
            failures = len(row_errors)
            return len(chunk_rows) - failures, failures, row_errors

        if not valid_rows:
            return 0, len(chunk_rows), row_errors

        reg_numbers = [row["registration_number"] for _, row in valid_rows]
        emails = [row["email"] for _, row in valid_rows if row.get("email")]

        existing_profiles_qs = StudentProfile.objects.select_related("user").filter(register_number__in=reg_numbers)
        existing_profiles = {profile.register_number: profile for profile in existing_profiles_qs}

        existing_users_qs = User.objects.select_related("role", "department").filter(
            register_number__in=reg_numbers
        ) | User.objects.select_related("role", "department").filter(email__in=emails)
        existing_users = list(existing_users_qs)
        existing_users_by_register = {user.register_number: user for user in existing_users if user.register_number}
        existing_users_by_email = {(user.email or "").lower(): user for user in existing_users if user.email}

        users_to_create = []
        users_to_update = []
        profiles_to_create_data = []
        profiles_to_update = []

        for row_no, row in valid_rows:
            try:
                with transaction.atomic():
                    register_number = row["registration_number"]
                    email = row["email"]
                    department = row["department"]
                    role = ValidationService.get_role_for_department(reference_maps["roles"], "STUDENT", department)

                    existing_profile = existing_profiles.get(register_number)
                    if existing_profile:
                        user = existing_profile.user
                        email_owner = existing_users_by_email.get(email)
                        if email_owner and email_owner.id != user.id:
                            row_errors.append(
                                ValidationService.build_error(
                                    row=row_no,
                                    error_type=ERROR_TYPE_DB,
                                    field="email",
                                    message=f"Email already used by another user: {email}",
                                    row_data=row,
                                )
                            )
                            continue

                        user.email = email
                        user.department = department
                        user.role = role
                        user.is_active = True
                        users_to_update.append(user)

                        existing_profile.first_name = row["first_name"]
                        existing_profile.last_name = row["last_name"]
                        existing_profile.phone = row["phone"]
                        existing_profile.department = department
                        existing_profile.course = row["course"]
                        existing_profile.section = row["section"]
                        existing_profile.year = row["year"]
                        existing_profile.semester = row["semester"]
                        existing_profile.admission_date = row["admission_date"]
                        existing_profile.is_active = True
                        profiles_to_update.append(existing_profile)
                        continue

                    existing_user = existing_users_by_register.get(register_number) or existing_users_by_email.get(email)
                    if existing_user and hasattr(existing_user, "student_profile"):
                        row_errors.append(
                            ValidationService.build_error(
                                row=row_no,
                                error_type=ERROR_TYPE_DB,
                                field="registration_number",
                                message="User already linked to another student profile",
                                row_data=row,
                            )
                        )
                        continue

                    if not existing_user:
                        users_to_create.append(
                            User(
                                email=email,
                                register_number=register_number,
                                role=role,
                                department=department,
                                is_active=True,
                                password=make_password(uuid4().hex),
                            )
                        )

                    profiles_to_create_data.append((row_no, row))
            except DatabaseError as exc:
                row_errors.append(
                    ValidationService.build_error(
                        row=row_no,
                        error_type=ERROR_TYPE_DB,
                        field="row",
                        message=f"Database error: {exc}",
                        row_data=row,
                    )
                )
            except Exception as exc:
                row_errors.append(
                    ValidationService.build_error(
                        row=row_no,
                        error_type=ERROR_TYPE_SYSTEM,
                        field="row",
                        message=f"System error: {exc}",
                        row_data=row,
                    )
                )

        if users_to_create:
            User.objects.bulk_create(users_to_create, ignore_conflicts=True)

        if users_to_update:
            lock_ids = [u.id for u in users_to_update if u.id]
            list(User.objects.select_for_update().filter(id__in=lock_ids))
            User.objects.bulk_update(users_to_update, ["email", "department", "role", "is_active"])

        if profiles_to_create_data:
            regs = [row["registration_number"] for _, row in profiles_to_create_data]
            emails_for_rows = [row["email"] for _, row in profiles_to_create_data if row.get("email")]

            user_map_by_reg = {
                user.register_number: user
                for user in User.objects.select_related("role", "department").filter(register_number__in=regs)
            }
            user_map_by_email = {
                user.email.lower(): user
                for user in User.objects.select_related("role", "department").filter(email__in=emails_for_rows)
                if user.email
            }

            profiles_to_create = []
            for row_no, row in profiles_to_create_data:
                user = user_map_by_reg.get(row["registration_number"]) or user_map_by_email.get(row["email"])
                if not user:
                    row_errors.append(
                        ValidationService.build_error(
                            row=row_no,
                            error_type=ERROR_TYPE_DB,
                            field="user",
                            message="Unable to resolve user for student profile creation",
                            row_data=row,
                        )
                    )
                    continue

                profiles_to_create.append(
                    StudentProfile(
                        user=user,
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                        phone=row["phone"],
                        register_number=row["registration_number"],
                        department=row["department"],
                        course=row["course"],
                        section=row["section"],
                        year=row["year"],
                        semester=row["semester"],
                        admission_date=row["admission_date"],
                        is_active=True,
                    )
                )
                EventService.emit_student_created(row["registration_number"], user.email)

            if profiles_to_create:
                StudentProfile.objects.bulk_create(profiles_to_create, ignore_conflicts=True)

        if profiles_to_update:
            lock_ids = [p.id for p in profiles_to_update if p.id]
            list(StudentProfile.objects.select_for_update().filter(id__in=lock_ids))
            StudentProfile.objects.bulk_update(
                profiles_to_update,
                [
                    "first_name",
                    "last_name",
                    "phone",
                    "department",
                    "course",
                    "section",
                    "year",
                    "semester",
                    "admission_date",
                    "is_active",
                ],
            )

        total_failures = len(row_errors)
        total_success = max(0, len(chunk_rows) - total_failures)
        return total_success, total_failures, row_errors

    @staticmethod
    def _finalize_task(task_log, started_at):
        if task_log.failure_count > 0 and task_log.success_count > 0:
            task_log.status = TASK_STATUS_PARTIAL
        elif task_log.failure_count > 0:
            task_log.status = TASK_STATUS_FAILED
        else:
            task_log.status = TASK_STATUS_COMPLETED

        ended_at = timezone.now()
        elapsed_ms = int((ended_at - started_at).total_seconds() * 1000)
        total = task_log.total_rows or 0
        if total:
            success_rate = (Decimal(task_log.success_count) * Decimal("100.00")) / Decimal(total)
            failure_rate = (Decimal(task_log.failure_count) * Decimal("100.00")) / Decimal(total)
        else:
            success_rate = Decimal("0")
            failure_rate = Decimal("0")

        task_log.processing_duration_ms = max(0, elapsed_ms)
        task_log.success_rate = success_rate
        task_log.failure_rate = failure_rate
        task_log.completed_at = ended_at
        task_log.save(
            update_fields=[
                "status",
                "processing_duration_ms",
                "success_rate",
                "failure_rate",
                "completed_at",
                "updated_at",
            ]
        )
