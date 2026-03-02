"""
GraphQL Schema for Study Materials
"""
import strawberry

from study_materials.graphql.queries import StudyMaterialQuery
from study_materials.graphql.mutations import StudyMaterialMutation


# Combine queries and mutations
@strawberry.type
class Query(StudyMaterialQuery):
    pass


@strawberry.type
class Mutation(StudyMaterialMutation):
    pass


# Schema for this module (for modularity)
schema = strawberry.Schema(query=Query, mutation=Mutation)
