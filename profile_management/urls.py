from django.urls import include, path

urlpatterns = [
    path("", include("profile_management.profile.urls")),
]
