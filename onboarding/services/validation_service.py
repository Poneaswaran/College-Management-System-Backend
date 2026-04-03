from datetime import datetime

from core.models import Course, Department, Role, Section, User
from onboarding.constants import (
    ERROR_TYPE_VALIDATION,
    MAX_BULK_UPLOAD_FILE_SIZE_BYTES,
    VALID_UPLOAD_EXTENSIONS,
)
from onboarding.exceptions import BulkValidationException
from profile_management.models import AcademicYear
from timetable.models import Subject


STUDENT_REQUIRED_FIELDS = {
    "registration_number",
    "first_name",
    "phone",
    "email",
    "department_code",
    "course_code",
    "section_name",
    "section_year",
    "academic_year_code",
}

FACULTY_REQUIRED_FIELDS = {
    "employee_id",
    "first_name",
    "email",
    "department_code",
    "designation",
    "qualifications",
    "specialization",
    "joining_date",
}


class ValidationService:
    @staticmethod
    def _json_safe(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): ValidationService._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [ValidationService._json_safe(v) for v in value]
        if hasattr(value, "pk"):
            return value.pk
        return str(value)

    @staticmethod
    def build_error(row, error_type, field, message, row_data=None):
        payload = {
            "row": row,
            "type": error_type,
            "field": field,
            "message": message,
        }
        if row_data is not None:
            payload["row_data"] = ValidationService._json_safe(row_data)
        return payload

    @staticmethod
    def validate_upload_file_meta(uploaded_file):
        if not uploaded_file:
            raise BulkValidationException("Upload file is required")

        if uploaded_file.size > MAX_BULK_UPLOAD_FILE_SIZE_BYTES:
            raise BulkValidationException("File size exceeds 10MB limit")

        filename = uploaded_file.name.lower()
        if not any(filename.endswith(ext) for ext in VALID_UPLOAD_EXTENSIONS):
            raise BulkValidationException("Unsupported file format. Allowed: .csv, .xlsx")

    @staticmethod
    def validate_file_schema(headers, required_fields):
        if not headers:
            raise BulkValidationException("Uploaded file contains no data rows")

        normalized_headers = set(str(h).strip() for h in headers if h is not None)
        missing = sorted(required_fields - normalized_headers)
        if missing:
            raise BulkValidationException(f"Missing required columns: {', '.join(missing)}")

    @staticmethod
    def validate_student_schema(headers):
        ValidationService.validate_file_schema(headers, STUDENT_REQUIRED_FIELDS)

    @staticmethod
    def validate_faculty_schema(headers):
        ValidationService.validate_file_schema(headers, FACULTY_REQUIRED_FIELDS)

    @staticmethod
    def parse_int(value, field_name):
        try:
            return int(value)
        except (TypeError, ValueError):
            raise BulkValidationException(f"Invalid integer for {field_name}")

    @staticmethod
    def parse_date(value, field_name):
        if value in [None, ""]:
            return None
        if isinstance(value, datetime):
            return value.date()
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return value
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]:
            try:
                return datetime.strptime(str(value), fmt).date()
            except ValueError:
                continue
        raise BulkValidationException(f"Invalid date format for {field_name}: {value}")

    @staticmethod
    def normalize_bool(value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        text = str(value).strip().lower()
        return text in {"1", "true", "yes", "y"}

    @staticmethod
    def get_reference_maps():
        departments = Department.objects.in_bulk(field_name="code")
        academic_years = AcademicYear.objects.in_bulk(field_name="year_code")

        course_qs = Course.objects.select_related("department")
        courses = {(c.department_id, c.code): c for c in course_qs}

        section_qs = Section.objects.select_related("course")
        sections = {(s.course_id, s.name, s.year): s for s in section_qs}

        subject_qs = Subject.objects.select_related("department")
        subjects = {s.code: s for s in subject_qs}

        roles = list(Role.objects.select_related("department"))
        role_map = {}
        for role in roles:
            role_map[(role.code, role.department_id)] = role
            if role.is_global:
                role_map.setdefault((role.code, None), role)

        return {
            "departments": departments,
            "academic_years": academic_years,
            "courses": courses,
            "sections": sections,
            "subjects": subjects,
            "roles": role_map,
        }

    @staticmethod
    def get_role_for_department(role_map, role_code, department):
        role = role_map.get((role_code, department.id)) or role_map.get((role_code, None))
        if not role:
            raise BulkValidationException(
                f"Role {role_code} is not configured for department {department.code}"
            )
        return role

    @staticmethod
    def validate_student_row(row, reference_maps, row_no):
        errors = []

        reg_no = str(row.get("registration_number", "")).strip()
        first_name = str(row.get("first_name", "")).strip()
        phone = str(row.get("phone", "")).strip()
        email = str(row.get("email", "")).strip().lower()

        department_code = str(row.get("department_code", "")).strip()
        course_code = str(row.get("course_code", "")).strip()
        section_name = str(row.get("section_name", "")).strip()
        academic_year_code = str(row.get("academic_year_code", "")).strip()

        if not reg_no:
            errors.append("registration_number is required")
        if not first_name:
            errors.append("first_name is required")
        if not phone:
            errors.append("phone is required")
        if not email:
            errors.append("email is required")

        department = reference_maps["departments"].get(department_code)
        if not department:
            errors.append(f"Invalid department_code: {department_code}")

        course = None
        if department:
            course = reference_maps["courses"].get((department.id, course_code))
            if not course:
                errors.append(f"Invalid course_code {course_code} for department {department_code}")

        try:
            section_year = ValidationService.parse_int(row.get("section_year"), "section_year")
        except BulkValidationException as exc:
            section_year = None
            errors.append(str(exc))

        section = None
        if course and section_year is not None:
            section = reference_maps["sections"].get((course.id, section_name, section_year))
            if not section:
                errors.append(
                    f"Section {section_name} for course {course_code} and year {section_year} not found"
                )

        academic_year = reference_maps["academic_years"].get(academic_year_code)
        if not academic_year:
            errors.append(f"Invalid academic_year_code: {academic_year_code}")

        try:
            semester = ValidationService.parse_int(row.get("semester", 1), "semester")
        except BulkValidationException as exc:
            semester = 1
            errors.append(str(exc))

        admission_date = None
        try:
            admission_date = ValidationService.parse_date(row.get("admission_date"), "admission_date")
        except BulkValidationException as exc:
            errors.append(str(exc))

        if errors:
            return None, [
                ValidationService.build_error(
                    row=row_no,
                    error_type=ERROR_TYPE_VALIDATION,
                    field="row",
                    message=err,
                    row_data=row,
                )
                for err in errors
            ]

        normalized = {
            "registration_number": reg_no,
            "first_name": first_name,
            "last_name": str(row.get("last_name", "")).strip(),
            "phone": phone,
            "email": email,
            "department": department,
            "course": course,
            "section": section,
            "year": section_year,
            "semester": semester,
            "admission_date": admission_date,
        }
        return normalized, None

    @staticmethod
    def validate_faculty_row(row, reference_maps, row_no):
        errors = []

        employee_id = str(row.get("employee_id", "")).strip().upper()
        first_name = str(row.get("first_name", "")).strip()
        email = str(row.get("email", "")).strip().lower()
        department_code = str(row.get("department_code", "")).strip()

        if not employee_id:
            errors.append("employee_id is required")
        if not first_name:
            errors.append("first_name is required")
        if not email:
            errors.append("email is required")

        department = reference_maps["departments"].get(department_code)
        if not department:
            errors.append(f"Invalid department_code: {department_code}")

        joining_date = None
        try:
            joining_date = ValidationService.parse_date(row.get("joining_date"), "joining_date")
        except BulkValidationException as exc:
            errors.append(str(exc))

        subject_codes_raw = str(row.get("subject_codes", "")).strip()
        subject_codes = [code.strip() for code in subject_codes_raw.split(",") if code.strip()]

        if department and subject_codes:
            invalid_subjects = []
            for code in subject_codes:
                subject = reference_maps["subjects"].get(code)
                if not subject or subject.department_id != department.id:
                    invalid_subjects.append(code)
            if invalid_subjects:
                errors.append(
                    "Subject(s) do not belong to selected department: "
                    + ", ".join(invalid_subjects)
                )

        is_hod = ValidationService.normalize_bool(row.get("is_hod"))

        try:
            teaching_load = ValidationService.parse_int(row.get("teaching_load", 0), "teaching_load")
        except BulkValidationException as exc:
            teaching_load = 0
            errors.append(str(exc))

        if errors:
            return None, [
                ValidationService.build_error(
                    row=row_no,
                    error_type=ERROR_TYPE_VALIDATION,
                    field="row",
                    message=err,
                    row_data=row,
                )
                for err in errors
            ]

        normalized = {
            "employee_id": employee_id,
            "first_name": first_name,
            "last_name": str(row.get("last_name", "")).strip(),
            "email": email,
            "department": department,
            "designation": str(row.get("designation", "")).strip(),
            "qualifications": str(row.get("qualifications", "")).strip(),
            "specialization": str(row.get("specialization", "")).strip(),
            "joining_date": joining_date,
            "office_hours": str(row.get("office_hours", "")).strip(),
            "teaching_load": teaching_load,
            "is_hod": is_hod,
            "subject_codes": subject_codes,
        }
        return normalized, None

    @staticmethod
    def validate_hod_uniqueness(department, candidate_user_id=None):
        hod_exists = User.objects.filter(
            department=department,
            role__code="HOD",
            is_active=True,
        )
        if candidate_user_id:
            hod_exists = hod_exists.exclude(id=candidate_user_id)
        return not hod_exists.exists()

    @staticmethod
    def validate_unique_email_for_upsert(email, existing_user_id=None):
        query = User.objects.filter(email__iexact=email)
        if existing_user_id:
            query = query.exclude(id=existing_user_id)
        return not query.exists()
