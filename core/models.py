from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager
)
from django.utils import timezone


# ==================================================
# ACADEMIC STRUCTURE
# ==================================================

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)  # CSE, ECE, MECH
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Course(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="courses"
    )
    name = models.CharField(max_length=100)  # BTech, MTech, BTech AIML
    code = models.CharField(max_length=30)   # BTECH, MTECH, BTECH_AIML
    duration_years = models.PositiveIntegerField(default=4)

    class Meta:
        unique_together = ("department", "code")

    def __str__(self):
        return f"{self.name} - {self.department.code}"


class Section(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="sections"
    )
    name = models.CharField(max_length=10)  # A, B, C
    year = models.PositiveIntegerField()    # 1,2,3,4

    class Meta:
        unique_together = ("course", "name", "year")

    def __str__(self):
        return f"{self.course.code} {self.year}-{self.name}"


# ==================================================
# ROLE MANAGEMENT (DYNAMIC + DEPARTMENT AWARE)
# ==================================================

class Role(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=30)  # STUDENT, FACULTY, HOD
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="roles"
    )
    is_global = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("code", "department")

    def __str__(self):
        return self.name


# ==================================================
# USER AUTH MODELS
# ==================================================

class UserManager(BaseUserManager):
    def create_user(self, password=None, **extra_fields):
        if not extra_fields.get("email") and not extra_fields.get("register_number"):
            raise ValueError("User must have email or register number")

        email = extra_fields.get("email")
        if email:
            extra_fields["email"] = self.normalize_email(email)

        user = self.model(**extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if not extra_fields.get("email"):
            raise ValueError("Superuser must have an email")

        # Assign ADMIN role if no role is provided
        if 'role' not in extra_fields:
            try:
                admin_role = self.model._meta.get_field('role').related_model.objects.get(
                    code='ADMIN', 
                    is_global=True
                )
                extra_fields['role'] = admin_role
            except self.model._meta.get_field('role').related_model.DoesNotExist:
                raise ValueError(
                    "ADMIN role not found. Please run migrations first: "
                    "python manage.py migrate"
                )

        return self.create_user(password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, null=True, blank=True)
    register_number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="users"
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users"
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email or self.register_number


# ==================================================
# TOKEN BLACKLIST (for logout functionality)
# ==================================================

class TokenBlacklist(models.Model):
    """
    Store invalidated JWT tokens (for logout functionality)
    Tokens in this table are considered logged out
    """
    token = models.CharField(max_length=500, unique=True, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blacklisted_tokens",
        null=True,
        blank=True
    )
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # Token expiry time
    reason = models.CharField(
        max_length=50,
        default='logout',
        choices=[
            ('logout', 'User Logout'),
            ('forced', 'Forced Logout'),
            ('security', 'Security Reason'),
        ]
    )

    class Meta:
        ordering = ['-blacklisted_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Blacklisted token for {self.user} at {self.blacklisted_at}"

    @classmethod
    def is_blacklisted(cls, token):
        """Check if a token is blacklisted"""
        return cls.objects.filter(token=token).exists()

    @classmethod
    def cleanup_expired(cls):
        """Remove expired tokens from blacklist (run periodically)"""
        from django.utils import timezone
        return cls.objects.filter(expires_at__lt=timezone.now()).delete()
