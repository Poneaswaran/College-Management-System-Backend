from django.db import models
from datetime import time
from profile_management.models import Semester

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
        app_label = 'configuration'
        verbose_name = "Timetable Configuration"
        verbose_name_plural = "Timetable Configurations"

    def __str__(self):
        return f"Config for {self.semester}"
