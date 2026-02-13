"""
GraphQL Schema for Assignment System
Combines queries and mutations
"""
import strawberry

from assignment.graphql.queries import AssignmentQuery
from assignment.graphql.mutations import AssignmentMutation


# Schema combining queries and mutations
assignment_query = AssignmentQuery
assignment_mutation = AssignmentMutation
