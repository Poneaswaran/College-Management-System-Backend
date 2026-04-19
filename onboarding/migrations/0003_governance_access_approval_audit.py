from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0002_hardening_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("profile_management", "0005_facultyprofile_first_name_facultyprofile_last_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnboardingAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(db_index=True, max_length=80)),
                (
                    "entity_type",
                    models.CharField(
                        choices=[("STUDENT", "Student"), ("FACULTY", "Faculty")],
                        default="STUDENT",
                        max_length=20,
                    ),
                ),
                ("entity_id", models.CharField(blank=True, max_length=120)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="onboarding_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="TemporaryOnboardingAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "scope",
                    models.CharField(
                        choices=[("STUDENT", "Student"), ("FACULTY", "Faculty"), ("ALL", "All")],
                        default="ALL",
                        max_length=20,
                    ),
                ),
                ("can_bulk_upload", models.BooleanField(default=True)),
                ("can_retry", models.BooleanField(default=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "faculty_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="temporary_onboarding_accesses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "granted_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="granted_onboarding_accesses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="StudentOnboardingApproval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("remarks", models.TextField(blank=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("rejected_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_student_onboarding_approvals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="requested_student_onboarding_approvals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student_profile",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="onboarding_approval",
                        to="profile_management.studentprofile",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.AddIndex(
            model_name="onboardingauditlog",
            index=models.Index(
                fields=["entity_type", "action", "created_at"],
                name="onboarding__entity__539dee_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="onboardingauditlog",
            index=models.Index(
                fields=["actor", "created_at"],
                name="onboarding__actor_i_ea4fcb_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="temporaryonboardingaccess",
            index=models.Index(
                fields=["faculty_user", "is_active", "expires_at"],
                name="onboarding__faculty_034c0a_idx",
            ),
        ),
    ]
