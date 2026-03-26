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
from onboarding.models import FacultyOnboardingRecord, OnboardingTaskLog
from onboarding.services.event_service import EventService
from onboarding.services.validation_service import ValidationService
from onboarding.exceptions import BulkValidationException
from onboarding.utils.file_parser import (
    get_extension,
    iter_chunked_rows,
    iter_upload_rows,
)

User = get_user_model()


class FacultyOnboardingService:
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
            normalized_rows = [(row, list(row.keys())) for row in rows_override]
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
                ValidationService.validate_faculty_schema(headers)
                headers_validated = True

            task_log.total_rows += len(rows_only)
            task_log.save(update_fields=["total_rows", "updated_at"])

            success_count, errors_count, row_errors = FacultyOnboardingService._process_chunk(
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

        FacultyOnboardingService._finalize_task(task_log, started_at)

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
                ValidationService.validate_faculty_schema(headers)
                headers_validated = True

            for idx, row in enumerate(rows_only):
                _, row_errors = ValidationService.validate_faculty_row(
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
        from profile_management.models import FacultyProfile

        valid_rows = []
        row_errors = []

        for idx, row in enumerate(chunk_rows):
            normalized, errors = ValidationService.validate_faculty_row(
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

        department_hod_in_chunk = set()
        filtered = []
        for row_no, row in valid_rows:
            if row["is_hod"]:
                dept_id = row["department"].id
                if dept_id in department_hod_in_chunk:
                    row_errors.append(
                        ValidationService.build_error(
                            row=row_no,
                            error_type=ERROR_TYPE_DB,
                            field="is_hod",
                            message="Only one HOD row is allowed per department in a single upload chunk",
                            row_data=row,
                        )
                    )
                    continue
                department_hod_in_chunk.add(dept_id)
            filtered.append((row_no, row))

        valid_rows = filtered
        if not valid_rows:
            return 0, len(chunk_rows), row_errors

        employee_ids = [row["employee_id"] for _, row in valid_rows]
        emails = [row["email"] for _, row in valid_rows if row.get("email")]

        existing_records_qs = FacultyOnboardingRecord.objects.select_related("faculty_profile", "faculty_profile__user").filter(
            employee_id__in=employee_ids
        )
        existing_records = {rec.employee_id: rec for rec in existing_records_qs}

        existing_users_qs = User.objects.select_related("role", "department").filter(
            register_number__in=employee_ids
        ) | User.objects.select_related("role", "department").filter(email__in=emails)
        existing_users = list(existing_users_qs)
        existing_users_by_register = {u.register_number: u for u in existing_users if u.register_number}
        existing_users_by_email = {(u.email or "").lower(): u for u in existing_users if u.email}

        existing_hod_department_ids = set(
            User.objects.filter(
                department_id__in=[row["department"].id for _, row in valid_rows],
                role__code="HOD",
                is_active=True,
            ).values_list("department_id", flat=True)
        )

        users_to_create = []
        users_to_update = []
        profiles_to_create_data = []
        profiles_to_update = []
        records_to_create = []
        records_to_update = []

        for row_no, row in valid_rows:
            try:
                with transaction.atomic():
                    employee_id = row["employee_id"]
                    email = row["email"]
                    department = row["department"]
                    record = existing_records.get(employee_id)

                    role_code = "HOD" if row["is_hod"] else "FACULTY"
                    role = ValidationService.get_role_for_department(reference_maps["roles"], role_code, department)

                    if record:
                        user = record.faculty_profile.user
                        if row["is_hod"] and department.id in existing_hod_department_ids and user.role.code != "HOD":
                            row_errors.append(
                                ValidationService.build_error(
                                    row=row_no,
                                    error_type=ERROR_TYPE_DB,
                                    field="is_hod",
                                    message="Another HOD already exists for this department",
                                    row_data=row,
                                )
                            )
                            continue

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
                        user.register_number = employee_id
                        user.department = department
                        user.role = role
                        user.is_active = True
                        users_to_update.append(user)

                        profile = record.faculty_profile
                        profile.first_name = row["first_name"]
                        profile.last_name = row["last_name"]
                        profile.department = department
                        profile.designation = row["designation"]
                        profile.qualifications = row["qualifications"]
                        profile.specialization = row["specialization"]
                        profile.joining_date = row["joining_date"]
                        profile.office_hours = row["office_hours"]
                        profile.teaching_load = row["teaching_load"]
                        profile.is_active = True
                        profiles_to_update.append(profile)

                        record.is_hod = row["is_hod"]
                        record.subject_codes = row["subject_codes"]
                        records_to_update.append(record)
                        continue

                    if row["is_hod"] and department.id in existing_hod_department_ids:
                        row_errors.append(
                            ValidationService.build_error(
                                row=row_no,
                                error_type=ERROR_TYPE_DB,
                                field="is_hod",
                                message="Another HOD already exists for this department",
                                row_data=row,
                            )
                        )
                        continue

                    existing_user = existing_users_by_register.get(employee_id) or existing_users_by_email.get(email)
                    if existing_user and hasattr(existing_user, "faculty_profile"):
                        row_errors.append(
                            ValidationService.build_error(
                                row=row_no,
                                error_type=ERROR_TYPE_DB,
                                field="employee_id",
                                message="User already linked to another faculty profile",
                                row_data=row,
                            )
                        )
                        continue

                    if not existing_user:
                        users_to_create.append(
                            User(
                                email=email,
                                register_number=employee_id,
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
            User.objects.bulk_update(
                users_to_update,
                ["email", "register_number", "department", "role", "is_active"],
            )

        if profiles_to_create_data:
            employee_ids_for_rows = [row["employee_id"] for _, row in profiles_to_create_data]
            emails_for_rows = [row["email"] for _, row in profiles_to_create_data if row.get("email")]

            user_map_by_emp = {
                user.register_number: user
                for user in User.objects.select_related("role", "department").filter(register_number__in=employee_ids_for_rows)
            }
            user_map_by_email = {
                user.email.lower(): user
                for user in User.objects.select_related("role", "department").filter(email__in=emails_for_rows)
                if user.email
            }

            profiles_to_create = []
            row_to_profile = []
            for row_no, row in profiles_to_create_data:
                user = user_map_by_emp.get(row["employee_id"]) or user_map_by_email.get(row["email"])
                if not user:
                    row_errors.append(
                        ValidationService.build_error(
                            row=row_no,
                            error_type=ERROR_TYPE_DB,
                            field="user",
                            message="Unable to resolve user for faculty profile creation",
                            row_data=row,
                        )
                    )
                    continue

                profile = FacultyProfile(
                    user=user,
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    department=row["department"],
                    designation=row["designation"],
                    qualifications=row["qualifications"],
                    specialization=row["specialization"],
                    joining_date=row["joining_date"],
                    office_hours=row["office_hours"],
                    teaching_load=row["teaching_load"],
                    is_active=True,
                )
                profiles_to_create.append(profile)
                row_to_profile.append((row_no, row, profile))

            if profiles_to_create:
                FacultyProfile.objects.bulk_create(profiles_to_create, ignore_conflicts=True)

            persisted_profiles = {
                p.user_id: p
                for p in FacultyProfile.objects.select_related("user").filter(
                    user_id__in=[profile.user_id for profile in profiles_to_create]
                )
            }

            for row_no, row, profile in row_to_profile:
                persisted = persisted_profiles.get(profile.user_id)
                if not persisted:
                    row_errors.append(
                        ValidationService.build_error(
                            row=row_no,
                            error_type=ERROR_TYPE_DB,
                            field="faculty_profile",
                            message="Unable to persist faculty profile",
                            row_data=row,
                        )
                    )
                    continue
                records_to_create.append(
                    FacultyOnboardingRecord(
                        faculty_profile=persisted,
                        employee_id=row["employee_id"],
                        is_hod=row["is_hod"],
                        subject_codes=row["subject_codes"],
                    )
                )
                EventService.emit_faculty_created(row["employee_id"], persisted.user.email)

        if profiles_to_update:
            lock_ids = [p.id for p in profiles_to_update if p.id]
            list(FacultyProfile.objects.select_for_update().filter(id__in=lock_ids))
            FacultyProfile.objects.bulk_update(
                profiles_to_update,
                [
                    "first_name",
                    "last_name",
                    "department",
                    "designation",
                    "qualifications",
                    "specialization",
                    "joining_date",
                    "office_hours",
                    "teaching_load",
                    "is_active",
                ],
            )

        if records_to_create:
            FacultyOnboardingRecord.objects.bulk_create(records_to_create, ignore_conflicts=True)

        if records_to_update:
            lock_ids = [r.id for r in records_to_update if r.id]
            list(FacultyOnboardingRecord.objects.select_for_update().filter(id__in=lock_ids))
            FacultyOnboardingRecord.objects.bulk_update(records_to_update, ["is_hod", "subject_codes"])

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
