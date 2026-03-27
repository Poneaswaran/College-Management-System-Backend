from django.urls import path
from .views import AssignPermissionAPIView, FilterOptionsAPIView

urlpatterns = [
    path('roles/permissions/assign/', AssignPermissionAPIView.as_view(), name='assign-role-permissions'),
    path('filters/', FilterOptionsAPIView.as_view(), name='core-filters'),
]
