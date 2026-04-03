import random
from datetime import datetime, timedelta

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model

from configuration.services.config_service import FeatureFlagService
from core.models import Role
from profile_management.models import ParentLoginOTP, ParentProfile, StudentProfile

from .tenant_service import TenantService

User = get_user_model()


class ParentAuthService:
    @staticmethod
    def request_otp(register_number, user=None):
        tenant_key = TenantService.get_tenant_key(user)
        enabled = FeatureFlagService.is_enabled(
            "enable_parent_otp_login",
            default=True,
            tenant_key=tenant_key,
            sub_app="profile",
        )
        if not enabled:
            raise Exception("Parent OTP login is currently disabled")

        profile = StudentProfile.objects.select_related("department").get(register_number=register_number)

        contact = profile.guardian_phone or profile.guardian_email
        if not contact:
            raise Exception("No guardian contact found on student profile")

        code = f"{random.randint(100000, 999999)}"
        now = datetime.utcnow()
        expires = now + timedelta(minutes=10)

        ParentLoginOTP.objects.create(
            student=profile,
            code=code,
            contact=contact,
            expires_at=expires,
        )

        masked = None
        if profile.guardian_phone:
            masked = f"***{profile.guardian_phone[-4:]}"
        elif profile.guardian_email:
            parts = profile.guardian_email.split("@")
            masked = parts[0][0] + "***" + parts[0][-1] + "@" + parts[1]

        return {
            "masked_contact": masked,
            "message": "OTP generated and sent to guardian contact (dev-logged).",
        }

    @staticmethod
    def verify_otp(register_number, otp, relationship=None, phone_number=None, user=None):
        tenant_key = TenantService.get_tenant_key(user)
        enabled = FeatureFlagService.is_enabled(
            "enable_parent_otp_login",
            default=True,
            tenant_key=tenant_key,
            sub_app="profile",
        )
        if not enabled:
            raise Exception("Parent OTP login is currently disabled")

        try:
            profile = StudentProfile.objects.get(register_number=register_number)
        except StudentProfile.DoesNotExist:
            raise Exception("Invalid register number")

        now = datetime.utcnow()
        candidate = ParentLoginOTP.objects.filter(
            student=profile,
            code=otp,
            used=False,
            expires_at__gt=now,
        ).first()

        if not candidate:
            last = ParentLoginOTP.objects.filter(student=profile).order_by("-created_at").first()
            if last:
                last.attempts = last.attempts + 1
                last.save()
            raise Exception("Invalid or expired OTP")

        candidate.used = True
        candidate.save()

        parent_email = f"{register_number}@p"
        parent_user, created = User.objects.get_or_create(
            email=parent_email,
            defaults={
                "register_number": None,
                "is_active": True,
            },
        )
        if created:
            parent_role, _ = Role.objects.get_or_create(
                code="PARENT",
                defaults={"name": "Parent", "is_global": True, "is_active": True},
            )
            parent_user.role = parent_role
            parent_user.set_unusable_password()
            parent_user.save()

        ParentProfile.objects.get_or_create(
            user=parent_user,
            student=profile,
            defaults={
                "relationship": relationship or profile.guardian_relationship or "Parent",
                "phone_number": phone_number or profile.guardian_phone or "",
            },
        )

        access_payload = {
            "user_id": parent_user.id,
            "email": parent_user.email,
            "register_number": parent_user.register_number,
            "role": parent_user.role.code,
            "department_id": parent_user.department.id if parent_user.department else None,
            "parent_for_student_id": profile.id,
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow(),
            "type": "access",
        }

        refresh_payload = {
            "user_id": parent_user.id,
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow(),
            "type": "refresh",
        }

        access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm="HS256")
        refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm="HS256")

        return {
            "user": parent_user,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "message": "Parent authenticated successfully",
        }
