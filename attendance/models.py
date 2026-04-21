"""
Attendance Models for College Management System
Period-wise attendance with image capture and session management
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
import os


def _build_check_constraint(*, expression, name):
    """Support both Django signatures: CheckConstraint(check=...) and condition=...."""
    try:
        return models.CheckConstraint(condition=expression, name=name)
    except TypeError:
        return models.CheckConstraint(check=expression, name=name)


def attendance_image_path(instance, filename):
    """
    Generate unique path for attendance images
    Format: attendance/images/{semester_id}/{section_id}/{date}/{student_id}_{timestamp}.jpg
    """
    ext = filename.split('.')[-1]
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    session = instance.session
    semester_id = session.timetable_entry.semester_id if session.timetable_entry_id else session.combined_session.semester_id
    section_id = getattr(instance.student, 'section_id', None) or instance.student.section.id

    return os.path.join(
        'attendance',
        'images',
        str(semester_id),
        str(section_id),
        session.date.strftime('%Y-%m-%d'),
        f"{instance.student.id}_{timestamp}.{ext}"
    )


class AttendanceSession(models.Model):
    """
    Represents an attendance session for a specific period
    Faculty opens session -> Students mark attendance -> Faculty closes session
    """
    
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),      # Default state, not yet opened
        ('ACTIVE', 'Active'),            # Session open, students can mark attendance
        ('CLOSED', 'Closed'),            # Session ended normally
        ('BLOCKED', 'Blocked'),          # Class cancelled, attendance blocked
        ('CANCELLED', 'Cancelled'),      # Same as blocked but with reason
    ]
    
    # Core References
    timetable_entry = models.ForeignKey(
        'timetable.TimetableEntry',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attendance_sessions',
        help_text="The timetable entry (class) for which attendance is being taken (if not a combined class)"
    )

    combined_session = models.ForeignKey(
        'timetable.CombinedClassSession',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attendance_sessions',
        help_text="The combined class session for which attendance is being taken (if combined)"
    )
    
    # Session Details
    date = models.DateField(
        help_text="Date when this attendance session occurs"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='SCHEDULED',
        db_index=True
    )
    
    # Session Control
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='opened_sessions',
        help_text="Faculty who opened this session"
    )
    opened_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the session was opened"
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the session was closed"
    )
    
    # Time Window (how long students have to mark attendance)
    attendance_window_minutes = models.PositiveIntegerField(
        default=10,
        help_text="Minutes after session opens during which students can mark attendance"
    )
    
    # Blocking/Cancellation
    cancellation_reason = models.CharField(
        max_length=500,
        blank=True,
        help_text="Reason for blocking/cancelling (e.g., 'Teacher sick', 'Holiday')"
    )
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blocked_sessions',
        help_text="Faculty/Admin who blocked this session"
    )
    blocked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the session was blocked"
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this session"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance_session'
        verbose_name = 'Attendance Session'
        verbose_name_plural = 'Attendance Sessions'
        ordering = ['-date', '-opened_at']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['timetable_entry', 'date']),
            models.Index(fields=['combined_session', 'date']),
            models.Index(fields=['status', 'opened_at']),
        ]

        constraints = [
            _build_check_constraint(
                expression=(
                    (Q(timetable_entry__isnull=False) & Q(combined_session__isnull=True))
                    | (Q(timetable_entry__isnull=True) & Q(combined_session__isnull=False))
                ),
                name='attendance_session_exactly_one_class_ref',
            ),
            models.UniqueConstraint(
                fields=['timetable_entry', 'date'],
                condition=Q(timetable_entry__isnull=False),
                name='attendance_unique_timetable_entry_date',
            ),
            models.UniqueConstraint(
                fields=['combined_session', 'date'],
                condition=Q(combined_session__isnull=False),
                name='attendance_unique_combined_session_date',
            ),
        ]
    
    def __str__(self):
        return f"{self.subject_name} - {self.sections_name} - {self.date} ({self.status})"

    @property
    def is_combined(self) -> bool:
        return bool(self.combined_session_id)

    @property
    def subject(self):
        if self.timetable_entry_id:
            return self.timetable_entry.subject
        return self.combined_session.subject

    @property
    def faculty(self):
        if self.timetable_entry_id:
            return self.timetable_entry.faculty
        return self.combined_session.faculty

    @property
    def period_definition(self):
        if self.timetable_entry_id:
            return self.timetable_entry.period_definition
        return self.combined_session.period_definition

    @property
    def semester(self):
        if self.timetable_entry_id:
            return self.timetable_entry.semester
        return self.combined_session.semester

    @property
    def sections(self):
        if self.timetable_entry_id:
            return [self.timetable_entry.section]
        return list(self.combined_session.sections.all())

    @property
    def subject_name(self) -> str:
        return self.subject.name

    @property
    def sections_name(self) -> str:
        if self.timetable_entry_id:
            return self.timetable_entry.section.name
        return " + ".join([s.name for s in self.combined_session.sections.all()])
    
    def clean(self):
        """Validate attendance session"""
        super().clean()

        # Ensure exactly one class reference is present.
        if bool(self.timetable_entry_id) == bool(self.combined_session_id):
            raise ValidationError("AttendanceSession must reference exactly one of timetable_entry or combined_session")
        
        # Ensure date is not in future beyond reasonable limit
        if self.date and self.date > (timezone.now().date() + timezone.timedelta(days=7)):
            raise ValidationError("Cannot create attendance session more than 7 days in advance")
        
        # Ensure the class reference is active
        if self.timetable_entry_id and self.timetable_entry and not self.timetable_entry.is_active:
            raise ValidationError("Cannot create attendance session for inactive timetable entry")
        if self.combined_session_id and self.combined_session and not self.combined_session.is_active:
            raise ValidationError("Cannot create attendance session for inactive combined session")
        
        # If blocking, ensure reason is provided
        if self.status in ['BLOCKED', 'CANCELLED'] and not self.cancellation_reason:
            raise ValidationError("Cancellation reason is required when blocking a session")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """Check if session is currently active for marking attendance"""
        if self.status != 'ACTIVE':
            return False
        
        if not self.opened_at:
            return False
        
        # Check if within time window
        window_end = self.opened_at + timezone.timedelta(minutes=self.attendance_window_minutes)
        return timezone.now() <= window_end
    
    @property
    def can_mark_attendance(self):
        """Check if students can currently mark attendance"""
        return self.status == 'ACTIVE' and self.is_active
    
    @property
    def time_remaining(self):
        """Get remaining time in minutes for marking attendance"""
        if not self.is_active or not self.opened_at:
            return 0
        
        window_end = self.opened_at + timezone.timedelta(minutes=self.attendance_window_minutes)
        remaining = (window_end - timezone.now()).total_seconds() / 60
        return max(0, int(remaining))
    
    @property
    def total_students(self):
        """Get total number of students in the class (1 section or 2 combined)."""
        if self.timetable_entry_id:
            return self.timetable_entry.section.student_profiles.count()

        total = 0
        for section in self.combined_session.sections.all():
            total += section.student_profiles.count()
        return total
    
    @property
    def present_count(self):
        """Get count of students marked present"""
        return self.student_attendances.filter(status='PRESENT').count()
    
    @property
    def attendance_percentage(self):
        """Calculate attendance percentage"""
        total = self.total_students
        if total == 0:
            return 0.0
        return round((self.present_count / total) * 100, 2)


class StudentAttendance(models.Model):
    """
    Individual student attendance record for a specific session
    One record per student per session (period)
    """
    
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
    ]
    
    # Core References
    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='student_attendances'
    )
    student = models.ForeignKey(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    
    # Attendance Details
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ABSENT',
        db_index=True
    )
    
    # Image Capture (REQUIRED for PRESENT status)
    attendance_image = models.ImageField(
        upload_to=attendance_image_path,
        null=True,
        blank=True,
        help_text="Photo captured during attendance marking (required for present)"
    )
    
    # Capture Metadata
    marked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When student marked attendance"
    )
    
    # Location Data (for future geo-fencing)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude where attendance was marked"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude where attendance was marked"
    )
    
    # Device Information (for audit)
    device_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="Device information (browser, OS, etc.)"
    )
    
    # Manual Override (by faculty/admin)
    is_manually_marked = models.BooleanField(
        default=False,
        help_text="True if marked manually by faculty/admin (not by student)"
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manually_marked_attendances',
        help_text="Faculty/Admin who manually marked this attendance"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Additional notes (e.g., reason for late, manual marking reason)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_attendance'
        verbose_name = 'Student Attendance'
        verbose_name_plural = 'Student Attendances'
        ordering = ['-session__date', 'student__first_name']
        unique_together = [['session', 'student']]
        indexes = [
            models.Index(fields=['session', 'student']),
            models.Index(fields=['student', 'status']),
            models.Index(fields=['session', 'status']),
            models.Index(fields=['marked_at']),
        ]
    
    def __str__(self):
        return f"{self.student.full_name} - {self.session.date} - {self.status}"
    
    def clean(self):
        """Validate student attendance"""
        super().clean()
        
        # Ensure student belongs to the class sections
        if self.session and self.student:
            if self.session.timetable_entry_id:
                section = self.session.timetable_entry.section
                if not section.student_profiles.filter(id=self.student.id).exists():
                    raise ValidationError(
                        f"Student {self.student.full_name} does not belong to section {section.name}"
                    )
            else:
                allowed = False
                for section in self.session.combined_session.sections.all():
                    if section.student_profiles.filter(id=self.student.id).exists():
                        allowed = True
                        break
                if not allowed:
                    raise ValidationError(
                        "Student does not belong to any section in this combined class"
                    )
        
        # Ensure image is provided for PRESENT status (unless manually marked)
        if self.status == 'PRESENT' and not self.is_manually_marked:
            if not self.attendance_image:
                raise ValidationError("Attendance image is required when marking present")
        
        # Validate session is not blocked
        if self.session and self.session.status in ['BLOCKED', 'CANCELLED']:
            raise ValidationError("Cannot mark attendance for blocked/cancelled sessions")
        
        # Ensure manual marking has marked_by
        if self.is_manually_marked and not self.marked_by:
            raise ValidationError("marked_by is required for manually marked attendance")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_present(self):
        """Check if student is present"""
        return self.status == 'PRESENT'
    
    @property
    def is_late(self):
        """Check if student marked late"""
        return self.status == 'LATE'


class AttendanceReport(models.Model):
    """
    Aggregated attendance report for a student in a subject
    Automatically calculated from StudentAttendance records
    """
    
    # Core References
    student = models.ForeignKey(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='attendance_reports'
    )
    subject = models.ForeignKey(
        'timetable.Subject',
        on_delete=models.CASCADE,
        related_name='attendance_reports'
    )
    semester = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='attendance_reports'
    )
    
    # Aggregate Data
    total_classes = models.PositiveIntegerField(
        default=0,
        help_text="Total number of classes held (excluding blocked/cancelled)"
    )
    present_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of classes attended"
    )
    absent_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of classes missed"
    )
    late_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times late"
    )
    
    # Calculated Fields
    attendance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Percentage of classes attended"
    )
    
    # Status
    is_below_threshold = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if attendance is below minimum required (usually 75%)"
    )
    
    # Metadata
    last_calculated = models.DateTimeField(
        auto_now=True,
        help_text="When this report was last updated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'attendance_report'
        verbose_name = 'Attendance Report'
        verbose_name_plural = 'Attendance Reports'
        ordering = ['-attendance_percentage']
        unique_together = [['student', 'subject', 'semester']]
        indexes = [
            models.Index(fields=['student', 'semester']),
            models.Index(fields=['subject', 'semester']),
            models.Index(fields=['is_below_threshold']),
            models.Index(fields=['attendance_percentage']),
        ]
    
    def __str__(self):
        return f"{self.student.full_name} - {self.subject.name} - {self.attendance_percentage}%"
    
    def calculate(self):
        """Calculate attendance statistics from StudentAttendance records"""
        attendances = StudentAttendance.objects.filter(
            student=self.student,
            session__status__in=['CLOSED'],
        ).filter(
            Q(
                session__timetable_entry__subject=self.subject,
                session__timetable_entry__semester=self.semester,
            )
            | Q(
                session__combined_session__subject=self.subject,
                session__combined_session__semester=self.semester,
            )
        ).exclude(
            session__status__in=['BLOCKED', 'CANCELLED']
        )
        
        self.total_classes = attendances.count()
        self.present_count = attendances.filter(status='PRESENT').count()
        self.absent_count = attendances.filter(status='ABSENT').count()
        self.late_count = attendances.filter(status='LATE').count()
        
        # Calculate percentage
        if self.total_classes > 0:
            # Count LATE as PRESENT for percentage calculation
            effective_present = self.present_count + self.late_count
            self.attendance_percentage = round((effective_present / self.total_classes) * 100, 2)
        else:
            self.attendance_percentage = 0.00
        
        # Check if below threshold (75%)
        self.is_below_threshold = self.attendance_percentage < 75.0
        
        self.save()
    
    @classmethod
    def update_for_student_subject(cls, student, subject, semester):
        """Update or create report for a student in a subject"""
        report, created = cls.objects.get_or_create(
            student=student,
            subject=subject,
            semester=semester
        )
        report.calculate()
        return report


def faculty_attendance_image_path(instance, filename):
    """
    Generate unique path for faculty attendance images
    Format: faculty_attendance/{type}/{date}/{faculty_id}_{timestamp}.jpg
    """
    ext = filename.split('.')[-1]
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    # Determine type based on instance state or context
    punch_type = 'punch_in' if not instance.punch_out_time else 'punch_out'
    return os.path.join(
        'faculty_attendance',
        punch_type,
        instance.date.strftime('%Y-%m-%d'),
        f"{instance.faculty.id}_{timestamp}.{ext}"
    )


class FacultyAttendance(models.Model):
    """
    Daily attendance for faculty (Punch-in/Punch-out)
    """
    faculty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='faculty_attendances'
    )
    date = models.DateField(default=timezone.now)
    
    # Punch-In Details
    punch_in_time = models.DateTimeField(null=True, blank=True)
    punch_in_photo = models.ImageField(upload_to=faculty_attendance_image_path, null=True, blank=True)
    punch_in_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    punch_in_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Punch-Out Details
    punch_out_time = models.DateTimeField(null=True, blank=True)
    punch_out_photo = models.ImageField(upload_to=faculty_attendance_image_path, null=True, blank=True)
    punch_out_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    punch_out_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Metadata
    is_late = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'faculty_attendance'
        verbose_name = 'Faculty Attendance'
        verbose_name_plural = 'Faculty Attendances'
        unique_together = [['faculty', 'date']]
        ordering = ['-date', '-punch_in_time']
        indexes = [
            models.Index(fields=['faculty', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.faculty} - {self.date}"
