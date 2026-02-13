"""
Tests for Assignment System
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from core.models import User, Role, Department, Section, StudentProfile
from timetable.models import Subject
from profile_management.models import Semester, AcademicYear
from assignment.models import Assignment, AssignmentSubmission, AssignmentGrade
from assignment.validators import AssignmentValidator


class AssignmentModelTest(TestCase):
    """Test Assignment model"""
    
    def setUp(self):
        """Set up test data"""
        # Create role
        self.faculty_role = Role.objects.create(name='FACULTY')
        self.student_role = Role.objects.create(name='STUDENT')
        
        # Create users
        self.faculty_user = User.objects.create(
            email='faculty@test.com',
            role=self.faculty_role
        )
        self.student_user = User.objects.create(
            email='student@test.com',
            role=self.student_role
        )
        
        # Create department
        self.department = Department.objects.create(
            name='Computer Science',
            code='CS'
        )
        
        # Create section
        self.section = Section.objects.create(
            name='CS-A',
            department=self.department
        )
        
        # Create academic year and semester
        self.academic_year = AcademicYear.objects.create(
            year='2025-2026',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=365)
        )
        self.semester = Semester.objects.create(
            academic_year=self.academic_year,
            number=1,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=180)
        )
        
        # Create subject
        self.subject = Subject.objects.create(
            code='CS101',
            name='Data Structures',
            department=self.department,
            semester_number=1,
            credits=4.0,
            subject_type='THEORY'
        )
        
        # Create student profile
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            register_number='2025001',
            section=self.section,
            semester=self.semester
        )
    
    def test_create_assignment(self):
        """Test creating an assignment"""
        assignment = Assignment.objects.create(
            subject=self.subject,
            section=self.section,
            semester=self.semester,
            created_by=self.faculty_user,
            title='Test Assignment',
            description='Test description',
            assignment_type='INDIVIDUAL',
            due_date=timezone.now() + timedelta(days=7),
            max_marks=100,
            weightage=10
        )
        
        self.assertEqual(assignment.title, 'Test Assignment')
        self.assertEqual(assignment.status, 'DRAFT')
        self.assertFalse(assignment.is_overdue)
        self.assertFalse(assignment.can_submit)  # Draft can't be submitted
    
    def test_assignment_can_submit(self):
        """Test assignment submission availability"""
        assignment = Assignment.objects.create(
            subject=self.subject,
            section=self.section,
            semester=self.semester,
            created_by=self.faculty_user,
            title='Test Assignment',
            description='Test description',
            assignment_type='INDIVIDUAL',
            due_date=timezone.now() + timedelta(days=7),
            max_marks=100,
            weightage=10,
            status='PUBLISHED'
        )
        
        # Should be able to submit
        self.assertTrue(assignment.can_submit)
        
        # Change status to closed
        assignment.status = 'CLOSED'
        assignment.save()
        self.assertFalse(assignment.can_submit)
    
    def test_assignment_overdue(self):
        """Test overdue assignment"""
        assignment = Assignment.objects.create(
            subject=self.subject,
            section=self.section,
            semester=self.semester,
            created_by=self.faculty_user,
            title='Test Assignment',
            description='Test description',
            assignment_type='INDIVIDUAL',
            due_date=timezone.now() - timedelta(days=1),  # Past due date
            max_marks=100,
            weightage=10,
            status='PUBLISHED'
        )
        
        self.assertTrue(assignment.is_overdue)
        self.assertFalse(assignment.can_submit)


class AssignmentSubmissionModelTest(TestCase):
    """Test AssignmentSubmission model"""
    
    def setUp(self):
        """Set up test data (reuse from AssignmentModelTest)"""
        # Create role
        self.faculty_role = Role.objects.create(name='FACULTY')
        self.student_role = Role.objects.create(name='STUDENT')
        
        # Create users
        self.faculty_user = User.objects.create(
            email='faculty@test.com',
            role=self.faculty_role
        )
        self.student_user = User.objects.create(
            email='student@test.com',
            role=self.student_role
        )
        
        # Create department
        self.department = Department.objects.create(
            name='Computer Science',
            code='CS'
        )
        
        # Create section
        self.section = Section.objects.create(
            name='CS-A',
            department=self.department
        )
        
        # Create academic year and semester
        self.academic_year = AcademicYear.objects.create(
            year='2025-2026',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=365)
        )
        self.semester = Semester.objects.create(
            academic_year=self.academic_year,
            number=1,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=180)
        )
        
        # Create subject
        self.subject = Subject.objects.create(
            code='CS101',
            name='Data Structures',
            department=self.department,
            semester_number=1,
            credits=4.0,
            subject_type='THEORY'
        )
        
        # Create student profile
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            register_number='2025001',
            section=self.section,
            semester=self.semester
        )
        
        # Create assignment
        self.assignment = Assignment.objects.create(
            subject=self.subject,
            section=self.section,
            semester=self.semester,
            created_by=self.faculty_user,
            title='Test Assignment',
            description='Test description',
            assignment_type='INDIVIDUAL',
            due_date=timezone.now() + timedelta(days=7),
            max_marks=100,
            weightage=10,
            status='PUBLISHED'
        )
    
    def test_create_submission(self):
        """Test creating a submission"""
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student_profile,
            submission_text='My submission'
        )
        
        self.assertEqual(submission.status, 'SUBMITTED')
        self.assertFalse(submission.is_late)
    
    def test_late_submission(self):
        """Test late submission flag"""
        # Create overdue assignment
        overdue_assignment = Assignment.objects.create(
            subject=self.subject,
            section=self.section,
            semester=self.semester,
            created_by=self.faculty_user,
            title='Overdue Assignment',
            description='Test description',
            assignment_type='INDIVIDUAL',
            due_date=timezone.now() - timedelta(days=1),
            max_marks=100,
            weightage=10,
            status='PUBLISHED',
            allow_late_submission=True,
            late_submission_deadline=timezone.now() + timedelta(days=2)
        )
        
        submission = AssignmentSubmission.objects.create(
            assignment=overdue_assignment,
            student=self.student_profile,
            submission_text='Late submission'
        )
        
        self.assertTrue(submission.is_late)


class AssignmentValidatorTest(TestCase):
    """Test Assignment validators"""
    
    def test_validate_file_size(self):
        """Test file size validation"""
        # This is a simplified test - in real scenario you'd need a mock file object
        pass
    
    def test_validate_marks(self):
        """Test marks validation"""
        # Test in validator directly
        pass


# Add more tests as needed
