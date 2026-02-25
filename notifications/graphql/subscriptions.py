"""
Optional Strawberry subscriptions for notifications.
Note: SSE is the primary real-time delivery mechanism.
These subscriptions are for WebSocket-based clients if needed.
"""
import strawberry
from typing import AsyncGenerator
from strawberry.types import Info

# Subscriptions are optional and can be implemented if WebSocket support is needed
# For now, SSE is the primary real-time mechanism


@strawberry.type
class NotificationSubscription:
    """
    WebSocket-based subscriptions (optional).
    SSE is the primary real-time mechanism.
    """
    
    @strawberry.subscription
    async def notification_stream(
        self,
        info: Info
    ) -> AsyncGenerator[str, None]:
        """
        Stream notifications via WebSocket.
        Note: This is optional - SSE is the primary mechanism.
        """
        # This would require additional WebSocket infrastructure
        # For production use, SSE endpoint is recommended
        yield "WebSocket subscriptions not implemented - use SSE endpoint"
