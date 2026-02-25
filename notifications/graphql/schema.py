"""
Strawberry GraphQL schema for notifications.
Combines queries and mutations into a single schema.
"""
import strawberry
from notifications.graphql.queries import NotificationQuery
from notifications.graphql.mutations import NotificationMutation


# Create the notification schema
schema = strawberry.Schema(
    query=NotificationQuery,
    mutation=NotificationMutation,
)


# Export for integration into main schema
__all__ = ["schema", "NotificationQuery", "NotificationMutation"]
