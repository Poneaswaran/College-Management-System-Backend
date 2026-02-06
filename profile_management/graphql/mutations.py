"""GraphQL mutations for profile management"""
import strawberry
from typing import Optional
from datetime import date

from profile_management.models import StudentProfile
from .types import StudentProfileType


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


# ==================================================
# MUTATIONS
# ==================================================

@strawberry.type
class ProfileMutation:

    @strawberry.mutation
    def update_student_profile(
        self,
        register_number: str,
        data: UpdateStudentProfileInput
    ) -> StudentProfileResponse:
        """Update student profile (editable fields only)"""
        try:
            profile = StudentProfile.objects.select_related(
                'user', 'department', 'course', 'section'
            ).get(register_number=register_number)
            
            # Update only provided fields
            if data.first_name is not None:
                profile.first_name = data.first_name
            if data.last_name is not None:
                profile.last_name = data.last_name
            if data.phone is not None:
                profile.phone = data.phone
            if data.date_of_birth is not None:
                profile.date_of_birth = data.date_of_birth
            if data.gender is not None:
                profile.gender = data.gender
            if data.address is not None:
                profile.address = data.address
            if data.guardian_name is not None:
                profile.guardian_name = data.guardian_name
            if data.guardian_relationship is not None:
                profile.guardian_relationship = data.guardian_relationship
            if data.guardian_phone is not None:
                profile.guardian_phone = data.guardian_phone
            if data.guardian_email is not None:
                profile.guardian_email = data.guardian_email
            
            profile.save()
            
            return StudentProfileResponse(
                profile=profile,
                message="Profile updated successfully"
            )
            
        except StudentProfile.DoesNotExist:
            raise Exception(f"Student profile with register number {register_number} not found")

    @strawberry.mutation
    def admin_update_student_profile(
        self,
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
