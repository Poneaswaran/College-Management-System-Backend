from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import Department, Course, Section, Role

User = get_user_model()


class SectionInline(admin.TabularInline):
	model = Section
	extra = 0


class CourseInline(admin.TabularInline):
	model = Course
	extra = 0


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
	list_display = ("name", "code", "is_active")
	search_fields = ("name", "code")
	list_filter = ("is_active",)
	inlines = [CourseInline]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
	list_display = ("name", "code", "department", "duration_years")
	search_fields = ("name", "code")
	list_filter = ("department",)
	inlines = [SectionInline]


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
	list_display = ("name", "course", "year")
	search_fields = ("name",)
	list_filter = ("year", "course__department")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
	list_display = ("name", "code", "department", "is_global", "is_active")
	search_fields = ("name", "code")
	list_filter = ("is_global", "is_active", "department")


@admin.register(User)
class CustomUserAdmin(admin.ModelAdmin):
	list_display = ("email", "register_number", "role", "department", "is_active", "is_staff")
	search_fields = ("email", "register_number")
	list_filter = ("role", "department", "is_active", "is_staff")
	readonly_fields = ("date_joined",)
	fieldsets = (
		(None, {"fields": ("email", "register_number", "password")} ),
		("Personal Info", {"fields": ("role", "department")} ),
		("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")} ),
		("Important dates", {"fields": ("date_joined",)} ),
	)
