"""
Middleware for notifications app.
Handles SSE-specific middleware and notification preference checks.
"""
import logging
from django.utils.deprecation import MiddlewareMixin


logger = logging.getLogger(__name__)


class NotificationMiddleware(MiddlewareMixin):
    """
    Middleware for notification-related processing.
    Can be extended to add custom notification logic.
    """
    
    def process_request(self, request):
        """
        Process incoming request.
        Currently a placeholder for future notification middleware logic.
        """
        # Add notification-related attributes to request if needed
        # For example: request.notification_preferences
        
        return None
    
    def process_response(self, request, response):
        """
        Process outgoing response.
        Currently a placeholder for future notification middleware logic.
        """
        return response


class SSECORSMiddleware(MiddlewareMixin):
    """
    Middleware to handle CORS for SSE endpoints.
    Ensures EventSource connections work cross-origin.
    """
    
    def process_response(self, request, response):
        """Add CORS headers for SSE endpoints."""
        # Check if this is an SSE endpoint
        if request.path.startswith('/api/notifications/stream'):
            response['Access-Control-Allow-Origin'] = '*'  # Configure based on your needs
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
        
        return response
