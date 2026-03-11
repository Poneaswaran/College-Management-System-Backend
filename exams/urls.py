from django.urls import path
from .views import MarkInvigilationAttendanceView

app_name = 'exams'

urlpatterns = [
    path('mark-attendance/', MarkInvigilationAttendanceView.as_view(), name='mark_attendance'),
]
