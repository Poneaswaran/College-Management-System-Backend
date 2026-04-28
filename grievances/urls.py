from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import GrievanceViewSet

router = SimpleRouter()
router.register(r'requests', GrievanceViewSet, basename='grievance')

urlpatterns = [
] + router.urls
