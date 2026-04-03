from django.urls import path
from .views import (
    TimetableEntryCreateView, SectionCreateTimetableAPIView, 
    PeriodDefinitionListView, SectionTimetableListView, FacultyScheduleListView
)

urlpatterns = [
    # Listing definitions
    path('periods/', PeriodDefinitionListView.as_view(), name='period-definition-list'),
    
    # Timetable viewing
    path('sections/view/', SectionTimetableListView.as_view(), name='section-timetable-view'),
    path('faculty/view/', FacultyScheduleListView.as_view(), name='faculty-timetable-view'),
    
    # Creation
    path('entries/create/', TimetableEntryCreateView.as_view(), name='timetable-entry-create'),
    path('sections/create-timetable/', SectionCreateTimetableAPIView.as_view(), name='section-timetable-bulk-create'),
]
