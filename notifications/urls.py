"""
URL configuration for notifications app.
Only contains SSE endpoint - all other operations use GraphQL.
"""
from django.urls import path
from notifications.sse.views import SSENotificationView, SSEStatsView
from notifications.hod_views import HODNoticeViewSet
from notifications.faculty_views import FacultyAnnouncementListView

app_name = 'notifications'

# Manual mapping for ViewSet to avoid DefaultRouter suffix registration issues
hod_notice_list = HODNoticeViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
hod_notice_detail = HODNoticeViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

urlpatterns = [
    # REST API endpoints
    path('hod/notices/', hod_notice_list, name='hod-notices-list'),
    path('hod/notices/<int:pk>/', hod_notice_detail, name='hod-notices-detail'),
    path('faculty/announcements/', FacultyAnnouncementListView.as_view(), name='faculty-announcements'),
    
    # SSE streaming endpoint
    path('stream/', SSENotificationView.as_view(), name='notification-stream'),
    
    # SSE statistics (admin only)
    path('sse/stats/', SSEStatsView.as_view(), name='sse-stats'),
]
