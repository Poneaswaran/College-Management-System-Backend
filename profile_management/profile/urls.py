from django.urls import path

from .views import (
    FacultyCoursesView,
    FacultyDashboardView,
    HODFacultyListView,
    FacultyProfileView,
    FacultyStudentsView,
    ParentRequestOtpView,
    ParentVerifyOtpView,
    StudentAdminProfileUpdateView,
    StudentCourseOverviewView,
    StudentCoursesView,
    StudentDashboardView,
    StudentListView,
    StudentProfileDetailView,
    StudentProfilePhotoUpdateView,
)

urlpatterns = [
    path("students/", StudentListView.as_view(), name="profile-students"),
    path("students/<str:register_number>/", StudentProfileDetailView.as_view(), name="profile-student-detail"),
    path(
        "students/<str:register_number>/photo/",
        StudentProfilePhotoUpdateView.as_view(),
        name="profile-student-photo-update",
    ),
    path(
        "students/<str:register_number>/admin/",
        StudentAdminProfileUpdateView.as_view(),
        name="profile-student-admin-update",
    ),
    path(
        "students/<str:register_number>/dashboard/",
        StudentDashboardView.as_view(),
        name="profile-student-dashboard",
    ),
    path(
        "students/<str:register_number>/courses/",
        StudentCoursesView.as_view(),
        name="profile-student-courses",
    ),
    path(
        "students/<str:register_number>/courses/overview/",
        StudentCourseOverviewView.as_view(),
        name="profile-student-courses-overview",
    ),
    path("faculty/me/", FacultyProfileView.as_view(), name="profile-faculty-me"),
    path("faculty/dashboard/", FacultyDashboardView.as_view(), name="profile-faculty-dashboard"),
    path("faculty/courses/", FacultyCoursesView.as_view(), name="profile-faculty-courses"),
    path("faculty/students/", FacultyStudentsView.as_view(), name="profile-faculty-students"),
    path("hod/faculty-list/", HODFacultyListView.as_view(), name="profile-hod-faculty-list"),
    path("parents/request-otp/", ParentRequestOtpView.as_view(), name="profile-parent-request-otp"),
    path("parents/verify-otp/", ParentVerifyOtpView.as_view(), name="profile-parent-verify-otp"),
]
