"""
Tests for SSE views.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from notifications.sse.views import SSENotificationView


User = get_user_model()


class SSEViewTest(TestCase):
    """Test SSE notification view."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_format_sse_event(self):
        """Test SSE event formatting."""
        event = SSENotificationView.format_sse_event(
            event='test',
            data={'message': 'Hello'},
            event_id=123
        )
        
        self.assertIn('id: 123', event)
        self.assertIn('event: test', event)
        self.assertIn('data:', event)
        self.assertTrue(event.endswith('\n\n'))
    
    @patch('notifications.sse.views.SSETokenAuthentication')
    def test_sse_endpoint_requires_auth(self, mock_auth):
        """Test SSE endpoint requires authentication."""
        # This is a basic test - full integration tests would use a test client
        view = SSENotificationView()
        self.assertEqual(view.authentication_classes, [mock_auth])
