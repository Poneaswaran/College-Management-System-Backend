"""
Utility functions for Study Materials Module
"""
from django.db.models import Count, Q, Max
from django.utils import timezone
from datetime import timedelta


def get_faculty_materials(faculty):
    """
    Get all study materials uploaded by a faculty member
    """
    from study_materials.models import StudyMaterial
    
    return StudyMaterial.objects.filter(
        faculty=faculty
    ).select_related('subject', 'section').order_by('-uploaded_at')


def get_faculty_materials_with_stats(faculty):
    """
    Get faculty materials with download/view statistics
    """
    from study_materials.models import StudyMaterial
    
    materials = StudyMaterial.objects.filter(
        faculty=faculty
    ).annotate(
        total_downloads=Count('downloads', distinct=True),
        total_views=Count('views', distinct=True),
        unique_students=Count('downloads__student', distinct=True)
    ).select_related('subject', 'section').order_by('-uploaded_at')
    
    return materials


def get_student_materials(student):
    """
    Get all study materials available for a student
    """
    from study_materials.models import StudyMaterial
    from profile_management.models import StudentProfile
    
    try:
        student_profile = StudentProfile.objects.get(user=student)
        
        materials = StudyMaterial.objects.filter(
            section=student_profile.section,
            status='PUBLISHED'
        ).select_related('subject', 'faculty', 'section').order_by('-published_at')
        
        return materials
    except StudentProfile.DoesNotExist:
        return StudyMaterial.objects.none()


def get_material_statistics(material):
    """
    Get detailed statistics for a study material
    """
    from study_materials.models import StudyMaterialDownload, StudyMaterialView
    
    total_downloads = StudyMaterialDownload.objects.filter(
        study_material=material
    ).count()
    
    unique_downloads = StudyMaterialDownload.objects.filter(
        study_material=material
    ).values('student').distinct().count()
    
    total_views = StudyMaterialView.objects.filter(
        study_material=material
    ).count()
    
    unique_views = StudyMaterialView.objects.filter(
        study_material=material
    ).values('student').distinct().count()
    
    recent_downloads = StudyMaterialDownload.objects.filter(
        study_material=material
    ).select_related('student').order_by('-downloaded_at')[:10]
    
    return {
        'total_downloads': total_downloads,
        'unique_downloads': unique_downloads,
        'total_views': total_views,
        'unique_views': unique_views,
        'recent_downloads': recent_downloads,
    }


def get_material_download_list(material):
    """
    Get list of students who downloaded a material
    """
    from study_materials.models import StudyMaterialDownload
    
    downloads = StudyMaterialDownload.objects.filter(
        study_material=material
    ).select_related('student').order_by('-downloaded_at')
    
    return downloads


def record_material_view(material, student):
    """
    Record when a student views a material
    """
    from study_materials.models import StudyMaterialView
    
    # Create view record
    StudyMaterialView.objects.create(
        study_material=material,
        student=student
    )
    
    # Increment view count
    material.view_count += 1
    material.save(update_fields=['view_count'])


def record_material_download(material, student, ip_address=None):
    """
    Record when a student downloads a material
    """
    from study_materials.models import StudyMaterialDownload
    
    # Create download record
    StudyMaterialDownload.objects.create(
        study_material=material,
        student=student,
        ip_address=ip_address
    )
    
    # Increment download count
    material.download_count += 1
    material.save(update_fields=['download_count'])


def get_faculty_subjects_sections(faculty):
    """
    Get all subjects and sections that a faculty teaches
    Returns a list of unique (subject, section) combinations
    """
    from timetable.models import TimeSlot
    
    slots = TimeSlot.objects.filter(
        faculty=faculty
    ).select_related('subject', 'section').values(
        'subject__id',
        'subject__name',
        'subject__code',
        'section__id',
        'section__name'
    ).distinct()
    
    return slots


def get_section_enrollment_count(section):
    """
    Get number of students enrolled in a section
    """
    from profile_management.models import StudentProfile
    
    return StudentProfile.objects.filter(section=section).count()


def get_hod_department_materials(hod):
    """
    Get all study materials for HOD's department
    """
    from study_materials.models import StudyMaterial
    from profile_management.models import FacultyProfile
    
    try:
        faculty_profile = FacultyProfile.objects.get(user=hod)
        department = faculty_profile.department
        
        # Get materials for sections in this department
        materials = StudyMaterial.objects.filter(
            section__department=department
        ).select_related('subject', 'section', 'faculty').order_by('-uploaded_at')
        
        return materials
    except FacultyProfile.DoesNotExist:
        return StudyMaterial.objects.none()
