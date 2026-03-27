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
    tenant_key = models.CharField(max_length=100, null=True, blank=True)
    sub_app = models.CharField(max_length=50, default="global")
    key = models.CharField(max_length=150)
    is_enabled = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sub_app", "key"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_key", "sub_app", "key"],
                name="unique_flag_per_tenant_subapp_key",
            )
        ]
        indexes = [
            models.Index(fields=["tenant_key", "sub_app", "key", "is_active"]),
        ]

    def __str__(self):
        scope = self.tenant_key or "global"
        return f"{scope}:{self.sub_app}.{self.key}={self.is_enabled}"
