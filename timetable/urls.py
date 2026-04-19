from django.urls import path
from .views import (
    # Existing
    TimetableEntryCreateView,
    SectionCreateTimetableAPIView,
    PeriodDefinitionListView,
    SectionTimetableListView,
    FacultyScheduleListView,
    # Item 3 — bulk generation
    GenerateSemesterTimetableView,
    # Item 6 — PDF export
    TimetableExportView,
    # Item 7 — configuration-driven period generation
    GeneratePeriodsView,
    # Requirements (Item 2 data layer)
    SectionSubjectRequirementListCreateView,
    SectionSubjectRequirementDetailView,
    SectionSubjectRequirementBulkCreateView,
    # Maintenance blocks (Item 4 data layer)
    RoomMaintenanceBlockListCreateView,
    RoomMaintenanceBlockDetailView,
    RescheduleMaintenanceView,
)

urlpatterns = [
    # ── Period definitions ────────────────────────────────────────────────
    path('periods/', PeriodDefinitionListView.as_view(), name='period-definition-list'),

    # ── Timetable viewing ─────────────────────────────────────────────────
    path('sections/view/', SectionTimetableListView.as_view(), name='section-timetable-view'),
    path('faculty/view/', FacultyScheduleListView.as_view(), name='faculty-timetable-view'),

    # ── Manual creation ───────────────────────────────────────────────────
    path('entries/create/', TimetableEntryCreateView.as_view(), name='timetable-entry-create'),
    path('sections/create-timetable/', SectionCreateTimetableAPIView.as_view(), name='section-timetable-bulk-create'),

    # ── Item 3: Full semester generation pipeline ─────────────────────────
    path('generate/', GenerateSemesterTimetableView.as_view(), name='timetable-generate-semester'),

    # ── Item 6: PDF export ────────────────────────────────────────────────
    path('export/', TimetableExportView.as_view(), name='timetable-export-pdf'),

    # ── Item 7: Configuration-driven period generation ────────────────────
    path('generate-periods/', GeneratePeriodsView.as_view(), name='timetable-generate-periods'),

    # ── SectionSubjectRequirement CRUD ────────────────────────────────────
    # POST /timetable/requirements/bulk/   ← must be registered BEFORE the plain list route
    path('requirements/bulk/', SectionSubjectRequirementBulkCreateView.as_view(), name='requirement-bulk-create'),
    path('requirements/', SectionSubjectRequirementListCreateView.as_view(), name='requirement-list-create'),
    path('requirements/<int:pk>/', SectionSubjectRequirementDetailView.as_view(), name='requirement-detail'),

    # ── RoomMaintenanceBlock CRUD + reschedule ────────────────────────────
    path('maintenance/', RoomMaintenanceBlockListCreateView.as_view(), name='maintenance-list-create'),
    path('maintenance/<int:pk>/', RoomMaintenanceBlockDetailView.as_view(), name='maintenance-detail'),
    path('maintenance/<int:pk>/reschedule/', RescheduleMaintenanceView.as_view(), name='maintenance-reschedule'),
]
