"""
Exam Management Models for College Management System
Handles exam scheduling, seating arrangements, marks entry, and hall tickets.
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


# ==================================================
# EXAM CYCLE
# ==================================================

class Exam(models.Model):
    """
    Represents an exam cycle (e.g., 'Fall 2026 End Semester', 'Midterm 1').
    An Exam groups multiple ExamSchedules for a semester.
    """

    EXAM_TYPE_CHOICES = [
        ('MIDTERM_1', 'Midterm 1'),
        ('MIDTERM_2', 'Midterm 2'),
        ('MIDTERM_3', 'Midterm 3'),
        ('END_SEMESTER', 'End Semester'),
        ('SUPPLEMENTARY', 'Supplementary'),
        ('RE_EXAM', 'Re-Examination'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    # Core fields
    name = models.CharField(
        max_length=200,
        help_text="Display name, e.g., 'End Semester Exam - Fall 2026'"
    )
    exam_type = models.CharField(
        max_length=20,
        choices=EXAM_TYPE_CHOICES,
        help_text="Type of examination"
    )
    semester = models.ForeignKey(
        'profile_management.Semester',
        on_delete=models.CASCADE,
        related_name='exams',
        help_text="Academic semester this exam belongs to"
    )
    department = models.ForeignKey(
        'core.Department',
        on_delete=models.CASCADE,
        related_name='exams',
        null=True,
        blank=True,
        help_text="Department (null = college-wide exam)"
    )

    # Schedule
    start_date = models.DateField(help_text="First exam date")
    end_date = models.DateField(help_text="Last exam date")

    # Configuration
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        help_text="Current exam cycle status"
    )
    max_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        help_text="Default maximum marks for exams in this cycle"
    )
    pass_marks_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=40,
        help_text="Pass marks percentage"
    )

    instructions = models.TextField(
        blank=True,
        help_text="General instructions for students"
    )

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exams',
        help_text="Admin/HOD who created this exam cycle"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Exam"
        verbose_name_plural = "Exams"
        indexes = [
            models.Index(fields=['semester', 'exam_type']),
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['department', 'semester']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_exam_type_display()})"

    def clean(self):
        """Validate exam dates"""
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError("Start date must be before end date")

    @property
    def is_upcoming(self):
        return self.start_date > timezone.now().date()

    @property
    def is_ongoing(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    @property
    def is_completed(self):
        return self.end_date < timezone.now().date()

    @property
    def total_subjects(self):
        return self.schedules.count()

    @property
    def total_students(self):
        """Count of unique students registered for this exam"""
        return ExamSeatingArrangement.objects.filter(
            schedule__exam=self
        ).values('student').distinct().count()


# ==================================================
# EXAM SCHEDULE
# ==================================================

class ExamSchedule(models.Model):
    """
    Schedule for a specific subject within an exam cycle.
    E.g., 'Data Structures on 2026-11-15 at 10:00 AM in Room 301'
    """

    SHIFT_CHOICES = [
        ('MORNING', 'Morning (FN)'),
        ('AFTERNOON', 'Afternoon (AN)'),
    ]

    # Core references
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='schedules',
        help_text="Parent exam cycle"
    )
    subject = models.ForeignKey(
        'timetable.Subject',
        on_delete=models.CASCADE,
        related_name='exam_schedules',
        help_text="Subject being examined"
    )
    section = models.ForeignKey(
        'core.Section',
        on_delete=models.CASCADE,
        related_name='exam_schedules',
        help_text="Section taking this exam"
    )

    # Timing
    date = models.DateField(help_text="Exam date")
    start_time = models.TimeField(help_text="Exam start time")
    end_time = models.TimeField(help_text="Exam end time")
    shift = models.CharField(
        max_length=10,
        choices=SHIFT_CHOICES,
        default='MORNING',
        help_text="Morning or afternoon shift"
    )
    duration_minutes = models.PositiveIntegerField(
        default=180,
        help_text="Exam duration in minutes"
    )

    # Room assignment
    room = models.ForeignKey(
        'timetable.Room',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_schedules',
        help_text="Room allocated for this exam"
    )

    # Configuration
    max_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override max marks (uses exam default if null)"
    )

    # Invigilators
    invigilator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invigilated_exams',
        help_text="Primary invigilator"
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes for this exam schedule"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'start_time']
        verbose_name = "Exam Schedule"
        verbose_name_plural = "Exam Schedules"
        unique_together = [['exam', 'subject', 'section']]
        indexes = [
            models.Index(fields=['exam', 'date']),
            models.Index(fields=['subject', 'date']),
            models.Index(fields=['room', 'date', 'start_time']),
            models.Index(fields=['section', 'date']),
        ]

    def __str__(self):
        return f"{self.subject.name} - {self.date} ({self.get_shift_display()})"

    def clean(self):
        """Validate schedule"""
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("Start time must be before end time")

        # Check date is within exam range
        if self.exam and self.date:
            if not (self.exam.start_date <= self.date <= self.exam.end_date):
                raise ValidationError(
                    f"Exam date must be between {self.exam.start_date} and {self.exam.end_date}"
                )

    @property
    def effective_max_marks(self):
        """Return override max_marks or fallback to exam default"""
        return self.max_marks if self.max_marks is not None else self.exam.max_marks

    @property
    def student_count(self):
        return self.seating_arrangements.count()

    @property
    def results_entered_count(self):
        return self.results.exclude(marks_obtained__isnull=True).count()


# ==================================================
# EXAM SEATING ARRANGEMENT
# ==================================================

class ExamSeatingArrangement(models.Model):
    """
    Maps a student to a specific seat in a specific exam schedule.
    """

    schedule = models.ForeignKey(
        ExamSchedule,
        on_delete=models.CASCADE,
        related_name='seating_arrangements',
        help_text="Exam schedule"
    )
    student = models.ForeignKey(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='exam_seats',
        help_text="Student assigned to this seat"
    )
    room = models.ForeignKey(
        'timetable.Room',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_seats',
        help_text="Room for this student (can differ from schedule room)"
    )
    seat_number = models.CharField(
        max_length=20,
        help_text="Seat/bench number, e.g., 'A-14', 'Row3-Seat5'"
    )

    # Attendance
    is_present = models.BooleanField(
        default=False,
        help_text="Whether student was present for exam"
    )
    marked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When attendance was marked"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['room__room_number', 'seat_number']
        verbose_name = "Seating Arrangement"
        verbose_name_plural = "Seating Arrangements"
        unique_together = [
            ['schedule', 'student'],
            ['schedule', 'room', 'seat_number'],
        ]
        indexes = [
            models.Index(fields=['student', 'schedule']),
            models.Index(fields=['schedule', 'room']),
        ]

    def __str__(self):
        room_name = self.room.room_number if self.room else "Unassigned"
        return f"{self.student.register_number} - {room_name} Seat {self.seat_number}"


# ==================================================
# EXAM RESULT
# ==================================================

class ExamResult(models.Model):
    """
    Stores marks obtained by a student in a specific exam schedule.
    """

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ENTERED', 'Entered'),
        ('VERIFIED', 'Verified'),
        ('PUBLISHED', 'Published'),
        ('WITHHELD', 'Withheld'),
    ]

    # Core references
    schedule = models.ForeignKey(
        ExamSchedule,
        on_delete=models.CASCADE,
        related_name='results',
        help_text="Exam schedule"
    )
    student = models.ForeignKey(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='exam_results',
        help_text="Student"
    )

    # Marks
    marks_obtained = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Marks obtained"
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text="Result status"
    )

    # Computed fields (populated on save)
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage scored"
    )
    is_pass = models.BooleanField(
        default=False,
        help_text="Whether student passed"
    )
    is_absent = models.BooleanField(
        default=False,
        help_text="Whether student was absent"
    )

    remarks = models.TextField(
        blank=True,
        help_text="Remarks (malpractice, medical, etc.)"
    )

    # Audit trail
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='entered_exam_results',
        help_text="Faculty who entered marks"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_exam_results',
        help_text="HOD/admin who verified marks"
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When result was published"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student__register_number']
        verbose_name = "Exam Result"
        verbose_name_plural = "Exam Results"
        unique_together = [['schedule', 'student']]
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['schedule', 'status']),
            models.Index(fields=['status', 'is_pass']),
        ]

    def __str__(self):
        marks = self.marks_obtained if self.marks_obtained is not None else "N/A"
        return f"{self.student.register_number} - {self.schedule.subject.name} - {marks}"

    def clean(self):
        """Validate result data"""
        max_marks = self.schedule.effective_max_marks
        if self.marks_obtained is not None:
            if self.marks_obtained < 0:
                raise ValidationError("Marks cannot be negative")
            if self.marks_obtained > max_marks:
                raise ValidationError(
                    f"Marks ({self.marks_obtained}) cannot exceed max marks ({max_marks})"
                )

    def save(self, *args, **kwargs):
        """Calculate percentage and pass status before saving"""
        if self.marks_obtained is not None and not self.is_absent:
            max_marks = self.schedule.effective_max_marks
            if max_marks > 0:
                self.percentage = (self.marks_obtained / max_marks) * 100
            else:
                self.percentage = Decimal('0')

            self.is_pass = self.percentage >= self.schedule.exam.pass_marks_percentage
        elif self.is_absent:
            self.marks_obtained = Decimal('0')
            self.percentage = Decimal('0')
            self.is_pass = False

        super().save(*args, **kwargs)

    @property
    def grade_letter(self):
        """Calculate letter grade from percentage"""
        if self.is_absent:
            return 'AB'
        if self.percentage is None:
            return '-'
        pct = float(self.percentage)
        if pct >= 90:
            return 'A+'
        elif pct >= 80:
            return 'A'
        elif pct >= 70:
            return 'B+'
        elif pct >= 60:
            return 'B'
        elif pct >= 50:
            return 'C'
        elif pct >= 40:
            return 'D'
        return 'F'


# ==================================================
# HALL TICKET
# ==================================================

class HallTicket(models.Model):
    """
    Generated hall ticket for a student for an exam cycle.
    Contains all the schedule info for the student's subjects.
    """

    STATUS_CHOICES = [
        ('GENERATED', 'Generated'),
        ('DOWNLOADED', 'Downloaded'),
        ('REVOKED', 'Revoked'),
    ]

    # Core references
    student = models.ForeignKey(
        'profile_management.StudentProfile',
        on_delete=models.CASCADE,
        related_name='hall_tickets',
        help_text="Student"
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='hall_tickets',
        help_text="Exam cycle"
    )

    # Hall ticket info
    ticket_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique hall ticket number"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='GENERATED'
    )

    # Eligibility
    is_eligible = models.BooleanField(
        default=True,
        help_text="Whether student is eligible to appear"
    )
    ineligibility_reason = models.TextField(
        blank=True,
        help_text="Reason if not eligible (attendance shortage, fees due, etc.)"
    )

    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_hall_tickets'
    )
    downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-generated_at']
        verbose_name = "Hall Ticket"
        verbose_name_plural = "Hall Tickets"
        unique_together = [['student', 'exam']]
        indexes = [
            models.Index(fields=['student', 'exam']),
            models.Index(fields=['ticket_number']),
        ]

    def __str__(self):
        return f"Hall Ticket {self.ticket_number} - {self.student.register_number}"
