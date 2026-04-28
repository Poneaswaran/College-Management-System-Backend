from django.urls import path
from .views import MarkInvigilationAttendanceView, HODArrearListView

app_name = 'exams'

urlpatterns = [
    path('mark-attendance/', MarkInvigilationAttendanceView.as_view(), name='mark_attendance'),
    path('hod-arrears/', HODArrearListView.as_view(), name='hod_arrear_list'),
]
