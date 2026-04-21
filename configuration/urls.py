from django.urls import path
from .views import FeatureFlagsView

urlpatterns = [
    path("features/", FeatureFlagsView.as_view(), name="feature-flags"),
]
