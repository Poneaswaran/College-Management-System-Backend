"""
timetable/serializers.py

All serializers for the timetable application.

Existing (preserved):
    TimetableEntrySerializer
    TimetableDetailSerializer
    PeriodDefinitionSerializer
    BulkTimetableEntryInputSerializer
    SectionCreateTimetableSerializer

New (added):
    SectionSubjectRequirementSerializer      — read/write for a single row
    SectionSubjectRequirementBulkSerializer  — bulk POST for one section+semester
    RoomMaintenanceBlockSerializer           — read/write for maintenance windows
"""

from rest_framework import serializers

from timetable.models import (
    TimetableEntry,
    Subject,
    PeriodDefinition,
    Room,
    TimetableApprovalRequest,
    SectionSubjectRequirement,
    RoomMaintenanceBlock,
    DepartmentSectionCombinePolicy,
    CombinedClassSession,
)
from core.models import Department, Section, User
from profile_management.models import Semester


# ===========================================================================
# Existing serializers (preserved, unchanged)
# ===========================================================================

class TimetableEntrySerializer(serializers.ModelSerializer):
    """
    Standard serializer for timetable entries.
    """
    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'section_id', 'subject_id', 'faculty_id', 'period_definition_id',
            'room_id', 'semester_id', 'notes', 'is_active', 'allocation_id'
        ]
        read_only_fields = ['id', 'allocation_id']


class TimetableDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer including relation data for displaying a timetable.
    """
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    faculty_name = serializers.CharField(source='faculty.get_full_name', read_only=True)
    period_number = serializers.IntegerField(source='period_definition.period_number', read_only=True)
    day_name = serializers.CharField(source='period_definition.get_day_of_week_display', read_only=True)
    start_time = serializers.TimeField(source='period_definition.start_time', read_only=True)
    end_time = serializers.TimeField(source='period_definition.end_time', read_only=True)
    room_name = serializers.CharField(source='room.room_number', read_only=True, allow_null=True)

    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'subject_name', 'subject_code', 'faculty_name',
            'period_number', 'day_name', 'start_time', 'end_time', 'room_name', 'notes'
        ]


class PeriodDefinitionSerializer(serializers.ModelSerializer):
    """
    Serializer for period slots.
    """
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = PeriodDefinition
        fields = ['id', 'period_number', 'day_name', 'start_time', 'end_time']


class BulkTimetableEntryInputSerializer(serializers.Serializer):
    """
    Input serializer for individual items in a bulk request.
    """
    subject_id = serializers.IntegerField(required=True)
    faculty_id = serializers.IntegerField(required=True)
    period_definition_id = serializers.IntegerField(required=True)
    room_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class SectionCreateTimetableSerializer(serializers.Serializer):
    """
    Serializer to handle creating multiple timetable entries for a specific section.
    """
    section_id = serializers.IntegerField(required=True)
    semester_id = serializers.IntegerField(required=True)
    entries = BulkTimetableEntryInputSerializer(many=True, required=True)


# ===========================================================================
# HOD Timetable Approval serializers
# ===========================================================================

class TimetableApprovalRequestSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.CharField(source='submitted_by.get_full_name', read_only=True)
    semester_label = serializers.SerializerMethodField(read_only=True)
    academic_year = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TimetableApprovalRequest
        fields = [
            'id',
            'status',
            'change_summary',
            'note',
            'slots',
            'submitted_by_name',
            'semester_label',
            'academic_year',
            'review_note',
            'reviewed_at',
            'created_at',
            'updated_at',
        ]

    def get_semester_label(self, obj) -> str:
        if not obj.semester:
            return 'N/A'
        return obj.semester.get_number_display()

    def get_academic_year(self, obj) -> str:
        if not obj.semester:
            return 'N/A'
        return obj.semester.academic_year.year_code


class TimetableApprovalRequestStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['PENDING', 'APPROVED', 'REJECTED'])
    review_note = serializers.CharField(required=False, allow_blank=True, default='')


# ===========================================================================
# SectionSubjectRequirement serializers
# ===========================================================================

class SectionSubjectRequirementSerializer(serializers.ModelSerializer):
    """
    Read/write serializer for a single SectionSubjectRequirement row.

    Write fields  : section_id, semester_id, subject_id, faculty_id, periods_per_week
    Display fields: subject_name, subject_code, subject_type, faculty_name
                    (all read-only, populated on list/retrieve)

    Usage
    -----
    POST   /timetable/requirements/          — create one requirement
    GET    /timetable/requirements/?section_id=&semester_id=  — list
    PATCH  /timetable/requirements/<id>/     — update periods_per_week or faculty
    DELETE /timetable/requirements/<id>/     — remove
    """

    # ── FKs (writable) ──────────────────────────────────────────────────────
    section_id  = serializers.PrimaryKeyRelatedField(
        source='section',
        queryset=Section.objects.all(),
        write_only=False,   # expose id in read output too
    )
    semester_id = serializers.PrimaryKeyRelatedField(
        source='semester',
        queryset=Semester.objects.all(),
        write_only=False,
    )
    subject_id  = serializers.PrimaryKeyRelatedField(
        source='subject',
        queryset=Subject.objects.filter(is_active=True),
        write_only=False,
    )
    faculty_id  = serializers.PrimaryKeyRelatedField(
        source='faculty',
        queryset=User.objects.filter(role__code='FACULTY', is_active=True),
        allow_null=True,
        required=False,
        write_only=False,
    )

    # ── Read-only display fields ─────────────────────────────────────────────
    subject_name = serializers.CharField(source='subject.name',         read_only=True)
    subject_code = serializers.CharField(source='subject.code',         read_only=True)
    subject_type = serializers.CharField(source='subject.subject_type', read_only=True)
    faculty_name = serializers.SerializerMethodField()

    class Meta:
        model  = SectionSubjectRequirement
        fields = [
            'id',
            'section_id',
            'semester_id',
            'subject_id',
            'subject_name',
            'subject_code',
            'subject_type',
            'faculty_id',
            'faculty_name',
            'periods_per_week',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at',
                            'subject_name', 'subject_code', 'subject_type', 'faculty_name']

    def get_faculty_name(self, obj) -> str | None:
        if obj.faculty:
            return obj.faculty.get_full_name()
        return None

    def validate_periods_per_week(self, value):
        if value < 1:
            raise serializers.ValidationError("periods_per_week must be at least 1.")
        if value > 10:
            raise serializers.ValidationError("periods_per_week cannot exceed 10.")
        return value

    def validate(self, data):
        """
        Prevent setting a LAB subject with 0 periods (lab slot is implicit from
        LabRotationSchedule, but the row still needs periods_per_week >= 1).
        """
        return data


class _SingleRequirementInputSerializer(serializers.Serializer):
    """
    One item inside a SectionSubjectRequirementBulkSerializer.
    """
    subject_id       = serializers.IntegerField()
    faculty_id       = serializers.IntegerField(required=False, allow_null=True)
    periods_per_week = serializers.IntegerField(min_value=1, max_value=10, default=1)


class SectionSubjectRequirementBulkSerializer(serializers.Serializer):
    """
    Accepts a batch of subject requirements for one section+semester in a
    single POST.  Mirrors the pattern used by SectionCreateTimetableSerializer.

    Request body:
    {
        "section_id":  <int>,
        "semester_id": <int>,
        "requirements": [
            {"subject_id": 1, "faculty_id": 5, "periods_per_week": 3},
            {"subject_id": 2, "faculty_id": 7, "periods_per_week": 2},
            ...
        ]
    }

    Behaviour:
    • For each entry, calls SectionSubjectRequirement.objects.update_or_create()
      keyed on (section, semester, subject) so the endpoint is idempotent.
    • Returns a list of the resulting IDs.
    """

    section_id   = serializers.IntegerField()
    semester_id  = serializers.IntegerField()
    requirements = _SingleRequirementInputSerializer(many=True, min_length=1)

    def validate_section_id(self, value):
        if not Section.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f"Section {value} does not exist.")
        return value

    def validate_semester_id(self, value):
        if not Semester.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f"Semester {value} does not exist.")
        return value

    def validate_requirements(self, items):
        seen_subjects: set[int] = set()
        for item in items:
            sid = item['subject_id']
            if sid in seen_subjects:
                raise serializers.ValidationError(
                    f"subject_id {sid} appears more than once in the list."
                )
            seen_subjects.add(sid)
            if not Subject.objects.filter(pk=sid, is_active=True).exists():
                raise serializers.ValidationError(
                    f"Subject {sid} does not exist or is inactive."
                )
            fid = item.get('faculty_id')
            if fid and not User.objects.filter(pk=fid, role__code='FACULTY', is_active=True).exists():
                raise serializers.ValidationError(
                    f"Faculty {fid} does not exist, is inactive, or is not a faculty member."
                )
        return items


# ===========================================================================
# RoomMaintenanceBlock serializer
# ===========================================================================

class RoomMaintenanceBlockSerializer(serializers.ModelSerializer):
    """
    Read/write serializer for RoomMaintenanceBlock.

    Write fields  : room_id, start_date, end_date, reason, is_active
    Display fields: room_number, room_building (read-only)

    Usage
    -----
    POST   /timetable/maintenance/             — create a block
    GET    /timetable/maintenance/?room_id=    — list active blocks for a room
    PATCH  /timetable/maintenance/<id>/        — update dates / reason / is_active
    DELETE /timetable/maintenance/<id>/        — remove

    After creating, call POST /timetable/reschedule/ or use the admin
    trigger_reschedule action to apply the rescheduling.
    """

    room_id      = serializers.PrimaryKeyRelatedField(
        source='room',
        queryset=Room.objects.filter(is_active=True),
    )
    room_number  = serializers.CharField(source='room.room_number',  read_only=True)
    room_building = serializers.CharField(source='room.building',    read_only=True)

    class Meta:
        model  = RoomMaintenanceBlock
        fields = [
            'id',
            'room_id',
            'room_number',
            'room_building',
            'start_date',
            'end_date',
            'reason',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'room_number', 'room_building', 'created_at', 'updated_at']

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )
        return data


# ===========================================================================
# Section Combining (Option A)
# ===========================================================================


class DepartmentSectionCombinePolicySerializer(serializers.ModelSerializer):
    department_id = serializers.PrimaryKeyRelatedField(
        source='department',
        queryset=Department.objects.filter(is_active=True),
    )
    allowed_partner_department_ids = serializers.PrimaryKeyRelatedField(
        source='allowed_partner_departments',
        queryset=Department.objects.filter(is_active=True),
        many=True,
        required=False,
    )

    class Meta:
        model = DepartmentSectionCombinePolicy
        fields = [
            'id',
            'department_id',
            'enabled',
            'max_sections',
            'same_course_only',
            'allow_cross_department',
            'allowed_partner_department_ids',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def validate(self, data):
        allow_cross = data.get('allow_cross_department')
        partners = data.get('allowed_partner_departments')
        if allow_cross is False and partners:
            raise serializers.ValidationError(
                {"allowed_partner_department_ids": "Must be empty when allow_cross_department is false."}
            )
        max_sections = data.get('max_sections')
        if max_sections and max_sections > 2:
            raise serializers.ValidationError({"max_sections": "Cannot exceed 2."})
        return data


class CombinedClassSessionSerializer(serializers.ModelSerializer):
    # Writable FK ids
    semester_id = serializers.PrimaryKeyRelatedField(
        source='semester',
        queryset=Semester.objects.all(),
    )
    period_definition_id = serializers.PrimaryKeyRelatedField(
        source='period_definition',
        queryset=PeriodDefinition.objects.all(),
    )
    subject_id = serializers.PrimaryKeyRelatedField(
        source='subject',
        queryset=Subject.objects.filter(is_active=True),
    )
    faculty_id = serializers.PrimaryKeyRelatedField(
        source='faculty',
        queryset=User.objects.filter(role__code='FACULTY', is_active=True),
        allow_null=True,
        required=False,
    )
    room_id = serializers.PrimaryKeyRelatedField(
        source='room',
        queryset=Room.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )

    # Sections
    section_ids = serializers.PrimaryKeyRelatedField(
        source='sections',
        queryset=Section.objects.all(),
        many=True,
        write_only=True,
    )
    sections = serializers.SerializerMethodField(read_only=True)

    # Read-only display fields
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    faculty_name = serializers.SerializerMethodField(read_only=True)
    period_number = serializers.IntegerField(source='period_definition.period_number', read_only=True)
    day_name = serializers.CharField(source='period_definition.get_day_of_week_display', read_only=True)
    start_time = serializers.TimeField(source='period_definition.start_time', read_only=True)
    end_time = serializers.TimeField(source='period_definition.end_time', read_only=True)
    room_name = serializers.CharField(source='room.room_number', read_only=True, allow_null=True)

    supersede_timetable_entries = serializers.BooleanField(
        write_only=True,
        required=False,
        default=True,
        help_text="If true, deactivates matching TimetableEntry rows for each section at this slot.",
    )

    class Meta:
        model = CombinedClassSession
        fields = [
            'id',
            'semester_id',
            'period_definition_id',
            'subject_id',
            'subject_name',
            'subject_code',
            'faculty_id',
            'faculty_name',
            'room_id',
            'room_name',
            'allocation_id',
            'section_ids',
            'sections',
            'period_number',
            'day_name',
            'start_time',
            'end_time',
            'is_active',
            'notes',
            'created_by',
            'created_at',
            'updated_at',
            'supersede_timetable_entries',
        ]
        read_only_fields = [
            'id',
            'allocation_id',
            'sections',
            'subject_name',
            'subject_code',
            'faculty_name',
            'period_number',
            'day_name',
            'start_time',
            'end_time',
            'room_name',
            'created_by',
            'created_at',
            'updated_at',
        ]

    def get_faculty_name(self, obj):
        if obj.faculty:
            return obj.faculty.get_full_name()
        return None

    def get_sections(self, obj):
        return [
            {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "course_id": s.course_id,
                "department_id": s.course.department_id,
                "year": s.year,
            }
            for s in obj.sections.select_related('course', 'course__department').all()
        ]

    def validate(self, data):
        sections = data.get('sections') or []
        if len(sections) != 2:
            raise serializers.ValidationError({"section_ids": "Exactly 2 sections are required."})

        section_1, section_2 = sections[0], sections[1]
        dept_1 = section_1.course.department
        dept_2 = section_2.course.department

        # Department policies must allow combining.
        try:
            policy_1 = DepartmentSectionCombinePolicy.objects.get(department=dept_1)
        except DepartmentSectionCombinePolicy.DoesNotExist:
            raise serializers.ValidationError(
                {"section_ids": f"No combine policy configured for department {dept_1.code}."}
            )
        if not policy_1.enabled or policy_1.max_sections < 2:
            raise serializers.ValidationError(
                {"section_ids": f"Combining is disabled for department {dept_1.code}."}
            )

        # Cross-department checks.
        if dept_1.id != dept_2.id:
            if not policy_1.allow_cross_department:
                raise serializers.ValidationError({"section_ids": "Cross-department combining is not allowed."})
            if not policy_1.allowed_partner_departments.filter(id=dept_2.id).exists():
                raise serializers.ValidationError({"section_ids": "Partner department is not allowed by policy."})

            # Partner department must also have an enabled reciprocal policy.
            try:
                policy_2 = DepartmentSectionCombinePolicy.objects.get(department=dept_2)
            except DepartmentSectionCombinePolicy.DoesNotExist:
                raise serializers.ValidationError(
                    {"section_ids": f"No combine policy configured for department {dept_2.code}."}
                )
            if not policy_2.enabled or policy_2.max_sections < 2:
                raise serializers.ValidationError(
                    {"section_ids": f"Combining is disabled for department {dept_2.code}."}
                )
            if not policy_2.allow_cross_department:
                raise serializers.ValidationError({"section_ids": "Partner department policy disallows cross-department combining."})
            if not policy_2.allowed_partner_departments.filter(id=dept_1.id).exists():
                raise serializers.ValidationError({"section_ids": "Partner department policy does not allow this department."})

        # Same-course enforcement (department 1 policy governs).
        if policy_1.same_course_only and section_1.course_id != section_2.course_id:
            raise serializers.ValidationError({"section_ids": "Only sections from the same course may be combined."})

        # Basic sanity: combine should usually be within the same year.
        if section_1.year != section_2.year:
            raise serializers.ValidationError({"section_ids": "Sections must be from the same year to be combined."})

        return data
