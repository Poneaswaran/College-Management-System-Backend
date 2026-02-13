import strawberry

from .queries import Query as CoreQuery
from .mutations import Mutation as CoreMutation
from profile_management.graphql.queries import ProfileQuery
from profile_management.graphql.mutations import ProfileMutation
from timetable.graphql.queries import TimetableQuery
from timetable.graphql.mutations import TimetableMutation
from attendance.graphql.queries import AttendanceQuery
from attendance.graphql.mutations import AttendanceMutation
from assignment.graphql.queries import AssignmentQuery
from assignment.graphql.mutations import AssignmentMutation

# ==================================================
# MERGED SCHEMA
# ==================================================

# Merge queries from core, profile_management, timetable, attendance, and assignment apps
@strawberry.type
class Query(CoreQuery, ProfileQuery, TimetableQuery, AttendanceQuery, AssignmentQuery):
    pass


# Merge mutations from core, profile_management, timetable, attendance, and assignment apps
@strawberry.type
class Mutation(CoreMutation, ProfileMutation, TimetableMutation, AttendanceMutation, AssignmentMutation):
    pass


# Create unified schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
