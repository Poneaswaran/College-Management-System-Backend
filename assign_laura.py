import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CMS.settings')
django.setup()

from django.contrib.auth import get_user_model
from profile_management.models import FacultyProfile, Semester
from core.models import Section
from timetable.models import Subject, SectionSubjectRequirement

User = get_user_model()

def assign_faculty():
    # 1. Find Laura Palmer
    faculty_profiles = FacultyProfile.objects.filter(
        first_name="Laura",
        last_name="Palmer"
    )
    
    if not faculty_profiles.exists():
        print("Faculty 'Laura Palmer' not found.")
        # Try searching by user email if profile name matches differently
        users = User.objects.filter(email__icontains="laura")
        for u in users:
            print(f"Found user: {u.email}")
        return

    faculty_profile = faculty_profiles.first()
    user = faculty_profile.user
    print(f"Found Faculty: {faculty_profile.full_name} (User ID: {user.id})")

    # 2. Get current semester
    current_semester = Semester.objects.filter(is_current=True).first()
    if not current_semester:
        print("Current semester not found.")
        return
    print(f"Current Semester: {current_semester}")

    # 3. Get some subjects and sections
    subjects = Subject.objects.all()[:3]
    sections = Section.objects.all()[:2]

    if not subjects.exists() or not sections.exists():
        print("Not enough subjects or sections to assign.")
        return

    # 4. Create assignments
    for subject in subjects:
        for section in sections:
            req, created = SectionSubjectRequirement.objects.get_or_create(
                subject=subject,
                section=section,
                semester=current_semester,
                defaults={'faculty': user}
            )
            if created:
                print(f"Assigned {faculty_profile.full_name} to {subject.code} for {section.name}")
            else:
                req.faculty = user
                req.save()
                print(f"Updated {faculty_profile.full_name} assignment for {subject.code} in {section.name}")

if __name__ == "__main__":
    assign_faculty()
