from django.urls import path
from .views import FacultyPunchInView, FacultyPunchOutView, HODFacultyAttendanceView

app_name = 'attendance'

urlpatterns = [
    path('faculty/punch-in/', FacultyPunchInView.as_view(), name='faculty_punch_in'),
    path('faculty/punch-out/', FacultyPunchOutView.as_view(), name='faculty_punch_out'),
    path('faculty/department-report/', HODFacultyAttendanceView.as_view(), name='department_report'),
]
