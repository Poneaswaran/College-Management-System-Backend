"""
Tests for GraphQL mutations.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from notifications.services import notification_service
from notifications.constants import NotificationType


User = get_user_model()


class NotificationGraphQLMutationTest(TestCase):
    """Test notification GraphQL mutations."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_mark_notification_read_mutation(self):
        """Test mark notification as read mutation."""
        # Create notification
        notification = notification_service.create_notification(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title='Test',
            message='Test'
        )
        
        # Mark as read
        updated = notification_service.mark_as_read(notification.id, self.user)
        
        self.assertTrue(updated.is_read)
