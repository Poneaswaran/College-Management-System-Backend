import strawberry

from .queries import Query as CoreQuery
from .mutations import Mutation as CoreMutation
from profile_management.graphql.queries import ProfileQuery
from profile_management.graphql.mutations import ProfileMutation

# ==================================================
# MERGED SCHEMA
# ==================================================

# Merge queries from core and profile_management apps
@strawberry.type
class Query(CoreQuery, ProfileQuery):
    pass


# Merge mutations from core and profile_management apps
@strawberry.type
class Mutation(CoreMutation, ProfileMutation):
    pass


# Create unified schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
