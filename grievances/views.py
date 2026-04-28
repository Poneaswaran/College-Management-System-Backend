from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Grievance
from .serializers import GrievanceSerializer
from configuration.services.feature_flag_service import FeatureFlagService
from django.core.exceptions import PermissionDenied

class GrievanceViewSet(viewsets.ModelViewSet):
    serializer_class = GrievanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # Check feature flag
        if not FeatureFlagService.is_enabled("hod_grievances"):
            return Grievance.objects.none()

        if user.role.code == 'HOD':
            # HOD can see all grievances in their department
            return Grievance.objects.filter(department=user.department)
        elif user.role.code == 'STUDENT':
            # Students can see only their own grievances
            return Grievance.objects.filter(student__user=user)
        elif user.role.code == 'ADMIN':
            # Admin can see everything
            return Grievance.objects.all()
        
        return Grievance.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role.code != 'STUDENT':
            raise PermissionDenied("Only students can create grievances.")
        
        # Auto-assign department from student profile
        student_profile = user.student_profile
        serializer.save(student=student_profile, department=student_profile.department)

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        grievance = self.get_object()
        user = request.user

        if user.role.code not in ['HOD', 'ADMIN']:
            return Response(
                {"detail": "You do not have permission to resolve grievances."},
                status=status.HTTP_403_FORBIDDEN
            )

        resolution_note = request.data.get('resolution_note')
        if not resolution_note:
            return Response(
                {"detail": "Resolution note is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        grievance.status = 'RESOLVED'
        grievance.resolved_by = user
        grievance.resolution_note = resolution_note
        grievance.resolved_at = timezone.now()
        grievance.save()

        return Response(GrievanceSerializer(grievance).data)

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        grievance = self.get_object()
        user = request.user

        if user.role.code not in ['HOD', 'ADMIN']:
            return Response(
                {"detail": "You do not have permission to update grievance status."},
                status=status.HTTP_403_FORBIDDEN
            )

        new_status = request.data.get('status')
        if new_status not in dict(Grievance.STATUS_CHOICES):
            return Response(
                {"detail": "Invalid status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        grievance.status = new_status
        grievance.save()

        return Response(GrievanceSerializer(grievance).data)
