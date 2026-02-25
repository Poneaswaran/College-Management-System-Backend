"""
DRF serializers for SSE notification payloads.
"""
from rest_framework import serializers
from notifications.models import Notification


class NotificationSSESerializer(serializers.ModelSerializer):
    """
    Serializer for notifications in SSE format.
    Converts notification model to JSON for SSE delivery.
    """
    
    actor_name = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'category',
            'priority',
            'title',
            'message',
            'action_url',
            'metadata',
            'is_read',
            'actor_name',
            'created_at',
            'time_ago',
        ]
    
    def get_actor_name(self, obj):
        """Get actor's full name if exists."""
        if obj.actor:
            full_name = obj.actor.get_full_name()
            return full_name if full_name else obj.actor.email
        return None
    
    def get_time_ago(self, obj):
        """Get human-readable time ago string."""
        from django.utils import timezone
        
        now = timezone.now()
        diff = now - obj.created_at
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            return obj.created_at.strftime('%b %d, %Y')


def serialize_notification_for_sse(notification: Notification) -> dict:
    """
    Serialize a notification for SSE delivery.
    
    Args:
        notification: Notification instance
        
    Returns:
        Dict ready for JSON encoding
    """
    serializer = NotificationSSESerializer(notification)
    return serializer.data
