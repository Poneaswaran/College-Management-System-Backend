from rest_framework import serializers

from profile_management.models import FacultyProfile, StudentProfile


class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "first_name",
            "last_name",
            "phone",
            "date_of_birth",
            "gender",
            "address",
            "profile_photo",
            "register_number",
            "roll_number",
            "department",
            "course",
            "section",
            "year",
            "semester",
            "admission_date",
            "academic_status",
            "guardian_name",
            "guardian_relationship",
            "guardian_phone",
            "guardian_email",
            "aadhar_number",
            "id_proof_type",
            "id_proof_number",
            "is_active",
            "profile_completed",
            "current_gpa",
            "updated_at",
        ]


class StudentProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=False)
    last_name = serializers.CharField(required=False, allow_blank=False)
    phone = serializers.CharField(required=False, allow_blank=False)
    date_of_birth = serializers.DateField(required=False)
    gender = serializers.CharField(required=False, allow_blank=False)
    address = serializers.CharField(required=False, allow_blank=False)
    guardian_name = serializers.CharField(required=False, allow_blank=False)
    guardian_relationship = serializers.CharField(required=False, allow_blank=False)
    guardian_phone = serializers.CharField(required=False, allow_blank=False)
    guardian_email = serializers.EmailField(required=False, allow_blank=False)


class StudentProfilePhotoUpdateSerializer(StudentProfileUpdateSerializer):
    profile_picture_base64 = serializers.CharField(required=False, allow_blank=False)


class StudentAdminUpdateSerializer(serializers.Serializer):
    roll_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    year = serializers.IntegerField(required=False)
    semester = serializers.IntegerField(required=False)
    section_id = serializers.IntegerField(required=False)
    admission_date = serializers.DateField(required=False, allow_null=True)
    academic_status = serializers.CharField(required=False)
    aadhar_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    id_proof_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    id_proof_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class FacultyProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = FacultyProfile
        fields = [
            "id",
            "user",
            "first_name",
            "last_name",
            "full_name",
            "department",
            "designation",
            "qualifications",
            "specialization",
            "joining_date",
            "office_hours",
            "teaching_load",
            "is_active",
            "updated_at",
        ]


class FacultyProfileUpdateSerializer(serializers.Serializer):
    designation = serializers.CharField(required=False)
    qualifications = serializers.CharField(required=False)
    specialization = serializers.CharField(required=False)
    office_hours = serializers.CharField(required=False)
    teaching_load = serializers.IntegerField(required=False)
    department_id = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)
    user_id = serializers.IntegerField(required=False)


class ParentOtpRequestSerializer(serializers.Serializer):
    register_number = serializers.CharField(required=True)


class ParentOtpVerifySerializer(serializers.Serializer):
    register_number = serializers.CharField(required=True)
    otp = serializers.CharField(required=True)
    relationship = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
