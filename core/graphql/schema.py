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
from grades.graphql.queries import GradesQuery
from grades.graphql.mutations import GradesMutation
from notifications.graphql.queries import NotificationQuery
from notifications.graphql.mutations import NotificationMutation
from exams.graphql.queries import ExamQuery
from exams.graphql.mutations import ExamMutation
from study_materials.graphql.queries import StudyMaterialQuery
from study_materials.graphql.mutations import StudyMaterialMutation

# ==================================================
# MERGED SCHEMA
# ==================================================

# Merge queries from core, profile_management, timetable, attendance, assignment, grades, notifications, exams, and study_materials apps
@strawberry.type
class Query(CoreQuery, ProfileQuery, TimetableQuery, AttendanceQuery, AssignmentQuery, GradesQuery, NotificationQuery, ExamQuery, StudyMaterialQuery):
    pass


# Merge mutations from core, profile_management, timetable, attendance, assignment, grades, notifications, exams, and study_materials apps
@strawberry.type
class Mutation(CoreMutation, ProfileMutation, TimetableMutation, AttendanceMutation, AssignmentMutation, GradesMutation, NotificationMutation, ExamMutation, StudyMaterialMutation):
    pass


# Create unified schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
