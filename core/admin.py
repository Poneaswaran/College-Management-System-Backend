from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django import forms

from .models import Department, Course, Section, Role

User = get_user_model()


# ==================================================
# CUSTOM USER FORMS WITH PASSWORD HASHING
# ==================================================

class UserCreationForm(forms.ModelForm):
	"""
	A form for creating new users with password hashing.
	Includes all the required fields, plus a repeated password.
	"""
	password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
	password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

	class Meta:
		model = User
		fields = ('email', 'register_number', 'role', 'department')

	def clean_password2(self):
		# Check that the two password entries match
		password1 = self.cleaned_data.get("password1")
		password2 = self.cleaned_data.get("password2")
		if password1 and password2 and password1 != password2:
			raise forms.ValidationError("Passwords don't match")
		return password2

	def clean(self):
		cleaned_data = super().clean()
		email = cleaned_data.get('email')
		register_number = cleaned_data.get('register_number')
		
		# At least one of email or register_number must be provided
		if not email and not register_number:
			raise forms.ValidationError("Either email or register number must be provided")
		
		return cleaned_data

	def save(self, commit=True):
		# Save the provided password in hashed format
		user = super().save(commit=False)
		user.set_password(self.cleaned_data["password1"])
		if commit:
			user.save()
		return user


class UserChangeForm(forms.ModelForm):
	"""
	A form for updating users. Includes all the fields on
	the user, but replaces the password field with admin's
	password hash display field.
	"""
	password = ReadOnlyPasswordHashField(
		label="Password",
		help_text=(
			"Raw passwords are not stored, so there is no way to see this "
			"user's password, but you can change the password using "
			"<a href=\"../password/\">this form</a>."
		),
	)

	class Meta:
		model = User
		fields = ('email', 'register_number', 'password', 'role', 'department', 
				  'is_active', 'is_staff', 'is_superuser')

	def clean_password(self):
		# Regardless of what the user provides, return the initial value.
		# This is done here, rather than on the field, because the
		# field does not have access to the initial value
		return self.initial.get("password")


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
class CustomUserAdmin(BaseUserAdmin):
	"""
	Custom User Admin with proper password hashing support
	"""
	# The forms to add and change user instances
	form = UserChangeForm
	add_form = UserCreationForm

	# The fields to be used in displaying the User model.
	list_display = ("email", "register_number", "role", "department", "is_active", "is_staff")
	search_fields = ("email", "register_number")
	list_filter = ("role", "department", "is_active", "is_staff", "is_superuser")
	readonly_fields = ("date_joined", "last_login")
	
	# Fieldsets for editing existing users
	fieldsets = (
		(None, {"fields": ("email", "register_number", "password")}),
		("Personal Info", {"fields": ("role", "department")}),
		("Permissions", {
			"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
		}),
		("Important dates", {"fields": ("date_joined", "last_login")}),
	)
	
	# add_fieldsets for creating new users with password hashing
	add_fieldsets = (
		(None, {
			"classes": ("wide",),
			"fields": ("email", "register_number", "role", "department", 
					   "password1", "password2", "is_active", "is_staff"),
		}),
	)
	
	ordering = ("-date_joined",)
	filter_horizontal = ("groups", "user_permissions")
