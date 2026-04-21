from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class TenantBrandingView(APIView):
    """
    GET /api/tenant/branding/

    Returns the current tenant's institution branding information.
    django-tenants makes the current tenant available via connection.tenant.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = connection.tenant

        logo_url = None
        if tenant.logo:
            try:
                logo_url = request.build_absolute_uri(tenant.logo.url)
            except ValueError:
                logo_url = None

        return Response({
            "name": tenant.name,
            "short_name": tenant.short_name,
            "logo_url": logo_url,
            "schema_name": tenant.schema_name,
            "email": tenant.email,
            "phone": tenant.phone,
            "address": tenant.address,
            "established_year": tenant.established_year,
        })
