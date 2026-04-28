from django.db import models
from django.conf import settings
from profile_management.models import StudentProfile
from core.models import Department

class Grievance(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    CATEGORY_CHOICES = [
        ('ACADEMIC', 'Academic'),
        ('FACILITY', 'Facility/Infrastructure'),
        ('HOSTEL', 'Hostel'),
        ('ADMINISTRATIVE', 'Administrative'),
        ('DISCIPLINARY', 'Disciplinary'),
        ('OTHER', 'Other'),
    ]

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='grievances'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='grievances'
    )
    subject = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Resolution
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_grievances'
    )
    resolution_note = models.TextField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['department', 'status']),
        ]

    def __str__(self):
        return f"{self.subject} - {self.student.register_number} ({self.status})"
