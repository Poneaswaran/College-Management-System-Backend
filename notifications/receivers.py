"""
Signal receivers for automatic notification creation.
Connects to Django model signals and triggers notification services.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from notifications.attendance import services as attendance_services
from notifications.assignments import services as assignment_services
from notifications.grades import services as grade_services


logger = logging.getLogger(__name__)


# ============================================================================
# ATTENDANCE SIGNAL RECEIVERS
# ============================================================================

@receiver(post_save, sender='attendance.AttendanceSession')
def handle_attendance_session_save(sender, instance, created, **kwargs):
    """
    Handle AttendanceSession save event.
    Creates notifications when session status changes.
    """
    try:
        # Import here to avoid circular imports
        from attendance.models import AttendanceSession
        
        # Check if status changed to ACTIVE (session opened)
        if hasattr(instance, 'status') and instance.status == 'ACTIVE':
            # Get all students in the section
            if hasattr(instance, 'section'):
                students = list(
                    instance.section.students.all()
                ) if hasattr(instance.section, 'students') else []
                
                if students:
                    actor = instance.created_by if hasattr(instance, 'created_by') else None
                    attendance_services.notify_session_opened(
                        session=instance,
                        students=students,
                        actor=actor
                    )
        
        # Check if status changed to CLOSED (session closed)
        elif hasattr(instance, 'status') and instance.status == 'CLOSED':
            # Get students who did NOT mark attendance
            if hasattr(instance, 'section') and hasattr(instance, 'marks'):
                all_students = set(instance.section.students.all()) if hasattr(instance.section, 'students') else set()
                marked_students = set(
                    mark.student for mark in instance.marks.all()
                ) if hasattr(instance, 'marks') else set()
                
                absent_students = list(all_students - marked_students)
                
                if absent_students:
                    actor = instance.updated_by if hasattr(instance, 'updated_by') else None
                    attendance_services.notify_session_closed_absent(
                        session=instance,
                        absent_students=absent_students,
                        actor=actor
                    )
    
    except Exception as e:
        logger.error(f"Error in attendance session signal receiver: {str(e)}")


# ============================================================================
# ASSIGNMENT SIGNAL RECEIVERS
# ============================================================================

@receiver(post_save, sender='assignment.Assignment')
def handle_assignment_save(sender, instance, created, **kwargs):
    """
    Handle Assignment save event.
    Creates notifications when assignment is published.
    """
    try:
        # Check if status changed to PUBLISHED
        if hasattr(instance, 'status') and instance.status == 'PUBLISHED':
            # Get all students in the section/course
            students = []
            
            if hasattr(instance, 'section'):
                students = list(
                    instance.section.students.all()
                ) if hasattr(instance.section, 'students') else []
            elif hasattr(instance, 'course'):
                # Get all students enrolled in the course
                from django.contrib.auth import get_user_model
                User = get_user_model()
                students = list(User.objects.filter(
                    role='STUDENT',
                    studentprofile__course=instance.course
                ))
            
            if students:
                actor = instance.created_by if hasattr(instance, 'created_by') else None
                assignment_services.notify_assignment_published(
                    assignment=instance,
                    students=students,
                    actor=actor
                )
    
    except Exception as e:
        logger.error(f"Error in assignment signal receiver: {str(e)}")


@receiver(post_save, sender='grades.Grade')
def handle_grade_save(sender, instance, created, **kwargs):
    """
    Handle Grade save event (for assignment grades).
    Creates notification when assignment is graded.
    """
    try:
        # Only notify on new grades
        if created and hasattr(instance, 'student') and hasattr(instance, 'assignment'):
            grade_value = instance.grade if hasattr(instance, 'grade') else "N/A"
            actor = instance.graded_by if hasattr(instance, 'graded_by') else None
            
            assignment_services.notify_assignment_graded(
                student=instance.student,
                assignment=instance.assignment,
                grade_value=str(grade_value),
                actor=actor
            )
    
    except Exception as e:
        logger.error(f"Error in grade signal receiver (assignment): {str(e)}")


@receiver(post_save, sender='assignment.Submission')
def handle_submission_save(sender, instance, created, **kwargs):
    """
    Handle Submission save event.
    Notifies faculty when student submits an assignment.
    """
    try:
        # Only notify on new submissions
        if created and hasattr(instance, 'assignment') and hasattr(instance, 'student'):
            # Determine faculty to notify
            faculty = None
            
            if hasattr(instance.assignment, 'created_by'):
                faculty = instance.assignment.created_by
            elif hasattr(instance.assignment, 'subject'):
                # Get faculty teaching this subject
                subject = instance.assignment.subject
                if hasattr(subject, 'faculty'):
                    faculty = subject.faculty
            
            if faculty:
                assignment_services.notify_submission_received(
                    faculty=faculty,
                    student=instance.student,
                    assignment=instance.assignment
                )
    
    except Exception as e:
        logger.error(f"Error in submission signal receiver: {str(e)}")


# ============================================================================
# CUSTOM SIGNAL RECEIVERS (for custom signals defined in signals.py)
# ============================================================================

from notifications.signals import (
    attendance_session_opened,
    attendance_session_closed,
    low_attendance_detected,
    assignment_published,
    assignment_graded,
    submission_received,
    grade_published,
    result_declared,
    announcement_created,
    fee_reminder_due,
)


@receiver(low_attendance_detected)
def handle_low_attendance(sender, student, subject, percentage, **kwargs):
    """Handle low attendance alert."""
    try:
        threshold = kwargs.get('threshold', 75.0)
        attendance_services.notify_low_attendance(
            student=student,
            subject=subject,
            percentage=percentage,
            threshold=threshold
        )
    except Exception as e:
        logger.error(f"Error in low attendance signal receiver: {str(e)}")


@receiver(grade_published)
def handle_grade_published(sender, student, subject, grade, grade_type, **kwargs):
    """Handle grade published notification."""
    try:
        actor = kwargs.get('actor')
        grade_services.notify_grade_published(
            student=student,
            subject=subject,
            grade_value=grade,
            grade_type=grade_type,
            actor=actor
        )
    except Exception as e:
        logger.error(f"Error in grade published signal receiver: {str(e)}")


@receiver(result_declared)
def handle_result_declared(sender, students, exam_name, semester, **kwargs):
    """Handle result declaration notification."""
    try:
        actor = kwargs.get('actor')
        grade_services.notify_result_declared(
            students=students,
            exam_name=exam_name,
            semester=semester,
            actor=actor
        )
    except Exception as e:
        logger.error(f"Error in result declared signal receiver: {str(e)}")


@receiver(announcement_created)
def handle_announcement_created(sender, recipients, title, message, **kwargs):
    """Handle announcement creation."""
    try:
        from notifications.system.services import create_announcement
        
        action_url = kwargs.get('action_url', '')
        priority = kwargs.get('priority', 'MEDIUM')
        actor = kwargs.get('actor')
        
        create_announcement(
            recipients=recipients,
            title=title,
            message=message,
            action_url=action_url,
            priority=priority,
            actor=actor
        )
    except Exception as e:
        logger.error(f"Error in announcement signal receiver: {str(e)}")


@receiver(fee_reminder_due)
def handle_fee_reminder(sender, students, amount, due_date, **kwargs):
    """Handle fee reminder notification."""
    try:
        from notifications.system.services import create_fee_reminder
        
        semester = kwargs.get('semester')
        create_fee_reminder(
            students=students,
            amount_due=amount,
            due_date=due_date,
            semester=semester
        )
    except Exception as e:
        logger.error(f"Error in fee reminder signal receiver: {str(e)}")
