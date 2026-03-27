from django.db import transaction
from django.db.models import Count
from django.core.exceptions import ValidationError
from .models import Resource, ResourceAllocation, Building, Floor, Venue
from timetable.models import TimetableEntry, PeriodDefinition
from datetime import datetime

class ResourceAllocationService:
    @staticmethod
    def check_conflict(resource, start_time, end_time):
        """
        Check if there is an overlapping allocation for the resource.
        """
        return ResourceAllocation.objects.filter(
            resource=resource,
            status='ACTIVE'
        ).filter(
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()

    @staticmethod
    def allocate(resource, start_time, end_time, allocation_type, source_app, source_id):
        """
        Allocate a resource, ensuring no overlap.
        """
        with transaction.atomic():
            if ResourceAllocationService.check_conflict(resource, start_time, end_time):
                return {'success': False, 'error': 'Resource is already allocated for the requested time period.'}

            allocation = ResourceAllocation(
                resource=resource,
                start_time=start_time,
                end_time=end_time,
                allocation_type=allocation_type,
                source_app=source_app,
                source_id=source_id,
                status='ACTIVE'
            )
            try:
                allocation.full_clean()
                allocation.save()
            except ValidationError as e:
                return {'success': False, 'error': str(e)}
            
            return {'success': True, 'allocation': allocation}

    @staticmethod
    def release(allocation_id):
        """
        Release a specific allocation.
        """
        try:
            allocation = ResourceAllocation.objects.get(id=allocation_id)
            allocation.status = 'CANCELLED'
            allocation.save()
            return {'success': True, 'message': 'Allocation successfully released.'}
        except ResourceAllocation.DoesNotExist:
            return {'success': False, 'error': 'Allocation not found.'}

class InfrastructureService:
    @staticmethod
    @transaction.atomic
    def create_full_room_setup(building_name, building_code, floor_number, venue_name, venue_type, capacity):
        """
        Creates building (if needed), floor (if needed), venue, and resource.
        """
        building, _ = Building.objects.get_or_create(code=building_code, defaults={'name': building_name})
        floor, _ = Floor.objects.get_or_create(building=building, floor_number=floor_number)
        
        venue = Venue.objects.create(
            name=venue_name,
            floor=floor,
            venue_type=venue_type,
            capacity=capacity
        )
        
        # Every venue being a ROOM resource
        resource = Resource.objects.create(
            resource_type='ROOM',
            reference_id=venue.id
        )
        
        return {'success': True, 'venue_id': venue.id, 'resource_id': resource.id, 'venue': venue}

    @staticmethod
    def create_building(name, code):
        """
        Creates a standalone building. Idempotent check on building code.
        """
        building, created = Building.objects.get_or_create(
            code=code,
            defaults={'name': name}
        )
        return {'success': True, 'id': building.id, 'created': created}

    @staticmethod
    def get_buildings_list():
        """
        Returns building list with counts of floors and rooms.
        """
        buildings = Building.objects.annotate(
            total_floors=Count('floors', distinct=True),
            total_rooms=Count('floors__venues', distinct=True) # venue count via floor relation
        ).all()
        
        return [{
            'id': b.id,
            'name': b.name,
            'code': b.code,
            'total_floors': b.total_floors,
            'total_rooms': b.total_rooms
        } for b in buildings]

    @staticmethod
    def update_building(building_id, name=None, code=None):
        """
        Updates building name and/or code.
        """
        try:
            building = Building.objects.get(id=building_id)
            if name:
                building.name = name
            if code:
                building.code = code
            building.save()
            return {'success': True}
        except Building.DoesNotExist:
            return {'success': False, 'error': 'Building not found.'}

    @staticmethod
    def delete_building(building_id):
        """
        Deletes a building and all associated floors/venues.
        """
        try:
            building = Building.objects.get(id=building_id)
            building.delete()
            return {'success': True}
        except Building.DoesNotExist:
            return {'success': False, 'error': 'Building not found.'}

class TimetableIntegrationService:
    @staticmethod
    @transaction.atomic
    def assign_room_to_timetable_entry(timetable_entry_id, room_venue_id):
        """
        Assigns a room (venue) to a specific class (TimetableEntry).
        Also creates the underlying ResourceAllocation.
        """
        try:
            entry = TimetableEntry.objects.get(id=timetable_entry_id)
            resource = Resource.objects.get(resource_type='ROOM', reference_id=room_venue_id)
            
            period = entry.period_definition
            dummy_date = datetime(1900, 1, period.day_of_week)
            start_time = datetime.combine(dummy_date, period.start_time)
            end_time = datetime.combine(dummy_date, period.end_time)

            # Check if this entry already has an allocation
            if entry.allocation_id:
                ResourceAllocationService.release(entry.allocation_id)

            allocation_result = ResourceAllocationService.allocate(
                resource=resource,
                start_time=start_time,
                end_time=end_time,
                allocation_type='CLASS',
                source_app='timetable',
                source_id=entry.id
            )

            if not allocation_result['success']:
                return allocation_result

            entry.allocation_id = allocation_result['allocation'].id
            # Note: TimetableEntry.room still points to Room model, which we might want to deprecate.
            # For now, we only update allocation_id which is the source of truth for campus_management.
            entry.save()
            
            return {'success': True, 'timetable_entry': entry.id}
            
        except TimetableEntry.DoesNotExist:
            return {'success': False, 'error': 'Timetable entry not found.'}
        except Resource.DoesNotExist:
            return {'success': False, 'error': 'Resource (room) not found.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
