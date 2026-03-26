from rest_framework import serializers

from onboarding.models import FacultyIDCard, OnboardingTaskLog


class FacultyBulkUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class OnboardingTaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingTaskLog
        fields = [
            "task_id",
            "entity_type",
            "idempotency_key",
            "is_active",
            "dry_run",
            "is_retry",
            "retry_attempt",
            "status",
            "total_rows",
            "processed",
            "success_count",
            "failure_count",
            "processing_started_at",
            "processing_duration_ms",
            "success_rate",
            "failure_rate",
            "error_log",
            "created_at",
            "updated_at",
            "completed_at",
        ]


class FacultyIDCardSerializer(serializers.ModelSerializer):
    faculty_id = serializers.IntegerField(source="faculty_profile.id", read_only=True)

    class Meta:
        model = FacultyIDCard
        fields = [
            "faculty_id",
            "card_number",
            "status",
            "qr_image",
            "pdf_file",
            "generated_at",
            "issued_at",
            "revoked_at",
        ]
