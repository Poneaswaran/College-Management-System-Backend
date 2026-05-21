from rest_framework import serializers

from core.models import Department
from profile_management.models import StudentProfile

from .models import (
    Company,
    PlacementDrive,
    StudentApplication,
    PlacementRound,
    RoundResult,
    PlacementOffer,
    StudentPlacementProfile,
)


class DepartmentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name"]


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "industry",
            "website",
            "logo",
            "contact_person",
            "email",
            "phone",
            "package_range",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if instance.logo and request is not None:
            data["logo"] = request.build_absolute_uri(instance.logo.url)
        return data


class CompanyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "industry", "logo", "package_range"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if instance.logo and request is not None:
            data["logo"] = request.build_absolute_uri(instance.logo.url)
        return data


class PlacementDriveSerializer(serializers.ModelSerializer):
    company = CompanyListSerializer(read_only=True)
    eligible_branches = DepartmentSummarySerializer(many=True, read_only=True)
    applications_count = serializers.SerializerMethodField()
    selected_count = serializers.SerializerMethodField()

    class Meta:
        model = PlacementDrive
        fields = [
            "id",
            "company",
            "title",
            "drive_type",
            "job_role",
            "job_description",
            "required_skills",
            "min_cgpa",
            "eligible_branches",
            "eligible_batch_year",
            "application_deadline",
            "drive_date",
            "venue",
            "package_offered",
            "bond_years",
            "status",
            "is_active",
            "created_at",
            "updated_at",
            "applications_count",
            "selected_count",
        ]

    def get_applications_count(self, obj):
        return obj.applications.filter(is_active=True).count()

    def get_selected_count(self, obj):
        return obj.applications.filter(is_active=True, status="selected").count()


class PlacementDriveCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementDrive
        fields = [
            "company",
            "title",
            "drive_type",
            "job_role",
            "job_description",
            "required_skills",
            "min_cgpa",
            "eligible_branches",
            "eligible_batch_year",
            "application_deadline",
            "drive_date",
            "venue",
            "package_offered",
            "bond_years",
            "status",
            "is_active",
        ]


class StudentSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = ["register_number", "name"]

    def get_name(self, obj):
        parts = [obj.first_name, obj.last_name]
        return " ".join([part for part in parts if part])


class StudentApplicationSerializer(serializers.ModelSerializer):
    drive = PlacementDriveSerializer(read_only=True)
    student = StudentSummarySerializer(read_only=True)

    class Meta:
        model = StudentApplication
        fields = [
            "id",
            "student",
            "drive",
            "resume",
            "cover_letter",
            "status",
            "applied_at",
            "updated_at",
            "notes",
            "is_active",
        ]


class StudentApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentApplication
        fields = ["drive", "resume", "cover_letter"]


class PlacementRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementRound
        fields = [
            "id",
            "drive",
            "round_number",
            "round_type",
            "scheduled_at",
            "venue",
            "instructions",
            "is_active",
            "created_at",
            "updated_at",
        ]


class RoundResultSerializer(serializers.ModelSerializer):
    notes = serializers.CharField(source="interviewer_notes", required=False, allow_blank=True)

    class Meta:
        model = RoundResult
        fields = [
            "id",
            "application",
            "round",
            "result",
            "score",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]


class BulkRoundResultSerializer(serializers.Serializer):
    results = RoundResultSerializer(many=True)


class ApplicationSummarySerializer(serializers.ModelSerializer):
    student = StudentSummarySerializer(read_only=True)
    drive_title = serializers.CharField(source="drive.title", read_only=True)
    company_name = serializers.CharField(source="drive.company.name", read_only=True)

    class Meta:
        model = StudentApplication
        fields = ["id", "student", "drive_title", "company_name", "status"]


class PlacementOfferSerializer(serializers.ModelSerializer):
    application = ApplicationSummarySerializer(read_only=True)

    class Meta:
        model = PlacementOffer
        fields = [
            "id",
            "application",
            "offer_letter",
            "ctc",
            "joining_date",
            "location",
            "is_accepted",
            "accepted_at",
            "is_active",
            "created_at",
            "updated_at",
        ]


class PlacementOfferCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementOffer
        fields = ["application", "ctc", "joining_date", "location", "offer_letter"]


class StudentPlacementProfileSerializer(serializers.ModelSerializer):
    placed_company_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentPlacementProfile
        fields = [
            "id",
            "student",
            "resume",
            "skills",
            "portfolio_url",
            "linkedin_url",
            "github_url",
            "is_placed",
            "placed_company",
            "placed_company_name",
            "placed_package",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_placed_company_name(self, obj):
        if obj.placed_company:
            return obj.placed_company.name
        return ""


class BulkShortlistSerializer(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.IntegerField(min_value=1))


class AnalyticsBranchSerializer(serializers.Serializer):
    branch = serializers.CharField()
    placed = serializers.IntegerField()
    total = serializers.IntegerField()


class AnalyticsDriveSerializer(serializers.Serializer):
    drive = serializers.CharField()
    applied = serializers.IntegerField()
    selected = serializers.IntegerField()


class AnalyticsCompanySerializer(serializers.Serializer):
    company = serializers.CharField()
    hired = serializers.IntegerField()


class AnalyticsSerializer(serializers.Serializer):
    total_drives = serializers.IntegerField()
    total_companies = serializers.IntegerField()
    students_eligible = serializers.IntegerField()
    students_applied = serializers.IntegerField()
    students_placed = serializers.IntegerField()
    placement_percentage = serializers.FloatField()
    avg_package = serializers.FloatField()
    highest_package = serializers.FloatField()
    branch_wise = AnalyticsBranchSerializer(many=True)
    drive_wise = AnalyticsDriveSerializer(many=True)
    top_companies = AnalyticsCompanySerializer(many=True)
