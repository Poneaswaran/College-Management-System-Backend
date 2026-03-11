"""
GraphQL Queries for Study Materials System
"""
import strawberry
from typing import List, Optional
from django.db.models import Q, Count

from study_materials.models import StudyMaterial, StudyMaterialDownload
from study_materials.utils import (
    get_faculty_materials,
    get_faculty_materials_with_stats,
    get_student_materials,
    get_material_statistics,
    get_material_download_list,
    get_faculty_subjects_sections,
    get_hod_department_materials
)
from study_materials.validators import StudyMaterialValidator
from study_materials.graphql.types import (
    StudyMaterialType,
    StudyMaterialDownloadType,
    MaterialStatisticsType,
    FacultySubjectSectionType
)
from core.graphql.auth import require_auth


@strawberry.type
class StudyMaterialQuery:
    """Study Material related queries"""
    
    @strawberry.field
    @require_auth
    def study_material(self, info, id: strawberry.ID) -> Optional[StudyMaterialType]:
        """
        Get a single study material by ID
        """
        user = info.context.request.user
        
        try:
            material = StudyMaterial.objects.select_related(
                'subject', 'section', 'faculty'
            ).get(id=id)
        except StudyMaterial.DoesNotExist:
            return None
        
        # Check access permissions
        is_valid, error_message = StudyMaterialValidator.validate_material_access(material, user)
        if not is_valid:
            raise Exception(error_message)
        
        return material
    
    @strawberry.field
    @require_auth
    def study_materials(
        self,
        info,
        subject_id: Optional[strawberry.ID] = None,
        section_id: Optional[strawberry.ID] = None,
        material_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[StudyMaterialType]:
        """
        Get list of study materials with filters
        Role-based access:
        - Students: See published materials for their section
        - Faculty: See materials they uploaded
        - HOD/Admin: See all materials
        """
        user = info.context.request.user
        
        if user.role.code == 'STUDENT':
            # Students see only published materials for their section
            materials = get_student_materials(user)
            
            # Apply filters
            if subject_id:
                materials = materials.filter(subject_id=subject_id)
            if material_type:
                materials = materials.filter(material_type=material_type)
        
        elif user.role.code == 'FACULTY':
            # Faculty see materials they uploaded
            materials = get_faculty_materials(user)
            
            # Apply filters
            if subject_id:
                materials = materials.filter(subject_id=subject_id)
            if section_id:
                materials = materials.filter(section_id=section_id)
            if material_type:
                materials = materials.filter(material_type=material_type)
            if status:
                materials = materials.filter(status=status)
        
        elif user.role.code == 'HOD':
            # HOD sees materials for their department
            materials = get_hod_department_materials(user)
            
            # Apply filters
            if subject_id:
                materials = materials.filter(subject_id=subject_id)
            if section_id:
                materials = materials.filter(section_id=section_id)
            if material_type:
                materials = materials.filter(material_type=material_type)
            if status:
                materials = materials.filter(status=status)
        
        else:  # ADMIN
            # Admin sees all materials
            materials = StudyMaterial.objects.select_related(
                'subject', 'section', 'faculty'
            ).all()
            
            # Apply filters
            if subject_id:
                materials = materials.filter(subject_id=subject_id)
            if section_id:
                materials = materials.filter(section_id=section_id)
            if material_type:
                materials = materials.filter(material_type=material_type)
            if status:
                materials = materials.filter(status=status)
        
        return list(materials)
    
    @strawberry.field
    @require_auth
    def my_uploaded_materials(
        self,
        info,
        status: Optional[str] = None
    ) -> List[StudyMaterialType]:
        """
        Get materials uploaded by the current faculty member
        Faculty only
        """
        user = info.context.request.user
        
        if user.role.code not in ['FACULTY', 'HOD', 'ADMIN']:
            raise Exception("Only faculty can access uploaded materials")
        
        materials = get_faculty_materials_with_stats(user)
        
        if status:
            materials = materials.filter(status=status)
        
        return list(materials)
    
    @strawberry.field
    @require_auth
    def material_statistics(
        self,
        info,
        material_id: strawberry.ID
    ) -> Optional[MaterialStatisticsType]:
        """
        Get detailed statistics for a study material
        Faculty/HOD/Admin only
        """
        user = info.context.request.user
        
        if user.role.code == 'STUDENT':
            raise Exception("Students cannot access material statistics")
        
        try:
            material = StudyMaterial.objects.get(id=material_id)
        except StudyMaterial.DoesNotExist:
            return None
        
        # Check permissions
        if user.role.code == 'FACULTY' and material.faculty.id != user.id:
            raise Exception("You can only view statistics for your own materials")
        
        if user.role.code == 'HOD':
            # HOD can view materials in their department
            from profile_management.models import FacultyProfile
            try:
                faculty_profile = FacultyProfile.objects.get(user=user)
                if material.section.department != faculty_profile.department:
                    raise Exception("You can only view statistics for materials in your department")
            except FacultyProfile.DoesNotExist:
                raise Exception("Faculty profile not found")
        
        stats = get_material_statistics(material)
        
        return MaterialStatisticsType(
            material_id=material.id,
            total_downloads=stats['total_downloads'],
            unique_downloads=stats['unique_downloads'],
            total_views=stats['total_views'],
            unique_views=stats['unique_views'],
            recent_downloads=list(stats['recent_downloads'])
        )
    
    @strawberry.field
    @require_auth
    def material_download_list(
        self,
        info,
        material_id: strawberry.ID
    ) -> List[StudyMaterialDownloadType]:
        """
        Get list of students who downloaded a material
        Faculty/HOD/Admin only
        """
        user = info.context.request.user
        
        if user.role.code == 'STUDENT':
            raise Exception("Students cannot access download lists")
        
        try:
            material = StudyMaterial.objects.get(id=material_id)
        except StudyMaterial.DoesNotExist:
            return []
        
        # Check permissions
        if user.role.code == 'FACULTY' and material.faculty.id != user.id:
            raise Exception("You can only view download lists for your own materials")
        
        if user.role.code == 'HOD':
            # HOD can view materials in their department
            from profile_management.models import FacultyProfile
            try:
                faculty_profile = FacultyProfile.objects.get(user=user)
                if material.section.department != faculty_profile.department:
                    raise Exception("You can only view download lists for materials in your department")
            except FacultyProfile.DoesNotExist:
                raise Exception("Faculty profile not found")
        
        downloads = get_material_download_list(material)
        
        return list(downloads)
    
    @strawberry.field
    @require_auth
    def my_faculty_subjects_sections(self, info) -> List[FacultySubjectSectionType]:
        """
        Get all subjects and sections that the current faculty teaches
        Faculty only - used to populate upload form
        """
        user = info.context.request.user
        
        if user.role.code not in ['FACULTY', 'HOD', 'ADMIN']:
            raise Exception("Only faculty can access teaching assignments")
        
        slots = get_faculty_subjects_sections(user)
        
        return [
            FacultySubjectSectionType(
                subject_id=slot['subject__id'],
                subject_name=slot['subject__name'],
                subject_code=slot['subject__code'],
                section_id=slot['section__id'],
                section_name=slot['section__name']
            )
            for slot in slots
        ]
    
    @strawberry.field
    @require_auth
    def available_materials_for_student(self, info) -> List[StudyMaterialType]:
        """
        Get all available study materials for the current student
        Student only
        """
        user = info.context.request.user
        
        if user.role.code != 'STUDENT':
            raise Exception("Only students can access this query")
        
        materials = get_student_materials(user)
        
        return list(materials)
