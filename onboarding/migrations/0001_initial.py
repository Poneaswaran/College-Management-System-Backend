# Generated manually for onboarding app
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import onboarding.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("profile_management", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnboardingTaskLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_id", models.CharField(default=uuid.uuid4, max_length=100, unique=True)),
                ("entity_type", models.CharField(choices=[("STUDENT", "Student"), ("FACULTY", "Faculty")], default="STUDENT", max_length=20)),
                ("file", models.FileField(upload_to=onboarding.models.onboarding_upload_file_path)),
                ("file_hash", models.CharField(db_index=True, max_length=64)),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("processed", models.PositiveIntegerField(default=0)),
                ("success_count", models.PositiveIntegerField(default=0)),
                ("failure_count", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("PROCESSING", "Processing"), ("PARTIAL", "Partial"), ("COMPLETED", "Completed"), ("FAILED", "Failed")], default="PENDING", max_length=20)),
                ("error_log", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="onboarding_task_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="FacultyIDCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("READY", "Ready"), ("ISSUED", "Issued"), ("REVOKED", "Revoked")], default="PENDING", max_length=20)),
                ("card_number", models.CharField(db_index=True, max_length=64, unique=True)),
                ("qr_token", models.TextField(blank=True)),
                ("qr_image", models.ImageField(blank=True, null=True, upload_to=onboarding.models.id_card_qr_path)),
                ("pdf_file", models.FileField(blank=True, null=True, upload_to=onboarding.models.id_card_pdf_path)),
                ("generated_at", models.DateTimeField(blank=True, null=True)),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("faculty_profile", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="id_card", to="profile_management.facultyprofile")),
                ("generated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generated_faculty_id_cards", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-generated_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="StudentIDCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("READY", "Ready"), ("ISSUED", "Issued"), ("REVOKED", "Revoked")], default="PENDING", max_length=20)),
                ("card_number", models.CharField(db_index=True, max_length=64, unique=True)),
                ("qr_token", models.TextField(blank=True)),
                ("qr_image", models.ImageField(blank=True, null=True, upload_to=onboarding.models.id_card_qr_path)),
                ("pdf_file", models.FileField(blank=True, null=True, upload_to=onboarding.models.id_card_pdf_path)),
                ("generated_at", models.DateTimeField(blank=True, null=True)),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("generated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="generated_student_id_cards", to=settings.AUTH_USER_MODEL)),
                ("student_profile", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="id_card", to="profile_management.studentprofile")),
            ],
            options={
                "ordering": ["-generated_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="FacultyOnboardingRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(db_index=True, max_length=40, unique=True)),
                ("is_hod", models.BooleanField(default=False)),
                ("subject_codes", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("faculty_profile", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="onboarding_record", to="profile_management.facultyprofile")),
            ],
            options={
                "ordering": ["employee_id"],
            },
        ),
        migrations.AddIndex(
            model_name="onboardingtasklog",
            index=models.Index(fields=["entity_type", "status"], name="onboarding__entity__a4db8e_idx"),
        ),
        migrations.AddIndex(
            model_name="onboardingtasklog",
            index=models.Index(fields=["uploaded_by", "created_at"], name="onboarding__uploade_a6bf1d_idx"),
        ),
    ]
