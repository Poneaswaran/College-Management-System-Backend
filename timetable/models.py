from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from datetime import time

from core.models import Department, Section, User
from profile_management.models import Semester


# ==================================================
# TIMETABLE CONFIGURATION
# ==================================================

from configuration.models import TimetableConfiguration


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
    allocation_id = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="ID of ResourceAllocation from campus_management"
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

        # Ensure that room assignment has a corresponding campus_management ResourceAllocation
        if self.room_id and not self.allocation_id:
            from campus_management.validators import TimetableIntegrationValidator
            # In an actual request, the source_id might be 0 before saving, so we check if allocation_id is set
            raise ValidationError("Timetable entry cannot bypass allocation service. Room allocation is missing.")


# ==================================================
# SECTION COMBINING (Option A)
# ==================================================


class DepartmentSectionCombinePolicy(models.Model):
    """Configures whether/how sections may be combined for a department.

    This is intentionally department-scoped (not course-scoped) per product
    requirement. Hard ceiling of 2 sections is enforced.
    """

    department = models.OneToOneField(
        Department,
        on_delete=models.CASCADE,
        related_name='section_combine_policy',
    )
    enabled = models.BooleanField(default=False)
    max_sections = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(2)],
        help_text="Maximum number of sections allowed in a combined class for this department (1-2).",
    )
    same_course_only = models.BooleanField(
        default=True,
        help_text="If true, only sections from the same Course may be combined.",
    )
    allow_cross_department = models.BooleanField(
        default=False,
        help_text="If true, allows combining with explicitly allowed partner departments.",
    )
    allowed_partner_departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='allowed_combine_partners',
        help_text="Departments this department is allowed to combine with (used only when allow_cross_department is true).",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Department Section Combine Policy'
        verbose_name_plural = 'Department Section Combine Policies'

    def clean(self):
        if self.max_sections > 2:
            raise ValidationError("max_sections cannot exceed 2.")
        if not self.allow_cross_department and self.pk:
            # Keep partner list empty when cross-department combining is disabled.
            if self.allowed_partner_departments.exists():
                raise ValidationError("allowed_partner_departments must be empty when allow_cross_department is false.")

    def __str__(self):
        return f"{self.department.code} policy (enabled={self.enabled}, max={self.max_sections})"


class CombinedClassSession(models.Model):
    """A single teaching session shared by up to 2 sections.

    This exists alongside TimetableEntry (Option A). Section timetables should
    include these sessions for any section listed in `sections`.
    """

    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name='combined_class_sessions',
    )
    period_definition = models.ForeignKey(
        PeriodDefinition,
        on_delete=models.CASCADE,
        related_name='combined_class_sessions',
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='combined_class_sessions',
    )
    faculty = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='combined_teaching_schedule',
        limit_choices_to={'role__code': 'FACULTY'},
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='combined_class_sessions',
    )
    allocation_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of ResourceAllocation from campus_management",
    )
    sections = models.ManyToManyField(
        Section,
        through='CombinedClassSessionSection',
        related_name='combined_class_sessions',
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_combined_sessions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['semester', 'period_definition']),
            models.Index(fields=['faculty', 'semester']),
            models.Index(fields=['room', 'period_definition']),
        ]
        verbose_name = 'Combined Class Session'
        verbose_name_plural = 'Combined Class Sessions'

    def __str__(self):
        return f"Combined {self.subject.code} @ {self.period_definition} ({self.semester_id})"

    def clean(self):
        # Mirror TimetableEntry allocation constraint.
        if self.room_id and not self.allocation_id:
            raise ValidationError("Combined class session cannot bypass allocation service. Room allocation is missing.")


class CombinedClassSessionSection(models.Model):
    combined_session = models.ForeignKey(
        CombinedClassSession,
        on_delete=models.CASCADE,
        related_name='section_links',
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='combined_session_links',
    )

    class Meta:
        unique_together = ('combined_session', 'section')
        verbose_name = 'Combined Class Session Section'
        verbose_name_plural = 'Combined Class Session Sections'

    def __str__(self):
        return f"{self.combined_session_id} <-> {self.section_id}"


# ==================================================
# NON-ROOM PERIOD
# ==================================================

class NonRoomPeriod(models.Model):
    """
    Records a period slot where a section does NOT need a classroom.
    This is the primary mechanism that reduces peak simultaneous room demand
    from 17 to 13-14, making the schedule feasible with only 14 rooms.

    Types:
      LAB     -> section is in a lab (lab room booked via TimetableEntry)
      PT      -> physical education / sports (outdoor, no room needed)
      LIBRARY -> library period (library space, not a classroom)
      FREE    -> free / self-study / overflow-compensation period
    """
    NON_ROOM_TYPES = [
        ('LAB',     'Lab Practical'),
        ('PT',      'Physical Education'),
        ('LIBRARY', 'Library Period'),
        ('FREE',    'Free / Self-Study'),
    ]

    section           = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='non_room_periods'
    )
    period_definition = models.ForeignKey(
        PeriodDefinition,
        on_delete=models.CASCADE,
        related_name='non_room_periods'
    )
    period_type = models.CharField(max_length=20, choices=NON_ROOM_TYPES)
    semester    = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='non_room_periods'
    )
    notes      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('section', 'period_definition', 'semester')
        indexes = [
            models.Index(fields=['semester', 'period_definition']),
            models.Index(fields=['section', 'semester']),
        ]
        verbose_name        = "Non-Room Period"
        verbose_name_plural = "Non-Room Periods"

    def __str__(self):
        return (
            f"{self.section} | {self.get_period_type_display()} | {self.period_definition}"
        )


# ==================================================
# OVERFLOW LOG
# ==================================================

class OverflowLog(models.Model):
    """
    Append-only record of every time a section was displaced from a room.
    The auto-scheduler reads aggregated counts to enforce fairness:
    sections displaced most often get priority in the next allocation run.

    Keep as a log (not a counter) so admins can audit per-day history.
    """
    section           = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='overflow_logs'
    )
    period_definition = models.ForeignKey(
        PeriodDefinition,
        on_delete=models.CASCADE,
        related_name='overflow_logs'
    )
    semester = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='overflow_logs'
    )
    overflow_date = models.DateField(
        help_text="Calendar date on which the overflow occurred"
    )
    reason = models.CharField(
        max_length=100,
        default='room_shortage',
        choices=[
            ('room_shortage',  'Room Shortage'),
            ('maintenance',    'Room Under Maintenance'),
            ('event',          'Room Occupied by Event'),
        ]
    )
    compensated = models.BooleanField(
        default=False,
        help_text="True once this section has been given compensatory priority"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['section', 'semester']),
            models.Index(fields=['semester', 'overflow_date']),
            models.Index(fields=['compensated']),
        ]
        verbose_name        = "Overflow Log"
        verbose_name_plural = "Overflow Logs"

    def __str__(self):
        return f"{self.section} overflowed on {self.overflow_date} ({self.reason})"


# ==================================================
# LAB ROTATION SCHEDULE
# ==================================================

class LabRotationSchedule(models.Model):
    """
    Precomputed mapping: which section uses which lab on which period slot.
    Generated once per semester by LabRotationGenerator.generate().
    Ensures:
      - No two sections share a lab at the same period
      - Every section gets exactly one lab session per week
      - Labs are available as classrooms during all other periods
    """
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='lab_rotations'
    )
    lab = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='lab_rotations',
        limit_choices_to={'room_type': 'LAB'}
    )
    period_definition = models.ForeignKey(
        PeriodDefinition,
        on_delete=models.CASCADE,
        related_name='lab_rotations'
    )
    semester = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='lab_rotations'
    )
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Each section gets exactly one lab slot per semester
        unique_together = ('section', 'semester')
        indexes = [
            models.Index(fields=['lab', 'period_definition', 'semester']),
            models.Index(fields=['semester', 'is_active']),
        ]
        verbose_name        = "Lab Rotation Schedule"
        verbose_name_plural = "Lab Rotation Schedules"

    def __str__(self):
        return (
            f"{self.section} -> {self.lab.room_number} @ {self.period_definition}"
        )

    def clean(self):
        """Prevent two sections from occupying the same lab at the same period."""
        if not self.lab_id or not self.period_definition_id or not self.semester_id:
            return
        conflict = LabRotationSchedule.objects.filter(
            lab=self.lab,
            period_definition=self.period_definition,
            semester=self.semester,
            is_active=True
        ).exclude(pk=self.pk)
        if conflict.exists():
            raise ValidationError(
                f"Lab {self.lab.room_number} is already assigned to another section "
                f"at {self.period_definition}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ==================================================
# SECTION SUBJECT REQUIREMENT  (Item 2)
# ==================================================

class SectionSubjectRequirement(models.Model):
    """
    Defines how many periods per week a subject must be scheduled for a
    given section in a given semester, and which faculty teaches it.

    The SubjectDistributionService reads these rows to fill the timetable
    grid before RoomAllocatorService assigns rooms.
    """
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='subject_requirements',
    )
    semester = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='subject_requirements',
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='section_requirements',
    )
    faculty = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_requirements',
        limit_choices_to={'role__code': 'FACULTY'},
        help_text="Faculty assigned to teach this subject to this section",
    )
    periods_per_week = models.PositiveIntegerField(
        default=1,
        help_text="Number of teaching periods required per week",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('section', 'semester', 'subject')
        ordering = ['section', 'subject']
        verbose_name = "Section Subject Requirement"
        verbose_name_plural = "Section Subject Requirements"

    def __str__(self):
        return (
            f"{self.section} | {self.subject.code} | "
            f"{self.periods_per_week}p/wk"
        )


# ==================================================
# ROOM MAINTENANCE BLOCK  (Item 4)
# ==================================================

class RoomMaintenanceBlock(models.Model):
    """
    Records a date range during which a room is unavailable due to
    maintenance.  RescheduleService uses these rows to nullify affected
    TimetableEntry room assignments and re-allocate rooms for impacted
    PeriodDefinition slots.
    """
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='maintenance_blocks',
        help_text="Room that will be unavailable",
    )
    start_date = models.DateField(
        help_text="First date the room is under maintenance (inclusive)",
    )
    end_date = models.DateField(
        help_text="Last date the room is under maintenance (inclusive)",
    )
    reason = models.CharField(
        max_length=255,
        help_text="Short description of the maintenance reason",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to cancel/withdraw this maintenance block",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['room', 'start_date', 'end_date']),
            models.Index(fields=['is_active', 'start_date']),
        ]
        verbose_name = "Room Maintenance Block"
        verbose_name_plural = "Room Maintenance Blocks"

    def __str__(self):
        return (
            f"{self.room} maintenance: {self.start_date} → {self.end_date} "
            f"({'active' if self.is_active else 'inactive'})"
        )

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("end_date must be on or after start_date.")
