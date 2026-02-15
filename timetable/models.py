from django.db import models
from django.core.exceptions import ValidationError
from datetime import time

from core.models import Department, Section, User
from profile_management.models import Semester


# ==================================================
# TIMETABLE CONFIGURATION
# ==================================================

class TimetableConfiguration(models.Model):
    """
    Store configurable period settings per semester
    Allows different semesters to have different period structures
    """
    semester = models.OneToOneField(
        Semester,
        on_delete=models.CASCADE,
        related_name="timetable_config"
    )
    periods_per_day = models.PositiveIntegerField(
        default=8,
        help_text="Number of periods in a day"
    )
    default_period_duration = models.PositiveIntegerField(
        default=50,
        help_text="Default duration of each period in minutes"
    )
    day_start_time = models.TimeField(
        default=time(9, 30),
        help_text="When the academic day starts"
    )
    day_end_time = models.TimeField(
        default=time(16, 30),
        help_text="When the academic day ends"
    )
    lunch_break_after_period = models.PositiveIntegerField(
        default=4,
        help_text="After which period number the lunch break occurs"
    )
    lunch_break_duration = models.PositiveIntegerField(
        default=30,
        help_text="Lunch break duration in minutes"
    )
    short_break_duration = models.PositiveIntegerField(
        default=10,
        help_text="Short break duration between periods in minutes"
    )
    working_days = models.JSONField(
        default=list,
        help_text="List of working day numbers [1=Mon, 2=Tue, ..., 7=Sun]"
    )

    class Meta:
        verbose_name = "Timetable Configuration"
        verbose_name_plural = "Timetable Configurations"

    def __str__(self):
        return f"Config for {self.semester}"


# ==================================================
# SUBJECT
# ==================================================

class Subject(models.Model):
    """
    Subjects/courses taught in the college (e.g., Mathematics, Data Structures)
    """
    SUBJECT_TYPE_CHOICES = [
        ('THEORY', 'Theory'),
        ('LAB', 'Lab'),
        ('TUTORIAL', 'Tutorial'),
        ('ELECTIVE', 'Elective'),
        ('PROJECT', 'Project'),
    ]

    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Subject code (e.g., CS301)"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(
        blank=True,
        help_text="Course description and objectives"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="subjects"
    )
    semester_number = models.PositiveIntegerField(
        help_text="Which semester this subject is taught (1-8)"
    )
    credits = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        help_text="Credit hours for this subject"
    )
    subject_type = models.CharField(
        max_length=20

,
        choices=SUBJECT_TYPE_CHOICES,
        default='THEORY'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['department', 'semester_number', 'code']
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

    def __str__(self):
        return f"{self.code} - {self.name}"


# ==================================================
# PERIOD DEFINITION
# ==================================================

class PeriodDefinition(models.Model):
    """
    Define when periods occur (e.g., Monday Period 1: 9:30-10:20)
    """
    DAY_CHOICES = [
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
        (6, 'Saturday'),
        (7, 'Sunday'),
    ]

    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="period_definitions"
    )
    period_number = models.PositiveIntegerField(
        help_text="Period number (1, 2, 3, ... 8)"
    )
    day_of_week = models.PositiveIntegerField(
        choices=DAY_CHOICES,
        help_text="Day of the week (1=Monday, 7=Sunday)"
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(
        help_text="Duration in minutes"
    )

    class Meta:
        unique_together = ('semester', 'period_number', 'day_of_week')
        ordering = ['day_of_week', 'start_time']
        indexes = [
            models.Index(fields=['semester', 'day_of_week']),
        ]
        verbose_name = "Period Definition"
        verbose_name_plural = "Period Definitions"

    def __str__(self):
        return f"{self.get_day_of_week_display()} P{self.period_number}: {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"

    @property
    def day_name(self):
        """Return the display name of the day"""
        return self.get_day_of_week_display()


# ==================================================
# ROOM
# ==================================================

class Room(models.Model):
    """
    Classrooms, labs, seminar halls, and other venues
    """
    ROOM_TYPE_CHOICES = [
        ('CLASSROOM', 'Classroom'),
        ('LAB', 'Laboratory'),
        ('SEMINAR', 'Seminar Hall'),
        ('AUDITORIUM', 'Auditorium'),
    ]

    room_number = models.CharField(
        max_length=20,
        unique=True,
        help_text="Room identifier (e.g., 301, Lab-A)"
    )
    building = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField(
        help_text="Maximum number of students"
    )
    room_type = models.CharField(
        max_length=20,
        choices=ROOM_TYPE_CHOICES,
        default='CLASSROOM'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rooms",
        help_text="Department that primarily uses this room (optional)"
    )
    facilities = models.JSONField(
        default=dict,
        help_text='Available facilities: {"projector": true, "ac": true, etc.}'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['building', 'room_number']
        verbose_name = "Room"
        verbose_name_plural = "Rooms"

    def __str__(self):
        return f"{self.building} - {self.room_number}"


# ==================================================
# TIMETABLE ENTRY (Core Model)
# ==================================================

class TimetableEntry(models.Model):
    """
    The actual schedule - which class happens when
    Links: Section + Subject + Faculty + Period + Room
    """
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="timetable_entries"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="timetable_entries"
    )
    faculty = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_schedule",
        limit_choices_to={'role__code': 'FACULTY'},
        help_text="Faculty member teaching this class"
    )
    period_definition = models.ForeignKey(
        PeriodDefinition,
        on_delete=models.CASCADE,
        related_name="timetable_entries"
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_entries"
    )
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="timetable_entries"
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('section', 'period_definition', 'semester')
        indexes = [
            models.Index(fields=['section', 'semester']),
            models.Index(fields=['faculty', 'semester']),
            models.Index(fields=['room', 'period_definition']),
        ]
        verbose_name = "Timetable Entry"
        verbose_name_plural = "Timetable Entries"

    def __str__(self):
        return f"{self.section} - {self.subject.code} - {self.period_definition}"

    def clean(self):
        """Validate timetable entry for conflicts"""
        from .validators import TimetableConflictValidator
        
        entry_data = {
            'id': self.pk,
            'faculty_id': self.faculty_id if self.faculty else None,
            'room_id': self.room_id if self.room else None,
            'section_id': self.section_id,
            'period_definition_id': self.period_definition_id,
            'semester_id': self.semester_id,
        }
        
        is_valid, error_message = TimetableConflictValidator.validate_entry(entry_data)
        if not is_valid:
            raise ValidationError(error_message)
