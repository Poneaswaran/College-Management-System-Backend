"""
GraphQL schema exports for Attendance System
"""
from .queries import AttendanceQuery
from .mutations import AttendanceMutation

__all__ = ['AttendanceQuery', 'AttendanceMutation']
