from rest_framework import serializers

from profile_management.models import FacultyProfile, StudentProfile, IDCardTemplate


class IDCardTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = IDCardTemplate
        fields = "__all__"


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
            "departmentName",
            "fullName",
            "email",
            "courseName",
            "sectionName",
            "registerNumber",
            "rollNumber",
            "profilePhoto",
        ]

    def get_fullName(self, obj):
        return f"{obj.first_name} {obj.last_name or ''}".strip()

    fullName = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    departmentName = serializers.CharField(source="department.name", read_only=True)
    courseName = serializers.CharField(source="course.name", read_only=True)
    sectionName = serializers.CharField(source="section.name", read_only=True)
    registerNumber = serializers.CharField(source="register_number", read_only=True)
    rollNumber = serializers.CharField(source="roll_number", read_only=True)
    profilePhoto = serializers.ImageField(source="profile_photo", read_only=True)


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
    email = serializers.EmailField(source="user.email", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = FacultyProfile
        fields = [
            "id",
            "user",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "address",
            "date_of_birth",
            "gender",
            "department",
            "department_name",
            "designation",
            "qualifications",
            "specialization",
            "joining_date",
            "office_hours",
            "teaching_load",
            "profile_photo",
            "research_interests",
            "experience",
            "is_active",
            "updated_at",
        ]


class FacultyProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    address = serializers.CharField(required=False)
    date_of_birth = serializers.DateField(required=False)
    gender = serializers.CharField(required=False)
    designation = serializers.CharField(required=False)
    qualifications = serializers.CharField(required=False)
    specialization = serializers.CharField(required=False)
    office_hours = serializers.CharField(required=False)
    teaching_load = serializers.IntegerField(required=False)
    research_interests = serializers.ListField(child=serializers.CharField(), required=False)
    experience = serializers.CharField(required=False)
    department_id = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)
    user_id = serializers.IntegerField(required=False)


class HODFacultyListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=False)
    designation = serializers.CharField(required=False, allow_blank=False)
    is_active = serializers.BooleanField(required=False)
    school_id = serializers.IntegerField(required=False)
    department_id = serializers.IntegerField(required=False)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100, default=10)


class HODFacultyListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    department_id = serializers.IntegerField(allow_null=True)
    department_name = serializers.CharField(allow_null=True)
    designation = serializers.CharField()
    specialization = serializers.CharField()
    joining_date = serializers.DateField()
    office_hours = serializers.CharField(allow_blank=True)
    teaching_load = serializers.IntegerField()
    is_active = serializers.BooleanField()
    profile_photo = serializers.ImageField(read_only=True)


class HODFacultyListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    results = HODFacultyListItemSerializer(many=True)


class ParentOtpRequestSerializer(serializers.Serializer):
    register_number = serializers.CharField(required=True)


class ParentOtpVerifySerializer(serializers.Serializer):
    register_number = serializers.CharField(required=True)
    otp = serializers.CharField(required=True)
    relationship = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)


class PublicationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    journal = serializers.CharField()
    year = serializers.IntegerField()
    type = serializers.CharField()
    doi = serializers.CharField(allow_null=True)


class DepartmentStatsSerializer(serializers.Serializer):
    totalFaculty = serializers.IntegerField(source="total_faculty")
    totalStudents = serializers.IntegerField(source="total_students")
    activeCourses = serializers.IntegerField(source="active_courses")
    researchProjects = serializers.IntegerField(source="research_projects")


class HODProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    fullName = serializers.CharField(source="full_name")
    email = serializers.EmailField()
    phone = serializers.CharField(allow_null=True)
    dateOfBirth = serializers.DateField(source="date_of_birth", allow_null=True)
    gender = serializers.CharField(allow_null=True)
    address = serializers.CharField(allow_null=True)
    profilePhoto = serializers.CharField(source="profile_photo", allow_null=True)
    employeeId = serializers.CharField(source="employee_id")
    designation = serializers.CharField()
    joiningDate = serializers.DateField(source="joining_date")
    hodSince = serializers.DateField(source="hod_since", allow_null=True)
    academicStatus = serializers.CharField(source="academic_status")
    qualifications = serializers.CharField()
    specialization = serializers.CharField()
    experience = serializers.CharField(allow_null=True)
    researchInterests = serializers.ListField(child=serializers.CharField(), source="research_interests")
    department = serializers.DictField()
    departmentStats = DepartmentStatsSerializer(source="department_stats")
    publications = PublicationSerializer(many=True)


class HODProfileUpdateSerializer(serializers.Serializer):
    firstName = serializers.CharField(required=False, source="first_name")
    lastName = serializers.CharField(required=False, source="last_name")
    phone = serializers.CharField(required=False)
    address = serializers.CharField(required=False)
    researchInterests = serializers.ListField(child=serializers.CharField(), required=False, source="research_interests")
