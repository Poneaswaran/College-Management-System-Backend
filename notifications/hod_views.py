from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import DepartmentNotice
from .serializers import DepartmentNoticeSerializer
from .services.notification_service import bulk_create_notifications
from .services.broadcast_service import broadcast_to_multiple_users
from .constants import NotificationType

User = get_user_model()

class HODNoticeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for HOD to manage department notices.
    """
    serializer_class = DepartmentNoticeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Only show notices for the HOD's department
        if hasattr(user, 'department') and user.department:
            return DepartmentNotice.objects.filter(department=user.department)
        return DepartmentNotice.objects.none()

    def perform_create(self, serializer):
        notice = serializer.save()
        
        # Trigger actual notifications to target audience
        self._notify_audience(notice)

    def _notify_audience(self, notice):
        """
        Send notifications and broadcast real-time events to the target audience.
        """
        department = notice.department
        target = notice.target_audience
        
        # Determine recipients
        query = Q(department=department)
        if target == 'STUDENTS':
            query &= Q(role__code='STUDENT')
        elif target == 'FACULTY':
            query &= Q(role__code='FACULTY')
        # BOTH doesn't need extra filter beyond department
        
        recipients = User.objects.filter(query).exclude(id=self.request.user.id)
        
        if not recipients.exists():
            return

        # 1. Store in DB
        bulk_create_notifications(
            recipients=list(recipients),
            notification_type=NotificationType.ANNOUNCEMENT,
            title=notice.title,
            message=notice.message,
            actor=self.request.user,
            metadata={
                "notice_id": notice.id,
                "department_code": department.code
            }
        )
        
        # 2. Broadcast real-time
        recipient_ids = list(recipients.values_list('id', flat=True))
        broadcast_to_multiple_users(
            user_ids=recipient_ids,
            notification_data={
                "type": NotificationType.ANNOUNCEMENT,
                "title": notice.title,
                "message": notice.message,
                "created_at": notice.created_at.isoformat(),
                "actor_name": self.request.user.get_full_name()
            }
        )
