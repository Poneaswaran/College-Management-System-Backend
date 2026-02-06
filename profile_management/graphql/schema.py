"""GraphQL schema for profile management"""
import strawberry

from .queries import ProfileQuery
from .mutations import ProfileMutation

# Combine all profile-related queries and mutations
schema = strawberry.Schema(
    query=ProfileQuery,
    mutation=ProfileMutation
)
