from django.urls import path
from .views import (
    LeaveTypeListView, FacultyLeaveBalanceView, LeaveApplicationView, 
    HODLeaveApprovalView, WeekendSettingsView, LeavePolicyViewSet
)

urlpatterns = [
    path('types/', LeaveTypeListView.as_view(), name='leave-types'),
    path('balances/', FacultyLeaveBalanceView.as_view(), name='leave-balances'),
    path('requests/', LeaveApplicationView.as_view(), name='leave-requests'),
    path('approvals/', HODLeaveApprovalView.as_view(), name='hod-approvals'),
    path('settings/weekends/', WeekendSettingsView.as_view(), name='weekend-settings'),
    
    # Policy Management (Manual Router equivalent)
    path('policies/', LeavePolicyViewSet.as_view({'get': 'list', 'post': 'create'}), name='leave-policy-list'),
    path('policies/resolve/', LeavePolicyViewSet.as_view({'get': 'resolve'}), name='leave-policy-resolve'),
    path('policies/<int:pk>/', LeavePolicyViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='leave-policy-detail'),
]
