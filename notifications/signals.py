"""
Django signals for notifications.
Defines custom signals that can be triggered throughout the application.
"""
from django.dispatch import Signal


# Attendance signals
attendance_session_opened = Signal()  # providing_args=["session", "students"]
attendance_session_closed = Signal()  # providing_args=["session", "absent_students"]
low_attendance_detected = Signal()  # providing_args=["student", "subject", "percentage"]

# Assignment signals
assignment_published = Signal()  # providing_args=["assignment", "students"]
assignment_graded = Signal()  # providing_args=["student", "assignment", "grade"]
submission_received = Signal()  # providing_args=["faculty", "student", "assignment"]

# Grade signals
grade_published = Signal()  # providing_args=["student", "subject", "grade", "grade_type"]
result_declared = Signal()  # providing_args=["students", "exam_name", "semester"]

# System signals
announcement_created = Signal()  # providing_args=["recipients", "title", "message"]
fee_reminder_due = Signal()  # providing_args=["students", "amount", "due_date"]
