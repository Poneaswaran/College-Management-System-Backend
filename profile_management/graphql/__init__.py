"""Profile management GraphQL package"""
from .types import StudentProfileType, ParentProfileType
from .queries import ProfileQuery
from .mutations import ProfileMutation
from .schema import schema

__all__ = [
    'StudentProfileType',
    'ParentProfileType',
    'ProfileQuery',
    'ProfileMutation',
    'schema',
]
