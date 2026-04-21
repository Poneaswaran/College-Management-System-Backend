from django_tenants.models import TenantMixin, DomainMixin
from django.db import models


class Client(TenantMixin):
    """
    One row per university/institution. Each gets its own PostgreSQL schema.

    django-tenants uses this model to create and manage per-tenant schemas.
    The `schema_name` field (provided by TenantMixin) maps to a PostgreSQL schema.
    """
    name = models.CharField(
        max_length=255,
        help_text="Full institution name, e.g. 'VELS Institute of Science, Technology & Advanced Studies'",
    )
    short_name = models.CharField(
        max_length=50,
        help_text="Short / abbreviated name, e.g. 'VISTAS'",
    )
    logo = models.ImageField(upload_to="logos/", null=True, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    established_year = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_on = models.DateField(auto_now_add=True)

    # django-tenants: automatically create the PostgreSQL schema on save
    auto_create_schema = True

    class Meta:
        verbose_name = "Institution"
        verbose_name_plural = "Institutions"

    def __str__(self):
        return f"{self.short_name} ({self.schema_name})"


class Domain(DomainMixin):
    """
    Maps subdomains to tenants.
    Example: vels.yoursaas.com -> Client(name="VELS Institute...")
    """
    pass
