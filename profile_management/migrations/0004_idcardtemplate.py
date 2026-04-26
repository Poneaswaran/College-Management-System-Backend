from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profile_management", "0003_alter_facultyprofile_department"),
    ]

    operations = [
        migrations.CreateModel(
            name="IDCardTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="default", editable=False, help_text="Internal sentinel — always 'default'. Do not change.", max_length=50, unique=True)),
                ("student_primary_color", models.CharField(default="#2563eb", help_text="Hex colour for student card header & accents (e.g. #2563eb)", max_length=7)),
                ("student_header_text_color", models.CharField(default="#ffffff", help_text="Hex colour for text inside the student card header", max_length=7)),
                ("student_background_color", models.CharField(default="#f8fafc", help_text="Hex colour for the student card background", max_length=7)),
                ("student_text_color", models.CharField(default="#111827", help_text="Hex colour for main body text on student cards", max_length=7)),
                ("student_label_color", models.CharField(default="#6b7280", help_text="Hex colour for field labels (e.g. REG NO, DEPT)", max_length=7)),
                ("faculty_primary_color", models.CharField(default="#059669", help_text="Hex colour for faculty card header & accents (e.g. #059669)", max_length=7)),
                ("faculty_header_text_color", models.CharField(default="#ffffff", help_text="Hex colour for text inside the faculty card header", max_length=7)),
                ("faculty_background_color", models.CharField(default="#f8fafc", help_text="Hex colour for the faculty card background", max_length=7)),
                ("faculty_text_color", models.CharField(default="#111827", help_text="Hex colour for main body text on faculty cards", max_length=7)),
                ("faculty_label_color", models.CharField(default="#6b7280", help_text="Hex colour for field labels on faculty cards", max_length=7)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "ID Card Template", "verbose_name_plural": "ID Card Templates"},
        ),
    ]
