from django.db import transaction
from django.db.models import Count
from django.core.exceptions import ValidationError
from .models import Resource, ResourceAllocation, Building, Floor, Venue
from timetable.models import TimetableEntry, PeriodDefinition
from datetime import datetime
from collections import Counter

class RolePermissionService:
    # (Implementation remains same, placeholder skipped for brevity)
    pass 

class ResourceAllocationService:
    @staticmethod
    def check_conflict(resource, start_time, end_time):
        overlapping = ResourceAllocation.objects.filter(
            resource=resource, status='ACTIVE', start_time__lt=end_time, end_time__gt=start_time
        )
        return overlapping.exists()

    @staticmethod
    def allocate(resource, start_time, end_time, allocation_type, source_app, source_id):
        if ResourceAllocationService.check_conflict(resource, start_time, end_time):
            return {'success': False, 'error': 'Resource already allocated for this time range.'}
        allocation = ResourceAllocation.objects.create(
            resource=resource, start_time=start_time, end_time=end_time,
            allocation_type=allocation_type, source_app=source_app, source_id=source_id
        )
        return {'success': True, 'allocation': allocation}

    @staticmethod
    def release(allocation_id):
        try:
            allocation = ResourceAllocation.objects.get(id=allocation_id)
            allocation.status = 'COMPLETED'
            allocation.save()
            return {'success': True}
        except ResourceAllocation.DoesNotExist:
            return {'success': False, 'error': 'Allocation not found.'}

class InfrastructureService:
    @staticmethod
    @transaction.atomic
    def create_full_room_setup(building_name, building_code, floor_number, venue_name, venue_type, capacity):
        building, _ = Building.objects.get_or_create(code=building_code, defaults={'name': building_name})
        floor, _ = Floor.objects.get_or_create(building=building, floor_number=floor_number)
        venue = Venue.objects.create(name=venue_name, floor=floor, venue_type=venue_type, capacity=capacity)
        resource = Resource.objects.create(resource_type='ROOM', reference_id=venue.id)
        return {'success': True, 'venue_id': venue.id, 'resource_id': resource.id}

    @staticmethod
    def create_building(name, code):
        building, created = Building.objects.get_or_create(code=code, defaults={'name': name})
        return {'success': True, 'id': building.id, 'created': created}

    @staticmethod
    def get_buildings_list():
        buildings = Building.objects.annotate(
            total_floors=Count('floors', distinct=True),
            total_rooms=Count('floors__venues', distinct=True)
        ).all()
        return [{
            'id': b.id, 'name': b.name, 'code': b.code,
            'total_floors': b.total_floors, 'total_rooms': b.total_rooms
        } for b in buildings]

    @staticmethod
    def update_building(building_id, name=None, code=None):
        try:
            building = Building.objects.get(id=building_id)
            if name: building.name = name
            if code: building.code = code
            building.save()
            return {'success': True}
        except Building.DoesNotExist:
            return {'success': False, 'error': 'Building not found.'}

    @staticmethod
    def delete_building(building_id):
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
        try:
            entry = TimetableEntry.objects.get(id=timetable_entry_id)
            resource = Resource.objects.get(resource_type='ROOM', reference_id=room_venue_id)
            period = entry.period_definition
            dummy_date = datetime(1900, 1, period.day_of_week)
            start_time = datetime.combine(dummy_date, period.start_time)
            end_time = datetime.combine(dummy_date, period.end_time)

            if entry.allocation_id:
                ResourceAllocationService.release(entry.allocation_id)

            allocation_result = ResourceAllocationService.allocate(
                resource=resource, start_time=start_time, end_time=end_time,
                allocation_type='CLASS', source_app='timetable', source_id=entry.id
            )

            if not allocation_result['success']:
                return allocation_result

            entry.allocation_id = allocation_result['allocation'].id
            entry.save()
            return {'success': True, 'timetable_entry': entry.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def bulk_assign_section_to_venue(section_id, venue_id):
        entries = TimetableEntry.objects.filter(section_id=section_id, is_active=True)
        if not entries.exists():
            return {'success': False, 'error': 'No timetable entries found for this section.'}

        results, errors = [], []
        for entry in entries:
            res = TimetableIntegrationService.assign_room_to_timetable_entry(entry.id, venue_id)
            if res['success']: results.append(entry.id)
            else: errors.append(f"Day {entry.period_definition.day_of_week} Period {entry.period_definition.period_number}: {res['error']}")

        return {'success': len(results) > 0, 'assigned_count': len(results), 'errors': errors}

    @staticmethod
    def get_assigned_venues_overview():
        """
        Returns an overview grouped by section. Highlighting venue changes within the schedule.
        """
        entries = TimetableEntry.objects.filter(allocation_id__isnull=False, is_active=True).select_related(
            'section', 'section__course', 'period_definition', 'subject'
        )
        
        allocation_ids = [e.allocation_id for e in entries]
        allocations = ResourceAllocation.objects.filter(id__in=allocation_ids).select_related('resource')
        alloc_map = {a.id: a for a in allocations}
        
        section_groups = {}
        for entry in entries:
            s_id = entry.section.id
            if s_id not in section_groups:
                section_groups[s_id] = {
                    'section_name': f"{entry.section.course.code} {entry.section.year}-{entry.section.name}",
                    'entries': []
                }
            
            alloc = alloc_map.get(entry.allocation_id)
            if alloc and alloc.resource.resource_type == 'ROOM':
                v = alloc.resource.venue
                section_groups[s_id]['entries'].append({
                    'entry': entry,
                    'venue_id': v.id,
                    'venue_name': v.name,
                    'building': v.floor.building.name
                })
        
        data = []
        for s_id, group in section_groups.items():
            # Determine the major venue (most used)
            venue_counts = Counter([e['venue_id'] for e in group['entries']])
            major_venue_id = venue_counts.most_common(1)[0][0]
            
            # Get major venue info
            major_v_info = next(e for e in group['entries'] if e['venue_id'] == major_venue_id)
            
            section_data = {
                'section_id': s_id,
                'section_name': group['section_name'],
                'primary_venue': major_v_info['venue_name'],
                'primary_building': major_v_info['building'],
                'schedule': []
            }
            
            for item in group['entries']:
                e = item['entry']
                sched_item = {
                    'id': e.id,
                    'day': e.period_definition.get_day_of_week_display(),
                    'period': e.period_definition.period_number,
                    'subject': e.subject.name
                }
                # ONLY if the venue is different from the primary venue, we add it
                if item['venue_id'] != major_venue_id:
                    sched_item['changed_venue'] = item['venue_name']
                    sched_item['changed_building'] = item['building']
                
                section_data['schedule'].append(sched_item)
            
            data.append(section_data)
            
        return sorted(data, key=lambda x: x['section_name'])
