from rest_framework import generics, permissions
from django.db.models import Q
from .models import DepartmentNotice
from .serializers import DepartmentNoticeSerializer

class FacultyAnnouncementListView(generics.ListAPIView):
    """
    View for faculty members to see notices posted for them in their department.
    """
    serializer_class = DepartmentNoticeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.department:
            return DepartmentNotice.objects.none()
            
        # Faculty should see notices where target is FACULTY or BOTH, within their department
        return DepartmentNotice.objects.filter(
            department=user.department,
            target_audience__in=['FACULTY', 'BOTH']
        ).order_by('-created_at')
