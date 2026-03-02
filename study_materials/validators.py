"""
Validators for Study Materials Module
"""
from django.core.exceptions import ValidationError
from django.utils import timezone
import os


class StudyMaterialValidator:
    """Validation logic for study materials"""
    
    ALLOWED_EXTENSIONS = [
        '.pdf', '.doc', '.docx', '.txt', '.rtf',
        '.ppt', '.pptx', '.xls', '.xlsx',
        '.zip', '.rar', '.7z',
        '.jpg', '.jpeg', '.png', '.gif',
        '.mp4', '.avi', '.mkv', '.webm'
    ]
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    @staticmethod
    def validate_file_extension(filename):
        """
        Validate that file extension is allowed
        """
        ext = os.path.splitext(filename)[1].lower()
        if ext not in StudyMaterialValidator.ALLOWED_EXTENSIONS:
            return False, f"File type '{ext}' not allowed. Allowed types: {', '.join(StudyMaterialValidator.ALLOWED_EXTENSIONS)}"
        return True, None
    
    @staticmethod
    def validate_file_size(size):
        """
        Validate file size
        """
        if size > StudyMaterialValidator.MAX_FILE_SIZE:
            max_mb = StudyMaterialValidator.MAX_FILE_SIZE / (1024 * 1024)
            actual_mb = size / (1024 * 1024)
            return False, f"File too large. Maximum size is {max_mb:.0f}MB (received {actual_mb:.2f}MB)"
        return True, None
    
    @staticmethod
    def validate_material_upload(subject, section, user):
        """
        Validate that user can upload material for this subject/section
        Check if faculty teaches this subject for this section
        """
        # HOD and Admin can upload for any subject/section
        if user.role.code in ['HOD', 'ADMIN']:
            return True, None
        
        # Faculty can only upload for subjects they teach
        if user.role.code == 'FACULTY':
            from timetable.models import TimeSlot
            
            # Check if faculty teaches this subject in this section
            teaches = TimeSlot.objects.filter(
                subject=subject,
                section=section,
                faculty=user
            ).exists()
            
            if not teaches:
                return False, "You can only upload materials for subjects you teach"
            
            return True, None
        
        return False, "Only faculty can upload study materials"
    
    @staticmethod
    def validate_material_access(material, user):
        """
        Validate if user can access a study material
        """
        # Faculty who uploaded can always access
        if material.faculty.id == user.id:
            return True, None
        
        # HOD and Admin can access all
        if user.role.code in ['HOD', 'ADMIN']:
            return True, None
        
        # Students can only access published materials for their section
        if user.role.code == 'STUDENT':
            from profile_management.models import StudentProfile
            
            try:
                student_profile = StudentProfile.objects.get(user=user)
                
                # Check if material is published
                if material.status != 'PUBLISHED':
                    return False, "This material is not yet available"
                
                # Check if material is for student's section
                if material.section != student_profile.section:
                    return False, "This material is not available for your section"
                
                return True, None
            except StudentProfile.DoesNotExist:
                return False, "Student profile not found"
        
        return False, "Access denied"
