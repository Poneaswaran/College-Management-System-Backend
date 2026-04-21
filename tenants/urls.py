from django.urls import path

from .views import TenantBrandingView

urlpatterns = [
    path("branding/", TenantBrandingView.as_view(), name="tenant-branding"),
]
