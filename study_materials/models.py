"""
Study Materials Models for College Management System
Faculty uploads study materials/notes for students
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
import os


def study_material_file_path(instance, filename):
    """
    Generate unique path for study material files
    Format: study_materials/{semester_id}/{subject_id}/{material_id}/{filename}
    """
    return os.path.join(
        'study_materials',
        str(instance.subject.semester_number),
        str(instance.subject.id),
        str(instance.id) if instance.id else 'temp',
        filename
    )


class StudyMaterial(models.Model):
    """
    Represents study materials/notes uploaded by faculty
    """
    
    MATERIAL_TYPE_CHOICES = [
        ('NOTES', 'Lecture Notes'),
        ('REFERENCE', 'Reference Material'),
        ('SLIDES', 'Presentation Slides'),
        ('BOOK', 'E-Book/Textbook'),
        ('PAPER', 'Research Paper'),
        ('TUTORIAL', 'Tutorial'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),           # Not yet published
        ('PUBLISHED', 'Published'),   # Active and visible to students
        ('ARCHIVED', 'Archived'),     # No longer active
    ]
    
    # Core References
    subject = models.ForeignKey(
        'timetable.Subject',
        on_delete=models.CASCADE,
        related_name='study_materials',
        help_text="Subject for which material is uploaded"
    )
    section = models.ForeignKey(
        'core.Section',
        on_delete=models.CASCADE,
        related_name='study_materials',
        help_text="Section to which material is assigned"
    )
    faculty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_materials',
        help_text="Faculty who uploaded the material"
    )
    
    # Material Details
    title = models.CharField(
        max_length=255,
        help_text="Title of the study material"
    )
    description = models.TextField(
        blank=True,
        help_text="Description or summary of the material"
    )
    material_type = models.CharField(
        max_length=20,
        choices=MATERIAL_TYPE_CHOICES,
        default='NOTES',
        help_text="Type of study material"
    )
    
    # File
    file = models.FileField(
        upload_to=study_material_file_path,
        help_text="Study material file"
    )
    file_size = models.BigIntegerField(
        default=0,
        help_text="File size in bytes"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        help_text="Publication status"
    )
    
    # Tracking
    view_count = models.IntegerField(
        default=0,
        help_text="Number of times material was viewed"
    )
    download_count = models.IntegerField(
        default=0,
        help_text="Number of times material was downloaded"
    )
    
    # Metadata
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the material was published"
    )
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Study Material'
        verbose_name_plural = 'Study Materials'
        indexes = [
            models.Index(fields=['subject', 'section', 'status']),
            models.Index(fields=['faculty', 'status']),
            models.Index(fields=['-uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.subject.name} ({self.section.name})"
    
    def clean(self):
        """Validate model data"""
        # Ensure faculty is actually a faculty member
        if self.faculty and self.faculty.role.code not in ['FACULTY', 'HOD', 'ADMIN']:
            raise ValidationError("Only faculty can upload study materials")
        
        # Validate file size (max 50MB)
        if self.file and self.file.size > 50 * 1024 * 1024:
            raise ValidationError("File size cannot exceed 50MB")
    
    def save(self, *args, **kwargs):
        # Set published_at when status changes to PUBLISHED
        if self.status == 'PUBLISHED' and not self.published_at:
            self.published_at = timezone.now()
        
        # Update file size
        if self.file:
            self.file_size = self.file.size
        
        super().save(*args, **kwargs)
    
    @property
    def file_extension(self):
        """Get file extension"""
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return None
    
    @property
    def file_size_mb(self):
        """Get file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)


class StudyMaterialDownload(models.Model):
    """
    Track individual student downloads of study materials
    """
    study_material = models.ForeignKey(
        StudyMaterial,
        on_delete=models.CASCADE,
        related_name='downloads',
        help_text="Study material that was downloaded"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='material_downloads',
        help_text="Student who downloaded the material"
    )
    downloaded_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address from which download was made"
    )
    
    class Meta:
        ordering = ['-downloaded_at']
        verbose_name = 'Study Material Download'
        verbose_name_plural = 'Study Material Downloads'
        indexes = [
            models.Index(fields=['study_material', 'student']),
            models.Index(fields=['-downloaded_at']),
        ]
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.study_material.title} ({self.downloaded_at})"


class StudyMaterialView(models.Model):
    """
    Track when students view/open study materials (for analytics)
    """
    study_material = models.ForeignKey(
        StudyMaterial,
        on_delete=models.CASCADE,
        related_name='views',
        help_text="Study material that was viewed"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='material_views',
        help_text="Student who viewed the material"
    )
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-viewed_at']
        verbose_name = 'Study Material View'
        verbose_name_plural = 'Study Material Views'
        indexes = [
            models.Index(fields=['study_material', 'student']),
            models.Index(fields=['-viewed_at']),
        ]
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.study_material.title} ({self.viewed_at})"
