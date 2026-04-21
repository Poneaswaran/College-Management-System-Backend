from django.urls import path

from .hod_views import (
    HODAssignSlotView,
    HODClassesView,
    HODFacultyBySubjectView,
    HODSubjectsView,
    HODTimetableView,
    HODSectionInchargeView,
    HODDepartmentFacultyView,
)

urlpatterns = [
    path("classes/", HODClassesView.as_view(), name="hod-classes"),
    path("timetable/", HODTimetableView.as_view(), name="hod-timetable"),
    path("subjects/", HODSubjectsView.as_view(), name="hod-subjects"),
    path("faculty/", HODFacultyBySubjectView.as_view(), name="hod-faculty"),
    path("assign-slot/", HODAssignSlotView.as_view(), name="hod-assign-slot"),
    path("section-incharge/", HODSectionInchargeView.as_view(), name="hod-section-incharge"),
    path("department-faculty/", HODDepartmentFacultyView.as_view(), name="hod-department-faculty"),
]
