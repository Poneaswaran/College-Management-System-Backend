from django.core.exceptions import ValidationError
from .services import ResourceAllocationService
from .models import ResourceAllocation

class ResourceAllocationValidator:
    @staticmethod
    def validate_allocation(resource, start_time, end_time):
        if ResourceAllocationService.check_conflict(resource, start_time, end_time):
            raise ValidationError("Double booking is not possible: overlapping allocation exists for this resource.")

class TimetableIntegrationValidator:
    @staticmethod
    def ensure_allocation_exists(source_app, source_id):
        # Using string matching since source_app is string 'timetable'
        exists = ResourceAllocation.objects.filter(
            source_app=source_app, 
            source_id=source_id, 
            status='ACTIVE'
        ).exists()
        if not exists:
            # We strictly enforce that a valid allocation should exist before TimetableEntry finalizes
            raise ValidationError("Timetable entry cannot bypass allocation service. Room allocation is missing.")
