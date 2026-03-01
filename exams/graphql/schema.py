"""
GraphQL schema exports for Exam Management.
"""
from exams.graphql.queries import ExamQuery
from exams.graphql.mutations import ExamMutation

__all__ = ['ExamQuery', 'ExamMutation']
