import strawberry

from .queries import Query
from .mutations import Mutation

# ==================================================
# SCHEMA
# ==================================================

schema = strawberry.Schema(query=Query, mutation=Mutation)
