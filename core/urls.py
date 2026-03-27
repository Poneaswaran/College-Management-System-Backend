from django.urls import path
from .views import (
    AssignPermissionAPIView, FilterOptionsAPIView, SectionListView,
    AdminDepartmentCreateView, AdminCourseCreateView, AdminSectionCreateView,
    DepartmentListView, CourseListView,
    AdminDepartmentDetailView, AdminCourseDetailView, AdminSectionDetailView
)

urlpatterns = [
    path('roles/permissions/assign/', AssignPermissionAPIView.as_view(), name='assign-role-permissions'),
    path('filters/', FilterOptionsAPIView.as_view(), name='core-filters'),
    path('sections/', SectionListView.as_view(), name='academic-section-list'),
    path('departments/', DepartmentListView.as_view(), name='academic-dept-list'),
    path('courses/', CourseListView.as_view(), name='academic-course-list'),
    path('admin/departments/create/', AdminDepartmentCreateView.as_view(), name='admin-dept-create'),
    path('admin/departments/<int:pk>/', AdminDepartmentDetailView.as_view(), name='admin-dept-detail'),
    path('admin/courses/create/', AdminCourseCreateView.as_view(), name='admin-course-create'),
    path('admin/courses/<int:pk>/', AdminCourseDetailView.as_view(), name='admin-course-detail'),
    path('admin/sections/create/', AdminSectionCreateView.as_view(), name='admin-section-create'),
    path('admin/sections/<int:pk>/', AdminSectionDetailView.as_view(), name='admin-section-detail'),
]
