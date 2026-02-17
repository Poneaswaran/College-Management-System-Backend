"""
Django management command to seed grades data for testing
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import date, timedelta

from profile_management.models import StudentProfile, Semester
from timetable.models import Subject
from grades.models import CourseGrade, SemesterGPA, StudentCGPA


class Command(BaseCommand):
    help = 'Seeds dummy grade data for student REG123456 (Bala)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--register-number',
            type=str,
            default='REG123456',
            help='Register number of the student (default: REG123456)'
        )

    def handle(self, *args, **options):
        register_number = options['register_number']
        
        try:
            with transaction.atomic():
                # Get the student
                try:
                    student = StudentProfile.objects.get(register_number=register_number)
                    self.stdout.write(f"Found student: {student.user.email} ({register_number})")
                except StudentProfile.DoesNotExist:
                    self.stdout.write(self.style.ERROR(
                        f"Student with register number {register_number} not found!"
                    ))
                    return

                # Get available semesters
                semesters = Semester.objects.all().order_by('start_date')
                if not semesters.exists():
                    self.stdout.write(self.style.ERROR("No semesters found! Please create semesters first."))
                    return

                # Get available subjects
                subjects = Subject.objects.filter(is_active=True)
                if not subjects.exists():
                    self.stdout.write(self.style.ERROR("No subjects found! Please create subjects first."))
                    return

                # Sample grade data for each semester
                grade_data = [
                    # Semester 1 - Excellent performance
                    {
                        'semester_index': 0,
                        'grades': [
                            {'internal': 28, 'exam': 85, 'exam_type': 'END_SEM'},
                            {'internal': 29, 'exam': 88, 'exam_type': 'END_SEM'},
                            {'internal': 27, 'exam': 82, 'exam_type': 'END_SEM'},
                            {'internal': 30, 'exam': 90, 'exam_type': 'END_SEM'},
                            {'internal': 26, 'exam': 80, 'exam_type': 'END_SEM'},
                        ]
                    },
                    # Semester 2 - Very good performance
                    {
                        'semester_index': 1,
                        'grades': [
                            {'internal': 27, 'exam': 83, 'exam_type': 'END_SEM'},
                            {'internal': 28, 'exam': 86, 'exam_type': 'END_SEM'},
                            {'internal': 26, 'exam': 79, 'exam_type': 'END_SEM'},
                            {'internal': 29, 'exam': 87, 'exam_type': 'END_SEM'},
                            {'internal': 25, 'exam': 76, 'exam_type': 'END_SEM'},
                        ]
                    },
                    # Semester 3 - Good performance
                    {
                        'semester_index': 2,
                        'grades': [
                            {'internal': 25, 'exam': 75, 'exam_type': 'END_SEM'},
                            {'internal': 26, 'exam': 78, 'exam_type': 'END_SEM'},
                            {'internal': 24, 'exam': 72, 'exam_type': 'END_SEM'},
                            {'internal': 27, 'exam': 80, 'exam_type': 'END_SEM'},
                            {'internal': 23, 'exam': 70, 'exam_type': 'END_SEM'},
                        ]
                    },
                ]

                created_count = 0
                
                for sem_data in grade_data:
                    if sem_data['semester_index'] >= len(semesters):
                        continue
                        
                    semester = semesters[sem_data['semester_index']]
                    available_subjects = list(subjects[:len(sem_data['grades'])])
                    
                    if len(available_subjects) < len(sem_data['grades']):
                        self.stdout.write(self.style.WARNING(
                            f"Not enough subjects for semester {semester}. "
                            f"Need {len(sem_data['grades'])}, have {len(available_subjects)}"
                        ))
                        continue

                    for i, grade_info in enumerate(sem_data['grades']):
                        subject = available_subjects[i]
                        
                        # Calculate exam date (assuming end of semester)
                        exam_date = semester.end_date - timedelta(days=15)
                        
                        # Create or update grade
                        grade, created = CourseGrade.objects.update_or_create(
                            student=student,
                            subject=subject,
                            semester=semester,
                            defaults={
                                'internal_marks': grade_info['internal'],
                                'internal_max_marks': 30,
                                'exam_marks': grade_info['exam'],
                                'exam_max_marks': 100,
                                'exam_type': grade_info['exam_type'],
                                'exam_date': exam_date,
                                'is_published': True,
                                'remarks': f"Academic performance for {semester.get_number_display()}"
                            }
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(
                                f"  ✓ Created grade for {subject.name} - "
                                f"{grade.grade} ({grade.percentage:.1f}%)"
                            )
                        else:
                            self.stdout.write(
                                f"  ↻ Updated grade for {subject.name} - "
                                f"{grade.grade} ({grade.percentage:.1f}%)"
                            )
                    
                    # Calculate semester GPA
                    semester_gpa = SemesterGPA.calculate_semester_gpa(student, semester)
                    if semester_gpa:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"\n{semester.get_number_display()} - "
                                f"GPA: {semester_gpa.gpa:.2f} | "
                                f"Credits: {semester_gpa.total_credits}"
                            )
                        )

                # Calculate overall CGPA
                cgpa = StudentCGPA.calculate_cgpa(student)
                if cgpa:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"\n{'='*60}\n"
                            f"Overall CGPA: {cgpa.cgpa:.2f}\n"
                            f"Total Credits: {cgpa.total_credits}\n"
                            f"Credits Earned: {cgpa.credits_earned}\n"
                            f"Performance Trend: {cgpa.performance_trend}\n"
                            f"{'='*60}"
                        )
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✅ Successfully seeded {created_count} new grade records for {register_number}!"
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error seeding grades: {str(e)}")
            )
            raise
