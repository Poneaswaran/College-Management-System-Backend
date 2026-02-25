"""
SSE (Server-Sent Events) views for real-time notification delivery.
Uses Django REST Framework with StreamingHttpResponse.
"""
import json
import logging
import time
import uuid
from typing import Iterator
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.renderers import BaseRenderer
from rest_framework.negotiation import BaseContentNegotiation
from django.conf import settings

from notifications.sse.authentication import SSETokenAuthentication
from notifications.sse.connection_manager import SSEConnectionManager
from notifications.services.broadcast_service import BroadcastService


logger = logging.getLogger(__name__)


class EventStreamRenderer(BaseRenderer):
    """Renderer that handles text/event-stream content type for SSE."""
    media_type = 'text/event-stream'
    format = 'text'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """
    Skip DRF's Accept header content negotiation for SSE views.
    EventSource always sends Accept: text/event-stream which DRF
    doesn't know about, so we bypass negotiation entirely.
    """
    def select_parser(self, request, parsers):
        return parsers[0] if parsers else None

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)


class SSENotificationView(APIView):
    """
    SSE endpoint for real-time notification streaming.
    
    Endpoint: GET /api/notifications/stream/?token=<jwt_token>
    
    Returns Server-Sent Events stream with:
    - Real-time notifications via Redis pub/sub
    - Heartbeat events every 30 seconds
    - Auto-reconnection support
    """
    
    authentication_classes = [SSETokenAuthentication]
    renderer_classes = [EventStreamRenderer]
    content_negotiation_class = IgnoreClientContentNegotiation
    
    def get(self, request):
        """
        Stream SSE events to the client.
        
        Query Parameters:
            token: JWT authentication token (required)
            
        Returns:
            StreamingHttpResponse with text/event-stream content
        """
        # Authenticate user
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        user = request.user
        connection_id = str(uuid.uuid4())
        
        # Check connection limit
        max_connections = getattr(
            settings,
            'NOTIFICATION_SSE_MAX_CONNECTIONS_PER_USER',
            3
        )
        
        if not SSEConnectionManager.add_connection(user.id, connection_id, max_connections):
            return Response(
                {'error': f'Maximum {max_connections} concurrent connections allowed'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Create streaming response
        response = StreamingHttpResponse(
            self.event_stream(user, connection_id),
            content_type='text/event-stream'
        )
        
        # Set SSE headers
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
        
        logger.info(f"SSE connection established for user {user.id} ({connection_id})")
        
        return response
    
    def event_stream(self, user, connection_id: str) -> Iterator[str]:
        """
        Generator function that yields SSE events.
        
        Args:
            user: Authenticated user
            connection_id: Unique connection identifier
            
        Yields:
            SSE formatted events
        """
        try:
            # Send initial connection event
            yield self.format_sse_event(
                event='connected',
                data={'message': 'Connected to notification stream', 'user_id': user.id},
                retry=3000
            )
            
            # Subscribe to user's Redis channel
            pubsub = BroadcastService.subscribe_to_user_channel(user.id)
            
            if not pubsub:
                logger.error(f"Failed to subscribe to Redis channel for user {user.id}")
                yield self.format_sse_event(
                    event='error',
                    data={'message': 'Failed to establish real-time connection'}
                )
                return
            
            # Get heartbeat interval
            heartbeat_interval = getattr(
                settings,
                'NOTIFICATION_SSE_HEARTBEAT_INTERVAL',
                30
            )
            
            last_heartbeat = time.time()
            
            # Listen for messages
            for message in pubsub.listen():
                # Check if client disconnected
                # Note: This is a simple implementation
                # Production might need more sophisticated disconnect detection
                
                # Send heartbeat
                now = time.time()
                if now - last_heartbeat >= heartbeat_interval:
                    yield self.format_sse_event(event='heartbeat', data={})
                    SSEConnectionManager.update_heartbeat(connection_id)
                    last_heartbeat = now
                
                # Process message
                if message['type'] == 'message':
                    try:
                        # Parse notification data
                        notification_data = json.loads(message['data'])
                        
                        # Send notification event
                        yield self.format_sse_event(
                            event=notification_data.get('notification_type', 'notification'),
                            data=notification_data,
                            event_id=notification_data.get('id')
                        )
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse notification data: {str(e)}")
                        continue
            
        except GeneratorExit:
            # Client disconnected
            logger.info(f"SSE client disconnected for user {user.id} ({connection_id})")
        
        except Exception as e:
            logger.error(f"SSE stream error for user {user.id}: {str(e)}")
            yield self.format_sse_event(
                event='error',
                data={'message': 'Stream error occurred'}
            )
        
        finally:
            # Cleanup
            try:
                if pubsub:
                    BroadcastService.unsubscribe_from_user_channel(pubsub, user.id)
            except Exception as e:
                logger.error(f"Error unsubscribing from Redis: {str(e)}")
            
            SSEConnectionManager.remove_connection(user.id, connection_id)
            logger.info(f"SSE connection closed for user {user.id} ({connection_id})")
    
    @staticmethod
    def format_sse_event(
        event: str = None,
        data: dict = None,
        event_id: int = None,
        retry: int = None
    ) -> str:
        """
        Format data as SSE event.
        
        Args:
            event: Event type
            data: Event data (will be JSON encoded)
            event_id: Optional event ID
            retry: Reconnection time in milliseconds
            
        Returns:
            SSE formatted string
        """
        sse_data = []
        
        if event_id:
            sse_data.append(f"id: {event_id}")
        
        if event:
            sse_data.append(f"event: {event}")
        
        if data:
            json_data = json.dumps(data)
            sse_data.append(f"data: {json_data}")
        
        if retry:
            sse_data.append(f"retry: {retry}")
        
        # SSE format requires double newline at the end
        return '\n'.join(sse_data) + '\n\n'


class SSEStatsView(APIView):
    """
    View to get SSE connection statistics (admin only).
    """
    
    authentication_classes = [SSETokenAuthentication]
    
    def get(self, request):
        """Get SSE connection statistics."""
        # Check admin permission
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Only allow admins
        if not hasattr(request.user, 'role') or request.user.role not in ['ADMIN', 'HOD']:
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        stats = SSEConnectionManager.get_stats()
        
        return Response({
            'success': True,
            'stats': stats,
            'timestamp': timezone.now().isoformat()
        })
