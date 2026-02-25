"""
Broadcast service - handles Redis pub/sub for real-time notification delivery.
"""
import json
import logging
from typing import List, Optional, Dict, Any
from django.conf import settings
from django.contrib.auth import get_user_model

try:
    import redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("redis-py not installed. Real-time notifications will not work.")


User = get_user_model()
logger = logging.getLogger(__name__)


class BroadcastService:
    """
    Handles Redis pub/sub for broadcasting notifications to SSE connections.
    """
    
    _redis_client: Optional["redis.Redis"] = None
    
    @classmethod
    def get_redis_client(cls) -> Optional["redis.Redis"]:
        """
        Get or create Redis client with connection pooling.
        
        Returns:
            Redis client instance or None if Redis is unavailable
        """
        if not REDIS_AVAILABLE:
            logger.warning("Redis is not available")
            return None
        
        if cls._redis_client is None:
            try:
                redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
                cls._redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                # Test connection
                cls._redis_client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                cls._redis_client = None
        
        return cls._redis_client
    
    @classmethod
    def get_channel_name(cls, user_id: int) -> str:
        """
        Get Redis channel name for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Redis channel name
        """
        return f"notifications:{user_id}"
    
    @classmethod
    def broadcast_to_user(
        cls,
        user_id: int,
        notification_data: Dict[str, Any]
    ) -> bool:
        """
        Broadcast a notification to a specific user via Redis pub/sub.
        
        Args:
            user_id: User ID to broadcast to
            notification_data: Notification data to broadcast (will be JSON serialized)
            
        Returns:
            True if broadcast successful, False otherwise
        """
        try:
            redis_client = cls.get_redis_client()
            if not redis_client:
                logger.warning("Redis client not available, skipping broadcast")
                return False
            
            channel = cls.get_channel_name(user_id)
            
            # Serialize notification data to JSON
            payload = json.dumps(notification_data)
            
            # Publish to Redis channel
            subscribers = redis_client.publish(channel, payload)
            
            logger.debug(
                f"Broadcasted notification to user {user_id} "
                f"(channel: {channel}, subscribers: {subscribers})"
            )
            
            return True
            
        except RedisConnectionError as e:
            logger.error(f"Redis connection error while broadcasting to user {user_id}: {str(e)}")
            return False
        except RedisError as e:
            logger.error(f"Redis error while broadcasting to user {user_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while broadcasting to user {user_id}: {str(e)}")
            return False
    
    @classmethod
    def bulk_broadcast(
        cls,
        user_ids: List[int],
        notification_data: Dict[str, Any]
    ) -> int:
        """
        Broadcast a notification to multiple users.
        
        Args:
            user_ids: List of user IDs to broadcast to
            notification_data: Notification data to broadcast
            
        Returns:
            Number of successful broadcasts
        """
        if not user_ids:
            return 0
        
        try:
            redis_client = cls.get_redis_client()
            if not redis_client:
                logger.warning("Redis client not available, skipping bulk broadcast")
                return 0
            
            # Serialize once for all users
            payload = json.dumps(notification_data)
            
            success_count = 0
            
            # Use pipeline for efficiency
            with redis_client.pipeline() as pipe:
                for user_id in user_ids:
                    channel = cls.get_channel_name(user_id)
                    pipe.publish(channel, payload)
                
                # Execute all publishes at once
                results = pipe.execute()
                success_count = len([r for r in results if r is not None])
            
            logger.info(
                f"Bulk broadcasted notification to {success_count}/{len(user_ids)} users"
            )
            
            return success_count
            
        except RedisConnectionError as e:
            logger.error(f"Redis connection error during bulk broadcast: {str(e)}")
            return 0
        except RedisError as e:
            logger.error(f"Redis error during bulk broadcast: {str(e)}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error during bulk broadcast: {str(e)}")
            return 0
    
    @classmethod
    def subscribe_to_user_channel(cls, user_id: int) -> Optional["redis.client.PubSub"]:
        """
        Subscribe to a user's notification channel.
        Used by SSE views to listen for real-time notifications.
        
        Args:
            user_id: User ID to subscribe to
            
        Returns:
            Redis PubSub instance or None if Redis unavailable
        """
        try:
            redis_client = cls.get_redis_client()
            if not redis_client:
                return None
            
            channel = cls.get_channel_name(user_id)
            pubsub = redis_client.pubsub()
            pubsub.subscribe(channel)
            
            logger.info(f"Subscribed to channel {channel} for user {user_id}")
            
            return pubsub
            
        except Exception as e:
            logger.error(f"Failed to subscribe to channel for user {user_id}: {str(e)}")
            return None
    
    @classmethod
    def unsubscribe_from_user_channel(
        cls,
        pubsub: "redis.client.PubSub",
        user_id: int
    ) -> bool:
        """
        Unsubscribe from a user's notification channel.
        
        Args:
            pubsub: Redis PubSub instance
            user_id: User ID
            
        Returns:
            True if unsubscribed successfully
        """
        try:
            channel = cls.get_channel_name(user_id)
            pubsub.unsubscribe(channel)
            pubsub.close()
            
            logger.info(f"Unsubscribed from channel {channel} for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe from channel for user {user_id}: {str(e)}")
            return False
    
    @classmethod
    def test_connection(cls) -> bool:
        """
        Test Redis connection.
        
        Returns:
            True if Redis is available and working, False otherwise
        """
        try:
            redis_client = cls.get_redis_client()
            if not redis_client:
                return False
            
            redis_client.ping()
            return True
            
        except Exception as e:
            logger.error(f"Redis connection test failed: {str(e)}")
            return False


# Convenience functions for direct use

def broadcast_notification(user_id: int, notification_data: Dict[str, Any]) -> bool:
    """
    Broadcast a notification to a user.
    Convenience wrapper for BroadcastService.broadcast_to_user().
    """
    return BroadcastService.broadcast_to_user(user_id, notification_data)


def broadcast_to_multiple_users(
    user_ids: List[int],
    notification_data: Dict[str, Any]
) -> int:
    """
    Broadcast a notification to multiple users.
    Convenience wrapper for BroadcastService.bulk_broadcast().
    """
    return BroadcastService.bulk_broadcast(user_ids, notification_data)
