import random
from django.core.management.base import BaseCommand
from django.db import connection
from tenants.models import Client
from core.models import Section, User
from profile_management.models import Semester
from timetable.models import TimetableEntry, PeriodDefinition, Subject

class Command(BaseCommand):
    help = 'Seed TimetableEntry objects for all sections and periods with subjects and faculty'

    def handle(self, *args, **options):
        try:
            tenant = Client.objects.get(schema_name='vels')
            connection.set_tenant(tenant)
        except Client.DoesNotExist:
            self.stdout.write(self.style.ERROR("Tenant 'vels' not found."))
            return

        current_semester = Semester.objects.filter(is_current=True).first()
        if not current_semester:
            self.stdout.write(self.style.ERROR("No current semester found."))
            return

        self.stdout.write(f"Seeding timetable entries for semester: {current_semester}")

        sections = Section.objects.all()
        faculties = list(User.objects.filter(role__code='FACULTY'))
        period_definitions = PeriodDefinition.objects.filter(semester=current_semester)

        if not faculties:
            self.stdout.write(self.style.ERROR("No faculty members found."))
            return

        if not period_definitions:
            self.stdout.write(self.style.ERROR("No period definitions found for the current semester."))
            return

        created_count = 0
        updated_count = 0

        for section in sections:
            # Determine the semester number for subjects (1-8)
            # Year 1 Odd -> Sem 1, Year 1 Even -> Sem 2
            # Year 2 Odd -> Sem 3, Year 2 Even -> Sem 4, etc.
            sem_number = (section.year - 1) * 2 + current_semester.number
            
            # Find subjects for this course and semester
            subjects = list(Subject.objects.filter(
                department=section.course.department,
                semester_number=sem_number
            ))
            
            if not subjects:
                # Fallback: any subject from the department
                subjects = list(Subject.objects.filter(department=section.course.department))
            
            if not subjects:
                self.stdout.write(self.style.WARNING(f"No subjects found for section {section}. Skipping."))
                continue

            for pd in period_definitions:
                subject = random.choice(subjects)
                faculty = random.choice(faculties)
                
                entry, created = TimetableEntry.objects.update_or_create(
                    section=section,
                    period_definition=pd,
                    semester=current_semester,
                    defaults={
                        "subject": subject,
                        "faculty": faculty,
                        "is_active": True,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"Finished seeding: {created_count} created, {updated_count} updated."))
