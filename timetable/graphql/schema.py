"""
GraphQL schema for timetable management
"""
from .queries import TimetableQuery
from .mutations import TimetableMutation

# These will be merged into the main schema
__all__ = ['TimetableQuery', 'TimetableMutation']
