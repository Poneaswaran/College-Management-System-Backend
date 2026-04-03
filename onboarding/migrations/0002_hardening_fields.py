from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions
import django.db.models.query_utils


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="onboardingtasklog",
            name="dry_run",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="onboardingtasklog",
            name="idempotency_key",
            field=models.CharField(default="", max_length=100, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="onboardingtasklog",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="onboardingtasklog",
            name="is_retry",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="onboardingtasklog",
            name="retry_attempt",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="onboardingtasklog",
            name="source_task",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="retry_tasks", to="onboarding.onboardingtasklog"),
        ),
        migrations.AddField(
            model_name="onboardingtasklog",
            name="processing_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="onboardingtasklog",
            name="processing_duration_ms",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="onboardingtasklog",
            name="success_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="onboardingtasklog",
            name="failure_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddIndex(
            model_name="onboardingtasklog",
            index=models.Index(fields=["is_active", "entity_type", "created_at"], name="onboarding__is_acti_965efb_idx"),
        ),
        migrations.AddConstraint(
            model_name="onboardingtasklog",
            constraint=models.UniqueConstraint(condition=django.db.models.query_utils.Q(("dry_run", False), ("is_active", True), ("is_retry", False)), fields=("entity_type", "file_hash"), name="uq_onboarding_entity_filehash_active"),
        ),
    ]
