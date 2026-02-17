"""GraphQL schema for grades management"""
import strawberry

from .queries import GradesQuery
from .mutations import GradesMutation

# Combine all grades-related queries and mutations
schema = strawberry.Schema(
    query=GradesQuery,
    mutation=GradesMutation
)
