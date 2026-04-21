from django.urls import path

from .hod_views import (
    HODAssignSlotView,
    HODClassesView,
    HODFacultyBySubjectView,
    HODSubjectsView,
    HODTimetableView,
)

urlpatterns = [
    path("classes/", HODClassesView.as_view(), name="hod-classes"),
    path("timetable/", HODTimetableView.as_view(), name="hod-timetable"),
    path("subjects/", HODSubjectsView.as_view(), name="hod-subjects"),
    path("faculty/", HODFacultyBySubjectView.as_view(), name="hod-faculty"),
    path("assign-slot/", HODAssignSlotView.as_view(), name="hod-assign-slot"),
]
