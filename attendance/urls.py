from django.urls import path
from .views import (
    FacultyPunchInView, 
    FacultyPunchOutView, 
    HODFacultyAttendanceView,
    StudentAttendanceReportsView,
    StudentAttendanceHistoryView,
    ActiveStudentSessionsView,
    StudentMarkAttendanceView
)

app_name = 'attendance'

urlpatterns = [
    path('faculty/punch-in/', FacultyPunchInView.as_view(), name='faculty_punch_in'),
    path('faculty/punch-out/', FacultyPunchOutView.as_view(), name='faculty_punch_out'),
    path('faculty/department-report/', HODFacultyAttendanceView.as_view(), name='department_report'),
    
    # Student endpoints
    path('student/reports/', StudentAttendanceReportsView.as_view(), name='student_reports'),
    path('student/history/', StudentAttendanceHistoryView.as_view(), name='student_history'),
    path('student/active-sessions/', ActiveStudentSessionsView.as_view(), name='student_active_sessions'),
    path('student/mark/', StudentMarkAttendanceView.as_view(), name='student_mark_attendance'),
]

