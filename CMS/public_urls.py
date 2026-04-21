"""
CMS/public_urls.py

URL configuration for the PUBLIC schema (landing page, tenant signup, super-admin).
This is served when a request comes from the public/shared domain (e.g. yoursaas.com)
rather than a tenant subdomain (e.g. vels.yoursaas.com).
"""

from django.contrib import admin
from django.urls import path
from django.http import JsonResponse


def public_root(request):
    """Simple health-check / landing for the public schema."""
    return JsonResponse({
        "status": "ok",
        "message": "College Management System - Public Schema",
        "hint": "Use a tenant subdomain (e.g. vels.localhost) to access institution data.",
    })


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", public_root, name="public-root"),
]
