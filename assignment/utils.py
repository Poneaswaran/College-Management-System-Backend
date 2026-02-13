"""
Utility functions for Assignment System
"""
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from datetime import datetime, timedelta


def get_active_assignments_for_student(student_profile):
    """
    Get all active (published) assignments for a student
    
    Args:
        student_profile: StudentProfile instance
    
    Returns:
        QuerySet of Assignment
    """
    from assignment.models import Assignment
    
    return Assignment.objects.filter(
        section=student_profile.section,
        semester=student_profile.semester,
        status='PUBLISHED'
    ).select_related(
        'subject',
        'section',
        'created_by'
    ).order_by('due_date')


def get_pending_assignments_for_student(student_profile):
    """
    Get assignments where student hasn't submitted yet
    
    Args:
        student_profile: StudentProfile instance
    
    Returns:
        QuerySet of Assignment
    """
    from assignment.models import Assignment, AssignmentSubmission
    
    # Get active assignments
    active_assignments = get_active_assignments_for_student(student_profile)
    
    # Filter out assignments where submission exists
    submitted_assignment_ids = AssignmentSubmission.objects.filter(
        student=student_profile,
        assignment__in=active_assignments
    ).exclude(
        status='RETURNED'  # Include returned assignments as pending
    ).values_list('assignment_id', flat=True)
    
    return active_assignments.exclude(id__in=submitted_assignment_ids)


def get_overdue_assignments_for_student(student_profile):
    """
    Get overdue assignments for a student
    
    Args:
        student_profile: StudentProfile instance
    
    Returns:
        QuerySet of Assignment
    """
    pending = get_pending_assignments_for_student(student_profile)
    
    return pending.filter(
        due_date__lt=timezone.now()
    )


def get_upcoming_assignments_for_student(student_profile, days=7):
    """
    Get assignments due in the next N days
    
    Args:
        student_profile: StudentProfile instance
        days: Number of days to look ahead
    
    Returns:
        QuerySet of Assignment
    """
    pending = get_pending_assignments_for_student(student_profile)
    
    future_date = timezone.now() + timedelta(days=days)
    
    return pending.filter(
        due_date__gte=timezone.now(),
        due_date__lte=future_date
    ).order_by('due_date')


def get_faculty_assignments(faculty_user, semester=None):
    """
    Get all assignments created by a faculty member
    
    Args:
        faculty_user: User instance with role FACULTY
        semester: Optional Semester instance to filter by
    
    Returns:
        QuerySet of Assignment
    """
    from assignment.models import Assignment
    
    assignments = Assignment.objects.filter(
        created_by=faculty_user
    ).select_related(
        'subject',
        'section',
        'semester'
    ).order_by('-created_at')
    
    if semester:
        assignments = assignments.filter(semester=semester)
    
    return assignments


def get_assignment_statistics(assignment):
    """
    Get statistics for an assignment
    
    Args:
        assignment: Assignment instance
    
    Returns:
        dict: Statistics including submission count, graded count, etc.
    """
    from assignment.models import AssignmentSubmission
    from core.models import StudentProfile
    
    # Total students in section
    total_students = StudentProfile.objects.filter(
        section=assignment.section,
        is_active=True
    ).count()
    
    # Submission statistics
    submissions = assignment.submissions.all()
    total_submissions = submissions.count()
    graded_count = submissions.filter(status='GRADED').count()
    pending_grading = submissions.filter(status__in=['SUBMITTED', 'RESUBMITTED']).count()
    
    # Late submissions
    late_submissions = submissions.filter(is_late=True).count()
    
    # Average marks (for graded submissions)
    avg_marks = 0
    if graded_count > 0:
        from assignment.models import AssignmentGrade
        grades = AssignmentGrade.objects.filter(submission__assignment=assignment)
        avg_marks = grades.aggregate(Avg('marks_obtained'))['marks_obtained__avg'] or 0
    
    return {
        'total_students': total_students,
        'total_submissions': total_submissions,
        'not_submitted': total_students - total_submissions,
        'submission_percentage': (total_submissions / total_students * 100) if total_students > 0 else 0,
        'graded_count': graded_count,
        'pending_grading': pending_grading,
        'late_submissions': late_submissions,
        'average_marks': round(avg_marks, 2),
        'average_percentage': round((avg_marks / assignment.max_marks * 100) if assignment.max_marks > 0 else 0, 2)
    }


def get_student_assignment_statistics(student_profile, semester=None):
    """
    Get assignment statistics for a student
    
    Args:
        student_profile: StudentProfile instance
        semester: Optional Semester instance to filter by
    
    Returns:
        dict: Statistics
    """
    from assignment.models import Assignment, AssignmentSubmission, AssignmentGrade
    
    # Get assignments for student's section
    assignments = Assignment.objects.filter(
        section=student_profile.section,
        status='PUBLISHED'
    )
    
    if semester:
        assignments = assignments.filter(semester=semester)
    else:
        assignments = assignments.filter(semester=student_profile.semester)
    
    total_assignments = assignments.count()
    
    # Get submissions
    submissions = AssignmentSubmission.objects.filter(
        student=student_profile,
        assignment__in=assignments
    )
    
    total_submitted = submissions.count()
    pending_submission = total_assignments - total_submitted
    
    # Graded submissions
    graded_submissions = submissions.filter(status='GRADED').count()
    
    # Average marks
    avg_marks = 0
    avg_percentage = 0
    if graded_submissions > 0:
        grades = AssignmentGrade.objects.filter(
            submission__in=submissions
        )
        avg_marks = grades.aggregate(Avg('marks_obtained'))['marks_obtained__avg'] or 0
        
        # Calculate weighted average percentage
        total_weightage = 0
        weighted_sum = 0
        for grade in grades:
            percentage = (grade.marks_obtained / grade.submission.assignment.max_marks) * 100
            weighted_sum += percentage * float(grade.submission.assignment.weightage)
            total_weightage += float(grade.submission.assignment.weightage)
        
        if total_weightage > 0:
            avg_percentage = weighted_sum / total_weightage
    
    # Overdue
    overdue = get_overdue_assignments_for_student(student_profile)
    if semester:
        overdue = overdue.filter(semester=semester)
    overdue_count = overdue.count()
    
    return {
        'total_assignments': total_assignments,
        'total_submitted': total_submitted,
        'pending_submission': pending_submission,
        'submission_percentage': (total_submitted / total_assignments * 100) if total_assignments > 0 else 0,
        'graded_count': graded_submissions,
        'pending_grading': total_submitted - graded_submissions,
        'overdue_count': overdue_count,
        'average_marks': round(avg_marks, 2),
        'average_percentage': round(avg_percentage, 2)
    }


def auto_close_expired_assignments():
    """
    Automatically close assignments that are past their deadline
    Called periodically (e.g., via cron job or celery task)
    
    Returns:
        int: Number of assignments closed
    """
    from assignment.models import Assignment
    
    now = timezone.now()
    
    # Find published assignments past their final deadline
    expired = Assignment.objects.filter(
        status='PUBLISHED'
    ).filter(
        Q(allow_late_submission=False, due_date__lt=now) |
        Q(allow_late_submission=True, late_submission_deadline__lt=now)
    )
    
    count = expired.update(status='CLOSED')
    return count


def notify_upcoming_deadlines(days=2):
    """
    Get assignments with upcoming deadlines for notifications
    
    Args:
        days: Number of days before deadline to notify
    
    Returns:
        QuerySet of Assignment
    """
    from assignment.models import Assignment
    
    now = timezone.now()
    future = now + timedelta(days=days)
    
    return Assignment.objects.filter(
        status='PUBLISHED',
        due_date__gte=now,
        due_date__lte=future
    ).select_related('subject', 'section')


def generate_assignment_report(assignment):
    """
    Generate detailed report for an assignment
    
    Args:
        assignment: Assignment instance
    
    Returns:
        dict: Detailed report data
    """
    from assignment.models import AssignmentGrade
    
    stats = get_assignment_statistics(assignment)
    
    # Grade distribution
    grades = AssignmentGrade.objects.filter(
        submission__assignment=assignment
    )
    
    grade_distribution = {
        'A+': 0, 'A': 0, 'B+': 0, 'B': 0,
        'C': 0, 'D': 0, 'F': 0
    }
    
    for grade in grades:
        letter = grade.grade_letter
        if letter in grade_distribution:
            grade_distribution[letter] += 1
    
    # Top performers
    top_submissions = grades.order_by('-marks_obtained')[:5].values(
        'submission__student__user__first_name',
        'submission__student__user__last_name',
        'marks_obtained',
        'submission__student__register_number'
    )
    
    return {
        'assignment_info': {
            'title': assignment.title,
            'subject': assignment.subject.name,
            'section': assignment.section.name,
            'due_date': assignment.due_date,
            'max_marks': assignment.max_marks,
            'weightage': assignment.weightage,
        },
        'statistics': stats,
        'grade_distribution': grade_distribution,
        'top_performers': list(top_submissions)
    }


def check_plagiarism_simple(submission1_text, submission2_text):
    """
    Simple plagiarism check (basic text similarity)
    For production, use proper plagiarism detection services
    
    Args:
        submission1_text: Text from first submission
        submission2_text: Text from second submission
    
    Returns:
        float: Similarity percentage (0-100)
    """
    # Very basic implementation - just for demonstration
    # In production, use proper algorithms or services
    
    if not submission1_text or not submission2_text:
        return 0.0
    
    # Simple word-based comparison
    words1 = set(submission1_text.lower().split())
    words2 = set(submission2_text.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    similarity = (len(intersection) / len(union)) * 100 if union else 0
    
    return round(similarity, 2)
