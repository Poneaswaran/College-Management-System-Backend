"""GraphQL types for profile management"""
import strawberry
from typing import Optional
from datetime import date, datetime

from profile_management.models import StudentProfile, ParentProfile
from core.graphql.types import DepartmentType, CourseType, SectionType, UserType


@strawberry.type
class StudentProfileType:
    id: int
    
    # Basic Personal Information
    first_name: str
    last_name: Optional[str]
    phone: str
    date_of_birth: Optional[date]
    gender: Optional[str]
    address: Optional[str]
    profile_photo: Optional[str]
    
    # Academic Information
    register_number: str
    roll_number: Optional[str]
    department: DepartmentType
    course: CourseType
    section: Optional[SectionType]
    year: int
    semester: int
    admission_date: Optional[date]
    academic_status: str
    
    # Guardian Details
    guardian_name: Optional[str]
    guardian_relationship: Optional[str]
    guardian_phone: Optional[str]
    guardian_email: Optional[str]
    
    # Identification (Admin only)
    aadhar_number: Optional[str]
    id_proof_type: Optional[str]
    id_proof_number: Optional[str]
    
    # System Fields
    is_active: bool
    profile_completed: bool
    created_at: datetime
    updated_at: datetime
    
    # User relationship
    user: UserType
    
    @strawberry.field
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name or ''}".strip()
    
    @strawberry.field
    def profile_photo_url(self) -> Optional[str]:
        if self.profile_photo:
            return f"/media/{self.profile_photo}"
        return None


@strawberry.type
class ParentProfileType:
    id: int
    relationship: str
    phone_number: str
    student: StudentProfileType
    user: UserType
