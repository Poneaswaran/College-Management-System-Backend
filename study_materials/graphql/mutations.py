"""
GraphQL Mutations for Study Materials System
"""
import strawberry
from typing import Optional
from django.utils import timezone
from django.core.files.base import ContentFile
import base64
import os

from study_materials.models import StudyMaterial, StudyMaterialDownload, StudyMaterialView
from study_materials.validators import StudyMaterialValidator
from study_materials.utils import record_material_view, record_material_download
from study_materials.graphql.types import (
    StudyMaterialType,
    UploadStudyMaterialInput,
    UpdateStudyMaterialInput,
    RecordDownloadInput,
    RecordViewInput,
    UploadMaterialResponse,
    UpdateMaterialResponse,
    DeleteMaterialResponse,
    RecordDownloadResponse
)
from core.graphql.auth import require_auth


@strawberry.type
class StudyMaterialMutation:
    """Study Material related mutations"""
    
    @strawberry.mutation
    @require_auth
    def upload_study_material(
        self,
        info,
        input: UploadStudyMaterialInput
    ) -> UploadMaterialResponse:
        """
        Faculty uploads a new study material
        """
        user = info.context.request.user
        
        # Check if user is faculty
        if user.role.code not in ['FACULTY', 'ADMIN', 'HOD']:
            return UploadMaterialResponse(
                success=False,
                message="Only faculty can upload study materials"
            )
        
        # Get related objects
        from timetable.models import Subject
        from core.models import Section
        
        try:
            subject = Subject.objects.get(id=input.subject_id)
            section = Section.objects.get(id=input.section_id)
        except Exception as e:
            return UploadMaterialResponse(
                success=False,
                message=f"Invalid reference: {str(e)}"
            )
        
        # Validate permission to upload for this subject/section
        is_valid, error_message = StudyMaterialValidator.validate_material_upload(
            subject,
            section,
            user
        )
        
        if not is_valid:
            return UploadMaterialResponse(
                success=False,
                message=error_message
            )
        
        # Validate file name
        is_valid, error_message = StudyMaterialValidator.validate_file_extension(
            input.file_name
        )
        if not is_valid:
            return UploadMaterialResponse(
                success=False,
                message=error_message
            )
        
        # Handle base64 file upload
        try:
            # Decode base64 data
            if ',' in input.file_data:
                # Format: "data:application/pdf;base64,JVBERi0..."
                file_data = base64.b64decode(input.file_data.split(',')[-1])
            else:
                # Raw base64 string
                file_data = base64.b64decode(input.file_data)
            
            # Validate file size
            is_valid, error_message = StudyMaterialValidator.validate_file_size(len(file_data))
            if not is_valid:
                return UploadMaterialResponse(
                    success=False,
                    message=error_message
                )
            
            # Create ContentFile
            file_content = ContentFile(file_data, name=input.file_name)
            
        except base64.binascii.Error as e:
            return UploadMaterialResponse(
                success=False,
                message=f"Invalid base64 data: {str(e)}"
            )
        except Exception as e:
            return UploadMaterialResponse(
                success=False,
                message=f"File processing error: {str(e)}"
            )
        
        # Create study material
        try:
            material = StudyMaterial.objects.create(
                subject=subject,
                section=section,
                faculty=user,
                title=input.title,
                description=input.description,
                material_type=input.material_type,
                status=input.status,
                file=file_content
            )
            
            return UploadMaterialResponse(
                success=True,
                message="Study material uploaded successfully",
                material=material
            )
        
        except Exception as e:
            return UploadMaterialResponse(
                success=False,
                message=f"Error creating material: {str(e)}"
            )
    
    @strawberry.mutation
    @require_auth
    def update_study_material(
        self,
        info,
        input: UpdateStudyMaterialInput
    ) -> UpdateMaterialResponse:
        """
        Update an existing study material
        Faculty can only update their own materials
        """
        user = info.context.request.user
        
        try:
            material = StudyMaterial.objects.get(id=input.material_id)
        except StudyMaterial.DoesNotExist:
            return UpdateMaterialResponse(
                success=False,
                message="Study material not found"
            )
        
        # Check permissions
        if user.role.code == 'FACULTY' and material.faculty.id != user.id:
            return UpdateMaterialResponse(
                success=False,
                message="You can only update your own materials"
            )
        
        # Update fields
        try:
            if input.title is not None:
                material.title = input.title
            
            if input.description is not None:
                material.description = input.description
            
            if input.material_type is not None:
                material.material_type = input.material_type
            
            if input.status is not None:
                material.status = input.status
            
            # Handle file replacement
            if input.file_data and input.file_name:
                # Validate file name
                is_valid, error_message = StudyMaterialValidator.validate_file_extension(
                    input.file_name
                )
                if not is_valid:
                    return UpdateMaterialResponse(
                        success=False,
                        message=error_message
                    )
                
                # Decode base64 data
                if ',' in input.file_data:
                    file_data = base64.b64decode(input.file_data.split(',')[-1])
                else:
                    file_data = base64.b64decode(input.file_data)
                
                # Validate file size
                is_valid, error_message = StudyMaterialValidator.validate_file_size(len(file_data))
                if not is_valid:
                    return UpdateMaterialResponse(
                        success=False,
                        message=error_message
                    )
                
                # Delete old file
                if material.file:
                    material.file.delete(save=False)
                
                # Create new file
                file_content = ContentFile(file_data, name=input.file_name)
                material.file = file_content
            
            material.save()
            
            return UpdateMaterialResponse(
                success=True,
                message="Study material updated successfully",
                material=material
            )
        
        except Exception as e:
            return UpdateMaterialResponse(
                success=False,
                message=f"Error updating material: {str(e)}"
            )
    
    @strawberry.mutation
    @require_auth
    def delete_study_material(
        self,
        info,
        material_id: strawberry.ID
    ) -> DeleteMaterialResponse:
        """
        Delete a study material
        Faculty can only delete their own materials
        """
        user = info.context.request.user
        
        try:
            material = StudyMaterial.objects.get(id=material_id)
        except StudyMaterial.DoesNotExist:
            return DeleteMaterialResponse(
                success=False,
                message="Study material not found"
            )
        
        # Check permissions
        if user.role.code == 'FACULTY' and material.faculty.id != user.id:
            return DeleteMaterialResponse(
                success=False,
                message="You can only delete your own materials"
            )
        
        try:
            title = material.title
            material.delete()
            
            return DeleteMaterialResponse(
                success=True,
                message=f"Study material '{title}' deleted successfully"
            )
        
        except Exception as e:
            return DeleteMaterialResponse(
                success=False,
                message=f"Error deleting material: {str(e)}"
            )
    
    @strawberry.mutation
    @require_auth
    def record_material_download(
        self,
        info,
        input: RecordDownloadInput
    ) -> RecordDownloadResponse:
        """
        Record when a student downloads a material
        Student only
        """
        user = info.context.request.user
        
        if user.role.code != 'STUDENT':
            return RecordDownloadResponse(
                success=False,
                message="Only students can record downloads"
            )
        
        try:
            material = StudyMaterial.objects.get(id=input.material_id)
        except StudyMaterial.DoesNotExist:
            return RecordDownloadResponse(
                success=False,
                message="Study material not found"
            )
        
        # Validate access
        is_valid, error_message = StudyMaterialValidator.validate_material_access(
            material, user
        )
        if not is_valid:
            return RecordDownloadResponse(
                success=False,
                message=error_message
            )
        
        try:
            # Get IP address
            ip_address = info.context.request.META.get('REMOTE_ADDR')
            
            # Record download
            record_material_download(material, user, ip_address)
            
            return RecordDownloadResponse(
                success=True,
                message="Download recorded successfully",
                material=material
            )
        
        except Exception as e:
            return RecordDownloadResponse(
                success=False,
                message=f"Error recording download: {str(e)}"
            )
    
    @strawberry.mutation
    @require_auth
    def record_material_view(
        self,
        info,
        input: RecordViewInput
    ) -> RecordDownloadResponse:  # Reusing same response type
        """
        Record when a student views a material
        Student only
        """
        user = info.context.request.user
        
        if user.role.code != 'STUDENT':
            return RecordDownloadResponse(
                success=False,
                message="Only students can record views"
            )
        
        try:
            material = StudyMaterial.objects.get(id=input.material_id)
        except StudyMaterial.DoesNotExist:
            return RecordDownloadResponse(
                success=False,
                message="Study material not found"
            )
        
        # Validate access
        is_valid, error_message = StudyMaterialValidator.validate_material_access(
            material, user
        )
        if not is_valid:
            return RecordDownloadResponse(
                success=False,
                message=error_message
            )
        
        try:
            # Record view
            record_material_view(material, user)
            
            return RecordDownloadResponse(
                success=True,
                message="View recorded successfully",
                material=material
            )
        
        except Exception as e:
            return RecordDownloadResponse(
                success=False,
                message=f"Error recording view: {str(e)}"
            )
