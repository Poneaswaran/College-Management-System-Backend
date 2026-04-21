from django.db import migrations
INITIAL_FLAGS = [
    ("timetable_assignment", "HOD can assign faculty to timetable slots", True),
    ("pdf_export",           "Export timetable as PDF",                   True),
    ("ai_copilot",           "AI timetable copilot chat interface",       False),
    ("schedule_audit",       "AI schedule health audit",                  False),
    ("exam_module",          "Exam scheduling and result management",     False),
    ("attendance_analytics", "Advanced attendance trend analytics",       False),
    ("faculty_workload",     "Faculty workload distribution reports",     True),
    ("leave_approval",       "HOD faculty leave approval workflow",       True),
    ("grade_submission",     "Faculty grade submission module",           True),
    ("study_materials",      "Study materials upload and access",         True),
]
def seed_flags(apps, schema_editor):
    FeatureFlag = apps.get_model("configuration", "FeatureFlag")
    for key, description, is_enabled_globally in INITIAL_FLAGS:
        FeatureFlag.objects.get_or_create(
            key=key,
            defaults={
                "description": description,
                "is_enabled_globally": is_enabled_globally,
            }
        )
def unseed_flags(apps, schema_editor):
    FeatureFlag = apps.get_model("configuration", "FeatureFlag")
    FeatureFlag.objects.filter(
        key__in=[f[0] for f in INITIAL_FLAGS]
    ).delete()
class Migration(migrations.Migration):
    dependencies = [
        ("configuration", "0003_add_feature_flags"),
    ]
    operations = [
        migrations.RunPython(seed_flags, reverse_code=unseed_flags),
    ]
