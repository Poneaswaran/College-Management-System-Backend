"""
Tests for GraphQL queries.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from notifications.services import notification_service
from notifications.constants import NotificationType
from notifications.graphql.types import NotificationType as NotificationTypeGQL

User = get_user_model()


class NotificationGraphQLQueryTest(TestCase):
    """Test notification GraphQL queries."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_notification_type_from_model(self):
        """Test creating GraphQL type from model."""
        notification = notification_service.create_notification(
            recipient=self.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title='Test',
            message='Test message'
        )
        
        gql_type = NotificationTypeGQL.from_model(notification)
        
        self.assertEqual(gql_type.id, notification.id)
        self.assertEqual(gql_type.title, 'Test')
        self.assertEqual(gql_type.message, 'Test message')
