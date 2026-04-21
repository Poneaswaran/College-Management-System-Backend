from django_tenants.admin import TenantAdminMixin
from django.contrib import admin

from .models import Client, Domain


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "short_name", "schema_name", "is_active", "created_on"]
    search_fields = ["name", "short_name", "schema_name"]
    list_filter = ["is_active"]


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ["domain", "tenant", "is_primary"]
    list_filter = ["is_primary"]
    search_fields = ["domain"]
