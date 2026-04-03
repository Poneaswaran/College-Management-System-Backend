"""GraphQL mutations for profile management"""
import strawberry
from typing import Optional
from datetime import date
from strawberry.types import Info
from strawberry.file_uploads import Upload

from django.contrib.auth import get_user_model

from profile_management.models import StudentProfile
from .types import StudentProfileType, FacultyProfileType
from core.graphql.types import UserType
from core.graphql.auth import require_auth
from profile_management.services import (
    FacultyProfileService,
    ParentAuthService,
    StudentProfileService,
)

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


@strawberry.input
class UpdateFacultyProfileInput:
    designation: Optional[str] = None
    qualifications: Optional[str] = None
    specialization: Optional[str] = None
    office_hours: Optional[str] = None
    teaching_load: Optional[int] = None
    department_id: Optional[int] = None
    is_active: Optional[bool] = None

# ==================================================
# RESPONSE TYPES
# ==================================================

@strawberry.type
class StudentProfileResponse:
    profile: StudentProfileType
    message: str


@strawberry.type
class FacultyProfileResponse:
    profile: Optional[FacultyProfileType]
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
            profile = StudentProfileService.update_profile(
                register_number=register_number,
                data={
                    "first_name": data.first_name,
                    "last_name": data.last_name,
                    "phone": data.phone,
                    "date_of_birth": data.date_of_birth,
                    "gender": data.gender,
                    "address": data.address,
                    "guardian_name": data.guardian_name,
                    "guardian_relationship": data.guardian_relationship,
                    "guardian_phone": data.guardian_phone,
                    "guardian_email": data.guardian_email,
                },
                actor=info.context.request.user,
            )
            
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
            actor = info.context.request.user

            # Check if file was uploaded via multipart and is in context
            if profile_picture is None and hasattr(info.context, '_uploaded_files'):
                uploaded_files = info.context._uploaded_files
                # Look for the file in the uploaded files
                for path, file_obj in uploaded_files.items():
                    if 'profilePicture' in path:
                        profile_picture = file_obj
                        break
            profile = StudentProfileService.update_profile_with_photo(
                register_number=register_number,
                data={
                    "first_name": data.first_name,
                    "last_name": data.last_name,
                    "phone": data.phone,
                    "date_of_birth": data.date_of_birth,
                    "gender": data.gender,
                    "address": data.address,
                    "guardian_name": data.guardian_name,
                    "guardian_relationship": data.guardian_relationship,
                    "guardian_phone": data.guardian_phone,
                    "guardian_email": data.guardian_email,
                },
                actor=actor,
                profile_picture=profile_picture,
                profile_picture_base64=profile_picture_base64,
            )
            
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
            profile = StudentProfileService.admin_update_profile(
                register_number=register_number,
                data={
                    "roll_number": data.roll_number,
                    "year": data.year,
                    "semester": data.semester,
                    "section_id": data.section_id,
                    "admission_date": data.admission_date,
                    "academic_status": data.academic_status,
                    "aadhar_number": data.aadhar_number,
                    "id_proof_type": data.id_proof_type,
                    "id_proof_number": data.id_proof_number,
                },
                actor=info.context.request.user,
            )
            
            return StudentProfileResponse(
                profile=profile,
                message="Profile updated successfully by admin"
            )
            
        except StudentProfile.DoesNotExist:
            raise Exception(f"Student profile with register number {register_number} not found")

    @strawberry.mutation
    def request_parent_otp(self, register_number: str) -> ParentOtpRequestResponse:
        """Request an OTP be sent to the guardian contact for the given student register number."""
        response_data = ParentAuthService.request_otp(register_number=register_number)
        return ParentOtpRequestResponse(
            masked_contact=response_data["masked_contact"],
            message=response_data["message"],
        )

    @strawberry.mutation
    def verify_parent_otp(
        self,
        register_number: str,
        otp: str,
        relationship: Optional[str] = None,
        phone_number: Optional[str] = None
    ) -> ParentVerifyResponse:
        """Verify provided OTP, create parent user/profile if needed and return JWT tokens."""
        response_data = ParentAuthService.verify_otp(
            register_number=register_number,
            otp=otp,
            relationship=relationship,
            phone_number=phone_number,
        )

        return ParentVerifyResponse(
            user=response_data["user"],
            access_token=response_data["access_token"],
            refresh_token=response_data["refresh_token"],
            message=response_data["message"],
        )

    # ==================================================
    # FACULTY PROFILE MUTATIONS
    # ==================================================

    @strawberry.mutation
    @require_auth
    def update_faculty_profile(
        self,
        info: Info,
        data: UpdateFacultyProfileInput,
        user_id: Optional[int] = None
    ) -> FacultyProfileResponse:
        """
        Update faculty profile. 
        Teachers can update their own profile.
        HODs/Admins can modify others by passing user_id.
        """
        try:
            profile = FacultyProfileService.update_profile(
                data={
                    "designation": data.designation,
                    "qualifications": data.qualifications,
                    "specialization": data.specialization,
                    "office_hours": data.office_hours,
                    "teaching_load": data.teaching_load,
                    "department_id": data.department_id,
                    "is_active": data.is_active,
                },
                request_user=info.context.request.user,
                user_id=user_id,
            )
            return FacultyProfileResponse(
                profile=profile,
                message="Faculty profile updated successfully"
            )
        except Exception as e:
            return FacultyProfileResponse(profile=None, message=f"Error updating profile: {str(e)}")
