from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import datetime
from campus_management.services import ResourceAllocationService
from campus_management.models import Resource
from timetable.models import TimetableEntry, PeriodDefinition

class TimetableService:
    @staticmethod
    @transaction.atomic
    def create_timetable_entry(
        section_id: int,
        subject_id: int,
        faculty_id: int,
        period_definition_id: int,
        semester_id: int,
        room_id: int = None,
        notes: str = ""
    ) -> TimetableEntry:
        """
        Business logic to create a new timetable entry.
        Integrates with campus_management for room allocation.
        """
        allocation_id = None
        if room_id:
            try:
                resource = Resource.objects.get(resource_type='ROOM', reference_id=room_id)
            except Resource.DoesNotExist:
                resource = Resource.objects.create(resource_type='ROOM', reference_id=room_id)
            
            # Fetch period to get timings for allocation
            try:
                period = PeriodDefinition.objects.get(id=period_definition_id)
            except PeriodDefinition.DoesNotExist:
                raise ValidationError("Invalid period definition ID.")
            
            # Create a representative dummy datetime for weekly recurring class
            dummy_date = datetime(1900, 1, period.day_of_week)
            start_time = datetime.combine(dummy_date, period.start_time)
            end_time = datetime.combine(dummy_date, period.end_time)

            allocation_result = ResourceAllocationService.allocate(
                resource=resource,
                start_time=start_time,
                end_time=end_time,
                allocation_type='CLASS',
                source_app='timetable',
                source_id=0  # Temporary, will update after save
            )
            
            if not allocation_result['success']:
                raise ValidationError(f"Room allocation failed: {allocation_result['error']}")
            
            allocation_id = allocation_result['allocation'].id

        # Create entry instance
        entry = TimetableEntry(
            section_id=section_id,
            subject_id=subject_id,
            faculty_id=faculty_id,
            period_definition_id=period_definition_id,
            semester_id=semester_id,
            room_id=room_id,
            allocation_id=allocation_id,
            notes=notes or "",
            is_active=True
        )
        
        # Validation (triggers custom model clean logic)
        entry.full_clean()
        entry.save()
        
        if allocation_id:
            allocation = allocation_result['allocation']
            allocation.source_id = entry.id
            allocation.save()
            
        return entry

    @staticmethod
    @transaction.atomic
    def bulk_create_timetable_entries(section_id: int, semester_id: int, entries_data: list):
        """
        Creates multiple timetable entries for a section in one transaction.
        """
        created_entries = []
        errors = []
        
        for idx, item in enumerate(entries_data):
            try:
                entry = TimetableService.create_timetable_entry(
                    section_id=section_id,
                    semester_id=semester_id,
                    subject_id=item.get('subject_id'),
                    faculty_id=item.get('faculty_id'),
                    period_definition_id=item.get('period_definition_id'),
                    room_id=item.get('room_id'),
                    notes=item.get('notes', "")
                )
                created_entries.append(entry)
            except ValidationError as e:
                errors.append(f"Entry {idx + 1}: {str(e)}")
            except Exception as e:
                errors.append(f"Entry {idx + 1}: Generic error - {str(e)}")
        
        if errors:
            # If any entry fails, rollback occurs due to @transaction.atomic
            raise ValidationError(errors)
            
        return created_entries

    @staticmethod
    def get_section_timetable(section_id: int, semester_id: int):
        """
        Fetch the full timetable for a section, organized chronologically.
        """
        return TimetableEntry.objects.filter(
            section_id=section_id,
            semester_id=semester_id,
            is_active=True
        ).select_related(
            'subject', 'faculty', 'room', 'period_definition'
        ).order_by('period_definition__day_of_week', 'period_definition__start_time')

    @staticmethod
    def get_faculty_timetable(faculty_id: int, semester_id: int):
        """
        Fetch the teaching schedule for a faculty member.
        """
        return TimetableEntry.objects.filter(
            faculty_id=faculty_id,
            semester_id=semester_id,
            is_active=True
        ).select_related(
            'section', 'section__course', 'subject', 'room', 'period_definition'
        ).order_by('period_definition__day_of_week', 'period_definition__start_time')
