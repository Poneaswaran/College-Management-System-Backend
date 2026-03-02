"""
GraphQL types for Study Materials System
"""
import strawberry
import strawberry_django
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from study_materials.models import StudyMaterial, StudyMaterialDownload, StudyMaterialView


# ==================== Output Types ====================

@strawberry_django.type(StudyMaterial)
class StudyMaterialType:
    """StudyMaterial GraphQL type"""
    id: strawberry.ID
    title: str
    description: str
    material_type: str
    status: str
    file: str
    file_size: int
    view_count: int
    download_count: int
    uploaded_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]
    
    # Related fields
    @strawberry_django.field
    def subject(self) -> 'SubjectType':
        return self.subject
    
    @strawberry_django.field
    def section(self) -> 'SectionType':
        return self.section
    
    @strawberry_django.field
    def faculty(self) -> 'UserType':
        return self.faculty
    
    # Computed fields
    @strawberry.field
    def file_url(self) -> str:
        """Get the file URL"""
        if self.file:
            return self.file.url
        return ""
    
    @strawberry.field
    def file_extension(self) -> Optional[str]:
        """Get file extension"""
        return self.file_extension
    
    @strawberry.field
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return self.file_size_mb


@strawberry_django.type(StudyMaterialDownload)
class StudyMaterialDownloadType:
    """StudyMaterialDownload GraphQL type"""
    id: strawberry.ID
    downloaded_at: datetime
    ip_address: Optional[str]
    
    @strawberry_django.field
    def study_material(self) -> StudyMaterialType:
        return self.study_material
    
    @strawberry_django.field
    def student(self) -> 'UserType':
        return self.student
    
    # Computed fields
    @strawberry.field
    def student_name(self) -> str:
        """Get student name"""
        return self.student.get_full_name()
    
    @strawberry.field
    def student_roll_number(self) -> Optional[str]:
        """Get student roll number"""
        try:
            return self.student.student_profile.roll_number
        except:
            return None


@strawberry_django.type(StudyMaterialView)
class StudyMaterialViewType:
    """StudyMaterialView GraphQL type"""
    id: strawberry.ID
    viewed_at: datetime
    
    @strawberry_django.field
    def study_material(self) -> StudyMaterialType:
        return self.study_material
    
    @strawberry_django.field
    def student(self) -> 'UserType':
        from core.graphql.types import UserType
        

@strawberry.type
class MaterialStatisticsType:
    """Statistics for a study material"""
    material_id: int
    total_downloads: int
    unique_downloads: int
    total_views: int
    unique_views: int
    recent_downloads: List[StudyMaterialDownloadType]


@strawberry.type
class FacultySubjectSectionType:
    """Subject-Section combination that a faculty teaches"""
    subject_id: int
    subject_name: str
    subject_code: str
    section_id: int
    section_name: str


# ==================== Input Types ====================

@strawberry.input
class UploadStudyMaterialInput:
    """Input for uploading a study material"""
    subject_id: int
    section_id: int
    title: str
    description: str
    material_type: str
    # Base64 file upload
    file_data: str  # Base64 encoded file (data:type;base64,...)
    file_name: str  # Original filename
    status: str = 'DRAFT'  # Default to DRAFT


@strawberry.input
class UpdateStudyMaterialInput:
    """Input for updating a study material"""
    material_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    material_type: Optional[str] = None
    status: Optional[str] = None
    # Optional file replacement
    file_data: Optional[str] = None  # Base64 encoded file
    file_name: Optional[str] = None  # Original filename


@strawberry.input
class RecordDownloadInput:
    """Input for recording a material download"""
    material_id: int


@strawberry.input
class RecordViewInput:
    """Input for recording a material view"""
    material_id: int


# ==================== Response Types ====================

@strawberry.type
class UploadMaterialResponse:
    """Response after uploading a material"""
    success: bool
    message: str
    material: Optional[StudyMaterialType] = None


@strawberry.type
class UpdateMaterialResponse:
    """Response after updating a material"""
    success: bool
    message: str
    material: Optional[StudyMaterialType] = None


@strawberry.type
class DeleteMaterialResponse:
    """Response after deleting a material"""
    success: bool
    message: str


@strawberry.type
class RecordDownloadResponse:
    """Response after recording a download"""
    success: bool
    message: str
    material: Optional[StudyMaterialType] = None


# Import types from other apps (at the end to avoid circular imports)
from timetable.graphql.types import SubjectType
from core.graphql.types import SectionType, UserType
