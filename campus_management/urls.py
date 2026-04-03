from django.urls import path
from .views.api_views import (
    VenueListView, AvailableVenueListView, AllocateResourceView, 
    AdminRoomCreateView, AssignRoomToClassView,
    AdminBuildingCreateView, AdminBuildingListView, AdminBuildingDetailView,
    AdminBulkAssignSectionRoomView, AssignedVenuesOverviewView,
    AdminSectionAllocationSummaryView
)

urlpatterns = [
    path('venues/', VenueListView.as_view(), name='venue-list'),
    path('venues/available/', AvailableVenueListView.as_view(), name='available-venue-list'),
    path('allocate/', AllocateResourceView.as_view(), name='allocate-resource'),
    
    # NEW Admin APIs
    path('admin/rooms/create/', AdminRoomCreateView.as_view(), name='admin-room-create'),
    path('admin/classes/assign-room/', AssignRoomToClassView.as_view(), name='admin-assign-room-to-class'),
    path('admin/buildings/', AdminBuildingListView.as_view(), name='admin-building-list'),
    path('admin/buildings/create/', AdminBuildingCreateView.as_view(), name='admin-building-create'),
    path('admin/buildings/<int:pk>/', AdminBuildingDetailView.as_view(), name='admin-building-detail'),
    path('admin/sections/assign-room/', AdminBulkAssignSectionRoomView.as_view(), name='admin-bulk-assign-section-room'),
    path('admin/sections/summary/', AdminSectionAllocationSummaryView.as_view(), name='admin-section-allocation-summary'),
    path('venues/assigned-overview/', AssignedVenuesOverviewView.as_view(), name='assigned-venues-overview'),
]
