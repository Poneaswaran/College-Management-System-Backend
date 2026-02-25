"""
URL configuration for notifications app.
Only contains SSE endpoint - all other operations use GraphQL.
"""
from django.urls import path
from notifications.sse.views import SSENotificationView, SSEStatsView


app_name = 'notifications'

urlpatterns = [
    # SSE streaming endpoint
    path('stream/', SSENotificationView.as_view(), name='notification-stream'),
    
    # SSE statistics (admin only)
    path('sse/stats/', SSEStatsView.as_view(), name='sse-stats'),
]
