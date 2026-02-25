"""
SSE connection manager.
Tracks active SSE connections, handles heartbeats, and enforces connection limits.
"""
import logging
import time
from typing import Dict, Set, Optional
from threading import Lock


logger = logging.getLogger(__name__)


class SSEConnectionManager:
    """
    Manages SSE connections per user.
    Tracks active connections, enforces limits, and handles cleanup.
    """
    
    # Class-level storage for connections
    _connections: Dict[int, Set[str]] = {}
    _connection_timestamps: Dict[str, float] = {}
    _lock = Lock()
    
    @classmethod
    def add_connection(cls, user_id: int, connection_id: str, max_connections: int = 3) -> bool:
        """
        Add a new SSE connection for a user.
        
        Args:
            user_id: User ID
            connection_id: Unique connection identifier
            max_connections: Maximum allowed connections per user
            
        Returns:
            True if connection added, False if limit exceeded
        """
        with cls._lock:
            # Initialize user's connection set if needed
            if user_id not in cls._connections:
                cls._connections[user_id] = set()
            
            # Check connection limit
            if len(cls._connections[user_id]) >= max_connections:
                logger.warning(
                    f"User {user_id} exceeded max SSE connections ({max_connections})"
                )
                return False
            
            # Add connection
            cls._connections[user_id].add(connection_id)
            cls._connection_timestamps[connection_id] = time.time()
            
            logger.info(
                f"Added SSE connection {connection_id} for user {user_id} "
                f"(total: {len(cls._connections[user_id])})"
            )
            
            return True
    
    @classmethod
    def remove_connection(cls, user_id: int, connection_id: str) -> None:
        """
        Remove an SSE connection.
        
        Args:
            user_id: User ID
            connection_id: Connection identifier
        """
        with cls._lock:
            if user_id in cls._connections:
                cls._connections[user_id].discard(connection_id)
                
                # Clean up empty set
                if not cls._connections[user_id]:
                    del cls._connections[user_id]
            
            # Remove timestamp
            cls._connection_timestamps.pop(connection_id, None)
            
            logger.info(f"Removed SSE connection {connection_id} for user {user_id}")
    
    @classmethod
    def get_user_connections(cls, user_id: int) -> Set[str]:
        """
        Get all active connections for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Set of connection IDs
        """
        with cls._lock:
            return cls._connections.get(user_id, set()).copy()
    
    @classmethod
    def get_connection_count(cls, user_id: int) -> int:
        """
        Get number of active connections for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of active connections
        """
        with cls._lock:
            return len(cls._connections.get(user_id, set()))
    
    @classmethod
    def get_total_connections(cls) -> int:
        """
        Get total number of active SSE connections.
        
        Returns:
            Total connection count
        """
        with cls._lock:
            return sum(len(conns) for conns in cls._connections.values())
    
    @classmethod
    def cleanup_stale_connections(cls, max_age_seconds: int = 300) -> int:
        """
        Clean up stale connections that haven't been updated recently.
        
        Args:
            max_age_seconds: Maximum age in seconds before connection is considered stale
            
        Returns:
            Number of connections cleaned up
        """
        now = time.time()
        stale_connections = []
        
        with cls._lock:
            for connection_id, timestamp in cls._connection_timestamps.items():
                if now - timestamp > max_age_seconds:
                    stale_connections.append(connection_id)
            
            # Remove stale connections
            for connection_id in stale_connections:
                # Find and remove from user connections
                for user_id, conns in list(cls._connections.items()):
                    if connection_id in conns:
                        conns.discard(connection_id)
                        if not conns:
                            del cls._connections[user_id]
                        break
                
                # Remove timestamp
                cls._connection_timestamps.pop(connection_id, None)
        
        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale SSE connections")
        
        return len(stale_connections)
    
    @classmethod
    def update_heartbeat(cls, connection_id: str) -> None:
        """
        Update heartbeat timestamp for a connection.
        
        Args:
            connection_id: Connection identifier
        """
        with cls._lock:
            if connection_id in cls._connection_timestamps:
                cls._connection_timestamps[connection_id] = time.time()
    
    @classmethod
    def get_stats(cls) -> dict:
        """
        Get connection statistics.
        
        Returns:
            Dict with connection stats
        """
        with cls._lock:
            total_connections = sum(len(conns) for conns in cls._connections.values())
            total_users = len(cls._connections)
            
            return {
                'total_connections': total_connections,
                'total_users': total_users,
                'users_with_connections': {
                    user_id: len(conns)
                    for user_id, conns in cls._connections.items()
                },
            }
