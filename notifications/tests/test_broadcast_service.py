"""
Tests for broadcast service.
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock

from notifications.services.broadcast_service import BroadcastService


class BroadcastServiceTest(TestCase):
    """Test broadcast service."""
    
    @patch('notifications.services.broadcast_service.REDIS_AVAILABLE', True)
    @patch('notifications.services.broadcast_service.redis')
    def test_broadcast_to_user(self, mock_redis):
        """Test broadcasting to a user."""
        mock_client = MagicMock()
        mock_client.publish.return_value = 1
        mock_redis.from_url.return_value = mock_client
        
        # Reset Redis client
        BroadcastService._redis_client = None
        
        notification_data = {
            'id': 1,
            'title': 'Test',
            'message': 'Test message'
        }
        
        result = BroadcastService.broadcast_to_user(123, notification_data)
        
        self.assertTrue(result)
        mock_client.publish.assert_called_once()
    
    @patch('notifications.services.broadcast_service.REDIS_AVAILABLE', False)
    def test_broadcast_without_redis(self):
        """Test broadcasting when Redis is not available."""
        notification_data = {'id': 1, 'title': 'Test'}
        
        result = BroadcastService.broadcast_to_user(123, notification_data)
        
        self.assertFalse(result)
    
    def test_get_channel_name(self):
        """Test getting channel name for user."""
        channel = BroadcastService.get_channel_name(123)
        
        self.assertEqual(channel, 'notifications:123')
