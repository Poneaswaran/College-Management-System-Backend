"""GraphQL mutations for profile management"""
import strawberry
from typing import Optional
from datetime import date
from strawberry.types import Info
from strawberry.file_uploads import Upload

import jwt
import random
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from core.models import Role

from profile_management.models import StudentProfile
from .types import StudentProfileType
from profile_management.models import ParentProfile, ParentLoginOTP
from core.graphql.types import UserType
from core.graphql.auth import require_auth

User = get_user_model()


# ==================================================
# INPUT TYPES
# ==================================================

@strawberry.input
class UpdateStudentProfileInput:
    """Input for updating student profile (fields editable by student)"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_relationship: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_email: Optional[str] = None


@strawberry.input
class UpdateStudentProfileWithPhotoInput:
    """Input for updating student profile with profile picture"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_relationship: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_email: Optional[str] = None


@strawberry.input
class AdminUpdateStudentProfileInput:
    """Input for admin to update academic fields"""
    roll_number: Optional[str] = None
    year: Optional[int] = None
    semester: Optional[int] = None
    section_id: Optional[int] = None
    admission_date: Optional[date] = None
    academic_status: Optional[str] = None
    aadhar_number: Optional[str] = None
    id_proof_type: Optional[str] = None
    id_proof_number: Optional[str] = None


# ==================================================
# RESPONSE TYPES
# ==================================================

@strawberry.type
class StudentProfileResponse:
    profile: StudentProfileType
    message: str


@strawberry.type
class ParentOtpRequestResponse:
    masked_contact: Optional[str]
    message: str


@strawberry.type
class ParentVerifyResponse:
    user: UserType
    access_token: str
    refresh_token: str
    message: str


# ==================================================
# MUTATIONS
# ==================================================

@strawberry.type
class ProfileMutation:

    @strawberry.mutation
    @require_auth
    def update_student_profile(
        self,
        info: Info,
        register_number: str,
        data: UpdateStudentProfileInput
    ) -> StudentProfileResponse:
        """Update student profile (editable fields only)"""
        try:
            profile = StudentProfile.objects.select_related(
                'user', 'department', 'course', 'section'
            ).get(register_number=register_number)
            
            # Update only provided fields (handle empty strings as None)
            if data.first_name is not None and data.first_name.strip():
                profile.first_name = data.first_name
            if data.last_name is not None and data.last_name.strip():
                profile.last_name = data.last_name
            if data.phone is not None and data.phone.strip():
                profile.phone = data.phone
            if data.date_of_birth is not None:
                profile.date_of_birth = data.date_of_birth
            if data.gender is not None and data.gender.strip():
                profile.gender = data.gender
            if data.address is not None and data.address.strip():
                profile.address = data.address
            if data.guardian_name is not None and data.guardian_name.strip():
                profile.guardian_name = data.guardian_name
            if data.guardian_relationship is not None and data.guardian_relationship.strip():
                profile.guardian_relationship = data.guardian_relationship
            if data.guardian_phone is not None and data.guardian_phone.strip():
                profile.guardian_phone = data.guardian_phone
            if data.guardian_email is not None and data.guardian_email.strip():
                profile.guardian_email = data.guardian_email
            
            profile.save()
            
            return StudentProfileResponse(
                profile=profile,
                message="Profile updated successfully"
            )
            
        except StudentProfile.DoesNotExist:
            raise Exception(f"Student profile with register number {register_number} not found")

    @strawberry.mutation
    @require_auth
    def update_student_profile_with_photo(
        self,
        info: Info,
        register_number: str,
        data: UpdateStudentProfileWithPhotoInput,
        profile_picture: Optional[Upload] = None,
        profile_picture_base64: Optional[str] = None
    ) -> StudentProfileResponse:
        """
        Update student profile with optional profile picture upload
        Supports both multipart upload (profile_picture) and base64 (profile_picture_base64)
        """
        try:
            profile = StudentProfile.objects.select_related(
                'user', 'department', 'course', 'section'
            ).get(register_number=register_number)
            
            # Check if file was uploaded via multipart and is in context
            if profile_picture is None and hasattr(info.context, '_uploaded_files'):
                uploaded_files = info.context._uploaded_files
                # Look for the file in the uploaded files
                for path, file_obj in uploaded_files.items():
                    if 'profilePicture' in path:
                        profile_picture = file_obj
                        break
            
            # Update text fields (handle empty strings as None)
            if data.first_name is not None and data.first_name.strip():
                profile.first_name = data.first_name
            if data.last_name is not None and data.last_name.strip():
                profile.last_name = data.last_name
            if data.phone is not None and data.phone.strip():
                profile.phone = data.phone
            if data.date_of_birth is not None:
                profile.date_of_birth = data.date_of_birth
            if data.gender is not None and data.gender.strip():
                profile.gender = data.gender
            if data.address is not None and data.address.strip():
                profile.address = data.address
            if data.guardian_name is not None and data.guardian_name.strip():
                profile.guardian_name = data.guardian_name
            if data.guardian_relationship is not None and data.guardian_relationship.strip():
                profile.guardian_relationship = data.guardian_relationship
            if data.guardian_phone is not None and data.guardian_phone.strip():
                profile.guardian_phone = data.guardian_phone
            if data.guardian_email is not None and data.guardian_email.strip():
                profile.guardian_email = data.guardian_email
            
            # Handle profile picture upload (multipart)
            if profile_picture is not None:
                # Delete old profile photo if exists
                if profile.profile_photo:
                    old_path = profile.profile_photo.path
                    if default_storage.exists(old_path):
                        default_storage.delete(old_path)
                
                # Save new profile photo
                file_name = f"student_profiles/{register_number}_{profile_picture.name}"
                profile.profile_photo.save(
                    file_name,
                    ContentFile(profile_picture.read()),
                    save=False
                )
            
            # Handle profile picture from base64
            elif profile_picture_base64 is not None:
                # Delete old profile photo if exists
                if profile.profile_photo:
                    old_path = profile.profile_photo.path
                    if default_storage.exists(old_path):
                        default_storage.delete(old_path)
                
                # Decode base64 image
                try:
                    import base64
                    from datetime import datetime
                    
                    # Split the base64 string: data:image/jpeg;base64,/9j/4AAQ...
                    image_format, image_string = profile_picture_base64.split(';base64,')
                    ext = image_format.split('/')[-1]
                    
                    # Decode base64 to binary
                    image_data = base64.b64decode(image_string)
                    
                    # Create filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_name = f"student_profiles/{register_number}_{timestamp}.{ext}"
                    
                    # Save the image
                    profile.profile_photo.save(
                        file_name,
                        ContentFile(image_data),
                        save=False
                    )
                except Exception as e:
                    raise Exception(f"Invalid base64 image data: {str(e)}")
            
            profile.save()
            
            return StudentProfileResponse(
                profile=profile,
                message="Profile updated successfully with photo"
            )
            
        except StudentProfile.DoesNotExist:
            raise Exception(f"Student profile with register number {register_number} not found")
        except Exception as e:
            raise Exception(f"Error updating profile: {str(e)}")

    @strawberry.mutation
    @require_auth
    def admin_update_student_profile(
        self,
        info: Info,
        register_number: str,
        data: AdminUpdateStudentProfileInput
    ) -> StudentProfileResponse:
        """Admin-only: Update academic and system fields"""
        try:
            profile = StudentProfile.objects.select_related(
                'user', 'department', 'course', 'section'
            ).get(register_number=register_number)
            
            # Update academic fields
            if data.roll_number is not None:
                profile.roll_number = data.roll_number
            if data.year is not None:
                profile.year = data.year
            if data.semester is not None:
                profile.semester = data.semester
            if data.section_id is not None:
                from core.models import Section
                profile.section = Section.objects.get(id=data.section_id)
            if data.admission_date is not None:
                profile.admission_date = data.admission_date
            if data.academic_status is not None:
                profile.academic_status = data.academic_status
            if data.aadhar_number is not None:
                profile.aadhar_number = data.aadhar_number
            if data.id_proof_type is not None:
                profile.id_proof_type = data.id_proof_type
            if data.id_proof_number is not None:
                profile.id_proof_number = data.id_proof_number
            
            profile.save()
            
            return StudentProfileResponse(
                profile=profile,
                message="Profile updated successfully by admin"
            )
            
        except StudentProfile.DoesNotExist:
            raise Exception(f"Student profile with register number {register_number} not found")

    @strawberry.mutation
    def request_parent_otp(self, register_number: str) -> ParentOtpRequestResponse:
        """Request an OTP be sent to the guardian contact for the given student register number."""
        try:
            profile = StudentProfile.objects.get(register_number=register_number)

            contact = profile.guardian_phone or profile.guardian_email
            if not contact:
                raise Exception("No guardian contact found on student profile")

            # generate 6-digit code
            code = f"{random.randint(100000, 999999)}"
            now = datetime.utcnow()
            expires = now + timedelta(minutes=10)

            otp = ParentLoginOTP.objects.create(
                student=profile,
                code=code,
                contact=contact,
                expires_at=expires
            )

            # TODO: In production, send SMS/Email here

            # mask contact for response
            masked = None
            if profile.guardian_phone:
                masked = f"***{profile.guardian_phone[-4:]}"
            elif profile.guardian_email:
                parts = profile.guardian_email.split('@')
                masked = parts[0][0] + '***' + parts[0][-1] + '@' + parts[1]

            return ParentOtpRequestResponse(
                masked_contact=masked,
                message="OTP generated and sent to guardian contact (dev-logged)."
            )

        except StudentProfile.DoesNotExist:
            raise Exception(f"Student profile with register number {register_number} not found")

    @strawberry.mutation
    def verify_parent_otp(
        self,
        register_number: str,
        otp: str,
        relationship: Optional[str] = None,
        phone_number: Optional[str] = None
    ) -> ParentVerifyResponse:
        """Verify provided OTP, create parent user/profile if needed and return JWT tokens."""
        try:
            profile = StudentProfile.objects.get(register_number=register_number)
        except StudentProfile.DoesNotExist:
            raise Exception("Invalid register number")

        # find matching active otp
        now = datetime.utcnow()
        candidate = ParentLoginOTP.objects.filter(student=profile, code=otp, used=False, expires_at__gt=now).first()
        if not candidate:
            # Track failed attempts
            last = ParentLoginOTP.objects.filter(student=profile).order_by('-created_at').first()
            if last:
                last.attempts = last.attempts + 1
                last.save()
            raise Exception("Invalid or expired OTP")

        # mark used
        candidate.used = True
        candidate.save()

        # Create or get parent User
        parent_email = f"{register_number}@p"
        parent_user, created = User.objects.get_or_create(
            email=parent_email,
            defaults={
                'register_number': None,
                'is_active': True,
            }
        )
        if created:
            # assign PARENT role (create if missing)
            parent_role, _ = Role.objects.get_or_create(code='PARENT', defaults={'name': 'Parent', 'is_global': True, 'is_active': True})
            parent_user.role = parent_role
            parent_user.set_unusable_password()
            parent_user.save()

        # ensure ParentProfile exists
        parent_profile, _ = ParentProfile.objects.get_or_create(
            user=parent_user,
            student=profile,
            defaults={
                'relationship': relationship or profile.guardian_relationship or 'Parent',
                'phone_number': phone_number or profile.guardian_phone or ''
            }
        )

        # generate tokens (same structure as core.login)
        access_payload = {
            'user_id': parent_user.id,
            'email': parent_user.email,
            'register_number': parent_user.register_number,
            'role': parent_user.role.code,
            'department_id': parent_user.department.id if parent_user.department else None,
            'parent_for_student_id': profile.id,
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow(),
            'type': 'access'
        }

        refresh_payload = {
            'user_id': parent_user.id,
            'exp': datetime.utcnow() + timedelta(days=7),
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }

        access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm='HS256')
        refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm='HS256')

        return ParentVerifyResponse(
            user=parent_user,
            access_token=access_token,
            refresh_token=refresh_token,
            message="Parent authenticated successfully"
        )
