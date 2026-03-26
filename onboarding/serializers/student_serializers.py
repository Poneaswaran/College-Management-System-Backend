from rest_framework import serializers

from onboarding.models import OnboardingTaskLog, StudentIDCard


class StudentBulkUploadSerializer(serializers.Serializer):
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


class StudentIDCardSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(source="student_profile.id", read_only=True)
    registration_number = serializers.CharField(source="student_profile.register_number", read_only=True)

    class Meta:
        model = StudentIDCard
        fields = [
            "student_id",
            "registration_number",
            "card_number",
            "status",
            "qr_image",
            "pdf_file",
            "generated_at",
            "issued_at",
            "revoked_at",
        ]
