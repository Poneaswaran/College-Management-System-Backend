import strawberry

from .queries import Query as CoreQuery
from .mutations import Mutation as CoreMutation
from profile_management.graphql.queries import ProfileQuery
from profile_management.graphql.mutations import ProfileMutation
from timetable.graphql.queries import TimetableQuery
from timetable.graphql.mutations import TimetableMutation
from attendance.graphql.queries import AttendanceQuery
from attendance.graphql.mutations import AttendanceMutation

# ==================================================
# MERGED SCHEMA
# ==================================================

# Merge queries from core, profile_management, timetable, and attendance apps
@strawberry.type
class Query(CoreQuery, ProfileQuery, TimetableQuery, AttendanceQuery):
    pass


# Merge mutations from core, profile_management, timetable, and attendance apps
@strawberry.type
class Mutation(CoreMutation, ProfileMutation, TimetableMutation, AttendanceMutation):
    pass


# Create unified schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
