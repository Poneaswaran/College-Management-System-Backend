"""
Tests for notification service.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from notifications.services import notification_service
from notifications.models import Notification
from notifications.constants import (
    NotificationType,
    NotificationPriority,
    NotificationCategory,
)


User = get_user_model()


class NotificationServiceTest(TestCase):
    """Test notification service functions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.user2 = User.objects.create_user(
            email='test2@example.com',
            password='testpass123'
        )
    
    def test_create_notification(self):
        """Test creating a notification."""
        notification = notification_service.create_notification(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title='Test Title',
            message='Test message',
            action_url='/test',
            metadata={'key': 'value'}
        )
        
        self.assertIsInstance(notification, Notification)
        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.title, 'Test Title')
        self.assertEqual(notification.category, NotificationCategory.SYSTEM)
    
    def test_bulk_create_notifications(self):
        """Test bulk creating notifications."""
        users = [self.user, self.user2]
        
        notifications = notification_service.bulk_create_notifications(
            recipients=users,
            notification_type=NotificationType.ANNOUNCEMENT,
            title='Bulk Test',
            message='Bulk message'
        )
        
        self.assertEqual(len(notifications), 2)
        self.assertEqual(Notification.objects.count(), 2)
    
    def test_mark_as_read(self):
        """Test marking notification as read."""
        notification = notification_service.create_notification(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title='Test',
            message='Test'
        )
        
        updated = notification_service.mark_as_read(notification.id, self.user)
        
        self.assertTrue(updated.is_read)
        self.assertIsNotNone(updated.read_at)
    
    def test_mark_as_read_wrong_user(self):
        """Test marking notification as read with wrong user."""
        notification = notification_service.create_notification(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title='Test',
            message='Test'
        )
        
        with self.assertRaises(PermissionError):
            notification_service.mark_as_read(notification.id, self.user2)
    
    def test_mark_all_as_read(self):
        """Test marking all notifications as read."""
        # Create multiple notifications
        for i in range(3):
            notification_service.create_notification(
                recipient=self.user,
                notification_type=NotificationType.ANNOUNCEMENT,
                title=f'Test {i}',
                message='Test'
            )
        
        count = notification_service.mark_all_as_read(self.user)
        
        self.assertEqual(count, 3)
        self.assertEqual(
            Notification.objects.filter(recipient=self.user, is_read=True).count(),
            3
        )
    
    def test_dismiss_notification(self):
        """Test dismissing a notification."""
        notification = notification_service.create_notification(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title='Test',
            message='Test'
        )
        
        result = notification_service.dismiss_notification(notification.id, self.user)
        
        self.assertTrue(result)
        
        notification.refresh_from_db()
        self.assertTrue(notification.is_dismissed)
    
    def test_get_unread_count(self):
        """Test getting unread count."""
        # Create 2 notifications
        notification_service.bulk_create_notifications(
            recipients=[self.user],
            notification_type=NotificationType.ANNOUNCEMENT,
            title='Test',
            message='Test'
        )
        notification_service.bulk_create_notifications(
            recipients=[self.user],
            notification_type=NotificationType.ANNOUNCEMENT,
            title='Test',
            message='Test'
        )
        
        count = notification_service.get_unread_count(self.user)
        self.assertEqual(count, 2)
        
        # Mark one as read
        notif = Notification.objects.first()
        notification_service.mark_as_read(notif.id, self.user)
        
        count = notification_service.get_unread_count(self.user)
        self.assertEqual(count, 1)
