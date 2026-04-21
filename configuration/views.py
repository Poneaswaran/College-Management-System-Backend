from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from configuration.services.feature_flag_service import FeatureFlagService
class FeatureFlagsView(APIView):
    """
    GET /api/config/features/
    Returns all feature flags resolved for the current tenant.
    Frontend uses this to show/hide sidebar items and guard routes.
    """
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response(FeatureFlagService.get_all_flags())
