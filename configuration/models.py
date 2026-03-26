from django.db import models


class Configuration(models.Model):
    key = models.CharField(max_length=150, unique=True)
    value = models.JSONField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["key"]
        indexes = [
            models.Index(fields=["key", "is_active"]),
        ]

    def __str__(self):
        return self.key
