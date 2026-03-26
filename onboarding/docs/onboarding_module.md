# Student + Faculty Onboarding Module

## 1. Overview

The onboarding module provides production-ready REST APIs for:

- Student bulk onboarding (idempotent upsert by registration number)
- Faculty bulk onboarding (idempotent upsert by employee ID)
- Async processing with Django Q2 and task progress tracking
- Student and faculty ID card generation/revocation
- QR verification for generated ID cards

This module is integrated into the existing JWT-authenticated Django backend and reuses existing domain models from core, profile_management, and timetable apps.

## 2. Architecture

### App Structure

```
onboarding/
├── models.py
├── serializers/
│   ├── student_serializers.py
│   └── faculty_serializers.py
├── views/
│   ├── student_views.py
│   └── faculty_views.py
├── urls.py
├── tasks.py
├── services/
│   ├── student_onboarding_service.py
│   ├── faculty_onboarding_service.py
│   ├── validation_service.py
│   └── id_card_service.py
├── utils/
│   ├── file_parser.py
│   ├── qr_generator.py
│   └── id_generator.py
├── constants.py
├── exceptions.py
└── docs/
    └── onboarding_module.md
```

### Service Layer Responsibilities

- `student_onboarding_service.py`: async chunk processing and upsert for student onboarding
- `faculty_onboarding_service.py`: async chunk processing and upsert for faculty onboarding
- `validation_service.py`: schema + domain validations for student/faculty
- `id_card_service.py`: QR JWT, PDF generation, issue/revoke, and QR token verification

Views contain only request/response and permission handling.

## 3. Models Created/Used

### New Models

#### OnboardingTaskLog

- `task_id`: async task reference
- `uploaded_by`: user who uploaded file
- `file`, `file_hash`: upload metadata and duplicate detection
- `total_rows`, `processed`, `success_count`, `failure_count`
- `status`: `PENDING | PROCESSING | PARTIAL | COMPLETED | FAILED`
- `error_log`: row-level errors in JSON format

#### FacultyOnboardingRecord

- `faculty_profile`: one-to-one with existing faculty profile
- `employee_id`: unique idempotency key
- `is_hod`: onboarding-managed HOD flag
- `subject_codes`: validated subject code list from upload

#### StudentIDCard

- `student_profile`: one-to-one
- `status`: `PENDING | READY | ISSUED | REVOKED`
- `card_number`, `qr_token`, `qr_image`, `pdf_file`
- timestamps for generation/issuance/revocation

#### FacultyIDCard

- `faculty_profile`: one-to-one
- `status`: `PENDING | READY | ISSUED | REVOKED`
- `card_number`, `qr_token`, `qr_image`, `pdf_file`
- timestamps for generation/issuance/revocation

### Existing Models Reused

- `core.User`, `core.Role`, `core.Department`, `core.Course`, `core.Section`
- `profile_management.StudentProfile`, `profile_management.FacultyProfile`, `profile_management.AcademicYear`
- `timetable.Subject`

## 4. APIs

All endpoints are mounted under `/api/`.

### Student APIs

#### POST `/api/admin/students/bulk-upload/`

- Purpose: Upload student file and queue async onboarding
- Permission: Authenticated admin (`ADMIN`, `SUPER_ADMIN`, or `is_superuser`)
- Request: multipart with `file`
- Response:

```json
{
  "task_id": "...",
  "status": "PENDING",
  "message": "Student bulk upload queued"
}
```

#### GET `/api/admin/students/bulk-upload/{task_id}/status/`

- Purpose: Get progress and errors of student onboarding task
- Permission: Authenticated admin
- Response includes task counters and `error_log`

#### GET `/api/students/me/id-card/`

- Purpose: Get logged-in student's ID card
- Permission: Authenticated user with student profile

#### POST `/api/admin/students/{id}/generate-id-card/`

- Purpose: Generate or regenerate student ID card + QR + PDF
- Permission: Authenticated admin

#### POST `/api/admin/students/{id}/revoke-id-card/`

- Purpose: Revoke student ID card
- Permission: Authenticated admin

### Faculty APIs

#### POST `/api/admin/faculty/bulk-upload/`

- Purpose: Upload faculty file and queue async onboarding
- Permission: Authenticated admin
- Request: multipart with `file`

#### GET `/api/admin/faculty/bulk-upload/{task_id}/status/`

- Purpose: Get progress and errors of faculty onboarding task
- Permission: Authenticated admin

#### GET `/api/faculty/me/id-card/`

- Purpose: Get logged-in faculty ID card
- Permission: Authenticated user with faculty profile

#### POST `/api/admin/faculty/{id}/generate-id-card/`

- Purpose: Generate or regenerate faculty ID card + QR + PDF
- Permission: Authenticated admin

#### POST `/api/admin/faculty/{id}/revoke-id-card/`

- Purpose: Revoke faculty ID card
- Permission: Authenticated admin

### QR Verification API

#### POST `/api/qr/verify/`

- Purpose: Verify JWT payload embedded in QR and validate card state
- Permission: Authenticated user
- Request:

```json
{
  "token": "<qr-jwt-token>"
}
```

- Response:

```json
{
  "is_valid": true,
  "entity_type": "STUDENT",
  "card_number": "STU-...",
  "status": "ISSUED"
}
```

## 5. Validations

### Common Validations

- File presence
- File size max 10MB
- File extension allowed: `.csv`, `.xlsx`
- File schema validation for mandatory columns
- Duplicate upload prevention using SHA256 file hash
- Email uniqueness conflict checks during upsert

### Student Validations

- Required fields: registration number, name, phone, email, department/course/section, academic year
- Department exists
- Course belongs to department
- Section exists for `(course, section_name, section_year)`
- Academic year code exists
- Data type/date parsing with row-level error capture

### Faculty Validations

- Required fields: employee ID, name, email, department, designation, joining and qualification fields
- Department exists
- Subject codes belong to faculty department
- Employee ID uniqueness via `FacultyOnboardingRecord`
- One HOD per department rule

## 6. Async Flow

Django Q2 is configured via `django_q` + `Q_CLUSTER` in Django settings.

### Lifecycle

1. Upload file via REST API
2. Save `OnboardingTaskLog` with `PENDING`
3. Trigger `async_task()` with task function and log id
4. Worker parses file and validates schema
5. Process chunk-by-chunk (100 rows per batch)
6. Perform create/update operations
7. Update progress counters and row errors after each chunk
8. Final status set to `COMPLETED`, `PARTIAL`, or `FAILED`

## 7. Performance Optimizations

The implementation avoids N+1 and scales for bulk processing by using:

- `select_related()` on foreign-key heavy reads
- bulk reference loading and in-memory maps for lookups
- `bulk_create()` for users, profiles, records
- `bulk_update()` for user/profile/record updates
- chunked processing for memory and transaction control

## 8. Security

- JWT auth via existing custom authentication class
- Admin-only permissions for onboarding operations
- File type/size checks for upload hardening
- Duplicate file hash prevention
- QR verification checks card status and revocation state

## 9. ID Card System

- QR payload uses JWT signed with project JWT secret and algorithm
- QR image generated using `qrcode`
- PDF generated with `reportlab`
- Card status lifecycle:

`PENDING -> READY -> ISSUED -> REVOKED`

- Student and faculty card generation supports regeneration and revocation

## 10. Enhancements

- Transaction safety: each processing chunk is wrapped in `transaction.atomic()`, and each row is handled within an inner atomic block for row-level failure isolation.
- Concurrency fixes: onboarding logs now include `idempotency_key` with DB-level uniqueness and active-file uniqueness constraints (`entity_type + file_hash`).
- Retry mechanism: failed rows can be retried using `POST /api/admin/onboarding/retry-failed/{task_id}/`.
- Dry-run mode: upload APIs support `?dry_run=true` to run validations without DB writes.
- Structured error schema:

```json
{
  "row": 12,
  "type": "VALIDATION_ERROR",
  "field": "department_code",
  "message": "Department not found",
  "row_data": {
    "department_code": "XYZ"
  }
}
```

## 11. Performance

- Memory optimization: file parsing now streams rows and processes chunk-by-chunk (`iter_upload_rows` + `iter_chunked_rows`) instead of loading whole files.
- Query optimization:
  - reference maps built via `in_bulk()` / preloaded querysets
  - FK-heavy queries use `select_related()`
  - updates and inserts use `bulk_update()` / `bulk_create()`
  - critical update sets lock rows using `select_for_update()` before bulk update

## 12. Failure Recovery

- Async resilience:
  - Django Q2 tasks now run with a hook (`onboarding.tasks.onboarding_task_hook`) to capture worker-level failures.
  - `Q_CLUSTER` includes retry/timeouts and bounded persistence settings for safer worker behavior.
- Retry flow:
  1. Original task stores structured row-level errors.
  2. Retry API extracts failed `row_data`.
  3. A new retry task log is created with linkage to `source_task` and incremented `retry_attempt`.
  4. Only failed rows are reprocessed asynchronously.

## 13. Observability

`OnboardingTaskLog` now tracks:

- `processing_started_at`
- `processing_duration_ms`
- `success_rate`
- `failure_rate`
- retry metadata (`is_retry`, `retry_attempt`, `source_task`)
- archival control (`is_active`)

Task status APIs expose these fields for dashboarding and operational monitoring.

## 14. Security Hardening

- Duplicate upload race prevention through DB-enforced idempotency keys.
- QR token hardening:
  - includes `exp` claim and `card_status` claim
  - verification checks token claim and current DB card status
  - revoked cards are always rejected
- Existing JWT auth + admin-only permission enforcement retained.

## 15. Configuration-Driven Refactor

The onboarding system now supports DB-driven runtime configuration through the `configuration` app.

### Configuration Model

- App: `configuration`
- Model: `Configuration`
- Fields: `key`, `value` (JSON), `description`, `is_active`

### Config Keys

- `onboarding.id_card.qr_ttl` (default: `2592000`)
- `onboarding.id_card.format` (default: `PREFIX-ID-RANDOM`)
- `onboarding.id_card.pdf_layout`:

```json
{
  "fields": ["name", "department", "card_number"],
  "title": "Student ID Card"
}
```

- `onboarding.id_card.qr_payload`:

```json
{
  "include_fields": ["entity_id", "card_id", "exp"]
}
```

- `onboarding.features.enable_id_card_generation` (default: `true`)
- `notifications.flags`:

```json
{
  "enable_email_notifications": true,
  "enable_sms_notifications": false
}
```

- `notifications.events`:

```json
{
  "STUDENT_CREATED": {"email": true, "sms": false},
  "FACULTY_CREATED": {"email": true, "sms": false},
  "ID_CARD_GENERATED": {"email": true, "sms": false}
}
```

## 16. Notification Decoupling

Email/sms dispatch is no longer implemented directly in onboarding services.

- `onboarding.services.event_service.EventService` now emits via
  `notifications.services.event_dispatcher.EventDispatcher`.
- `notifications.services.delivery_service.NotificationService` owns delivery methods:
  - `send_email(...)`
  - `send_sms(...)`

This keeps onboarding focused on domain events and preserves backward compatibility through a `LEGACY_EMAIL` event path.

## 17. ETag Support

ETag support is applied to onboarding GET APIs via `ETagMixin`:

- Student task status
- Faculty task status
- Student my ID card
- Faculty my ID card

Behavior:

- Server computes ETag from response payload + detected update timestamp.
- `ETag` header is set on successful GET responses.
- If request has `If-None-Match` with same ETag, API returns `304 Not Modified`.

## 18. Backward Compatibility

- Existing endpoints and response core fields remain intact.
- Config service always falls back to defaults when DB key is missing.
- Legacy email path remains supported through event-dispatcher compatibility handling.
