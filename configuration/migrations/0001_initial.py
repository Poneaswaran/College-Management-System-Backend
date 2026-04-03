from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Configuration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=150, unique=True)),
                ("value", models.JSONField()),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["key"]},
        ),
        migrations.AddIndex(
            model_name="configuration",
            index=models.Index(fields=["key", "is_active"], name="configurati_key_4f631a_idx"),
        ),
    ]
