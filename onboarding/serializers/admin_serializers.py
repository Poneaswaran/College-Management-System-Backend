from rest_framework import serializers

from onboarding.models import OnboardingDraft, StudentOnboardingApproval, FacultyOnboardingApproval, TemporaryOnboardingAccess


class TemporaryAccessGrantSerializer(serializers.Serializer):
    faculty_user_id = serializers.IntegerField()
    scope = serializers.ChoiceField(choices=TemporaryOnboardingAccess.SCOPE_CHOICES)
    expires_at = serializers.DateTimeField()
    can_bulk_upload = serializers.BooleanField(required=False, default=True)
    can_retry = serializers.BooleanField(required=False, default=True)


class TemporaryAccessRevokeSerializer(serializers.Serializer):
    access_id = serializers.IntegerField()


class StudentApprovalActionSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class FacultyApprovalActionSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class BulkApprovalActionSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField())
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class StudentOnboardingApprovalSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(source="student_profile.id", read_only=True)
    registration_number = serializers.CharField(source="student_profile.register_number", read_only=True)
    student_name = serializers.CharField(source="student_profile.full_name", read_only=True)

    class Meta:
        model = StudentOnboardingApproval
        fields = [
            "id",
            "student_id",
            "registration_number",
            "student_name",
            "status",
            "remarks",
            "created_at",
            "updated_at",
            "approved_at",
            "rejected_at",
        ]


class FacultyOnboardingApprovalSerializer(serializers.ModelSerializer):
    faculty_id = serializers.IntegerField(source="faculty_profile.id", read_only=True)
    employee_id = serializers.SerializerMethodField(read_only=True)
    faculty_name = serializers.CharField(source="faculty_profile.full_name", read_only=True)

    class Meta:
        model = FacultyOnboardingApproval
        fields = [
            "id",
            "faculty_id",
            "employee_id",
            "faculty_name",
            "status",
            "remarks",
            "created_at",
            "updated_at",
            "approved_at",
            "rejected_at",
        ]

    def get_employee_id(self, obj):
        from onboarding.models import FacultyOnboardingRecord
        record = FacultyOnboardingRecord.objects.filter(faculty_profile=obj.faculty_profile).first()
        return record.employee_id if record else "UNKNOWN"


class StudentManualOnboardingSerializer(serializers.Serializer):
    registration_number = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField()
    email = serializers.EmailField()
    department_code = serializers.CharField()
    course_code = serializers.CharField()
    section_name = serializers.CharField()
    section_year = serializers.IntegerField()
    academic_year_code = serializers.CharField()
    semester = serializers.IntegerField(required=False, default=1)
    admission_date = serializers.DateField(required=False, allow_null=True)


class FacultyManualOnboardingSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField()
    department_code = serializers.CharField()
    designation = serializers.CharField()
    qualifications = serializers.CharField()
    specialization = serializers.CharField()
    joining_date = serializers.DateField()
    office_hours = serializers.CharField(required=False, allow_blank=True, default="")
    teaching_load = serializers.IntegerField(required=False, default=0)
    is_hod = serializers.BooleanField(required=False, default=False)
    subject_codes = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )


class OnboardingDraftCreateSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=["STUDENT", "FACULTY"])
    payload = serializers.JSONField(required=False, default=dict)


class OnboardingDraftUpdateSerializer(serializers.Serializer):
    payload = serializers.JSONField(required=False)


class OnboardingDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingDraft
        fields = [
            "id",
            "entity_type",
            "payload",
            "status",
            "created_by",
            "updated_by",
            "submitted_by",
            "submitted_at",
            "created_at",
            "updated_at",
        ]
