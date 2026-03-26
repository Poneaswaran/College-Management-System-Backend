from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("configuration", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="configuration",
            name="configurati_key_4f631a_idx",
        ),
        migrations.AddField(
            model_name="configuration",
            name="sub_app",
            field=models.CharField(default="global", max_length=50),
        ),
        migrations.AddField(
            model_name="configuration",
            name="tenant_key",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="configuration",
            name="key",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterModelOptions(
            name="configuration",
            options={"ordering": ["sub_app", "key"]},
        ),
        migrations.AddConstraint(
            model_name="configuration",
            constraint=models.UniqueConstraint(
                fields=("tenant_key", "sub_app", "key"),
                name="unique_config_per_tenant_subapp_key",
            ),
        ),
        migrations.AddIndex(
            model_name="configuration",
            index=models.Index(
                fields=["tenant_key", "sub_app", "key", "is_active"],
                name="configurati_tenant__aad67b_idx",
            ),
        ),
        migrations.CreateModel(
            name="FeatureFlag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant_key", models.CharField(blank=True, max_length=100, null=True)),
                ("sub_app", models.CharField(default="global", max_length=50)),
                ("key", models.CharField(max_length=150)),
                ("is_enabled", models.BooleanField(default=False)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["sub_app", "key"]},
        ),
        migrations.AddConstraint(
            model_name="featureflag",
            constraint=models.UniqueConstraint(
                fields=("tenant_key", "sub_app", "key"),
                name="unique_flag_per_tenant_subapp_key",
            ),
        ),
        migrations.AddIndex(
            model_name="featureflag",
            index=models.Index(
                fields=["tenant_key", "sub_app", "key", "is_active"],
                name="configurati_tenant__9184b5_idx",
            ),
        ),
    ]
