from django.db import models
from .timetable.models import TimetableConfiguration


class Configuration(models.Model):
    tenant_key = models.CharField(max_length=100, null=True, blank=True)
    sub_app = models.CharField(max_length=50, default="global")
    key = models.CharField(max_length=150)
    value = models.JSONField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sub_app", "key"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_key", "sub_app", "key"],
                name="unique_config_per_tenant_subapp_key",
            )
        ]
        indexes = [
            models.Index(fields=["tenant_key", "sub_app", "key", "is_active"]),
        ]

    def __str__(self):
        scope = self.tenant_key or "global"
        return f"{scope}:{self.sub_app}.{self.key}"


class FeatureFlag(models.Model):
    """
    One row per product feature. Source of truth for all tenants.
    is_enabled_globally = True means ON for everyone unless overridden.
    """
    key = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_enabled_globally = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.key} ({'ON' if self.is_enabled_globally else 'OFF'} globally)"

class TenantFeatureOverride(models.Model):
    """
    Per-tenant override. If a row exists, it takes priority over
    FeatureFlag.is_enabled_globally for that specific tenant schema.
    """
    flag = models.ForeignKey(
        FeatureFlag, on_delete=models.CASCADE, related_name="overrides"
    )
    schema_name = models.CharField(
        max_length=63,
        help_text="Matches Client.schema_name from django-tenants e.g. 'vels', 'anna'"
    )
    is_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ("flag", "schema_name")
    def __str__(self):
        return f"{self.schema_name} → {self.flag.key} = {self.is_enabled}"

