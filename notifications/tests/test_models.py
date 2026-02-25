"""
Tests for notification models.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from notifications.models import Notification, NotificationPreference
from notifications.constants import (
    NotificationType,
    NotificationPriority,
    NotificationCategory,
)


User = get_user_model()


class NotificationModelTest(TestCase):
    """Test Notification model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_create_notification(self):
        """Test creating a notification."""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            category=NotificationCategory.SYSTEM,
            priority=NotificationPriority.MEDIUM,
            title='Test Notification',
            message='This is a test message',
            action_url='/test',
            metadata={'test': 'data'}
        )
        
        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.notification_type, NotificationType.ANNOUNCEMENT)
        self.assertFalse(notification.is_read)
        self.assertFalse(notification.is_dismissed)
        self.assertEqual(notification.metadata, {'test': 'data'})
    
    def test_notification_ordering(self):
        """Test notifications are ordered by created_at descending."""
        # Create multiple notifications
        notif1 = Notification.objects.create(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            category=NotificationCategory.SYSTEM,
            title='First'
        )
        
        notif2 = Notification.objects.create(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            category=NotificationCategory.SYSTEM,
            title='Second'
        )
        
        notifications = Notification.objects.all()
        self.assertEqual(notifications[0], notif2)
        self.assertEqual(notifications[1], notif1)
    
    def test_notification_str(self):
        """Test notification string representation."""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            category=NotificationCategory.SYSTEM,
            title='Test Title'
        )
        
        str_repr = str(notification)
        self.assertIn('ANNOUNCEMENT', str_repr)
        self.assertIn('Test Title', str_repr)


class NotificationPreferenceModelTest(TestCase):
    """Test NotificationPreference model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_preference(self):
        """Test creating a preference."""
        preference = NotificationPreference.objects.create(
            user=self.user,
            category=NotificationCategory.ATTENDANCE,
            is_enabled=True,
            is_sse_enabled=True,
            is_email_enabled=False
        )
        
        self.assertEqual(preference.user, self.user)
        self.assertEqual(preference.category, NotificationCategory.ATTENDANCE)
        self.assertTrue(preference.is_enabled)
        self.assertTrue(preference.is_sse_enabled)
        self.assertFalse(preference.is_email_enabled)
    
    def test_unique_user_category(self):
        """Test user-category uniqueness constraint."""
        NotificationPreference.objects.create(
            user=self.user,
            category=NotificationCategory.ATTENDANCE
        )
        
        # Creating duplicate should fail
        with self.assertRaises(Exception):
            NotificationPreference.objects.create(
                user=self.user,
                category=NotificationCategory.ATTENDANCE
            )
