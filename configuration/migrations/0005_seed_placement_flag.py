from django.db import migrations

def seed_placement_flag(apps, schema_editor):
    FeatureFlag = apps.get_model("configuration", "FeatureFlag")
    FeatureFlag.objects.get_or_create(
        key="placement_module",
        defaults={
            "description": "Placement Board & Jobs module access",
            "is_enabled_globally": True,
        }
    )

def unseed_placement_flag(apps, schema_editor):
    FeatureFlag = apps.get_model("configuration", "FeatureFlag")
    FeatureFlag.objects.filter(key="placement_module").delete()

class Migration(migrations.Migration):
    dependencies = [
        ("configuration", "0004_seed_feature_flags"),
    ]
    operations = [
        migrations.RunPython(seed_placement_flag, reverse_code=unseed_placement_flag),
    ]
