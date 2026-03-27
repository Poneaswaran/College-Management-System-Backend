from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.dateparse import parse_datetime
from campus_management.models import Venue, Resource, Building, Floor
from campus_management.services import ResourceAllocationService, InfrastructureService, TimetableIntegrationService
from rest_framework.permissions import IsAuthenticated
from core.models import User
from core.utils import generate_etag, check_etag

class VenueListView(APIView):
    def get(self, request):
        venues = Venue.objects.select_related('floor__building').filter(is_active=True)
        data = [{
            'id': v.id,
            'name': v.name,
            'venue_type': v.venue_type,
            'capacity': v.capacity,
            'floor': v.floor.floor_number,
            'building': v.floor.building.name
        } for v in venues]
        
        # ETag implementation
        etag = generate_etag(data)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
            
        response = Response({'venues': data})
        response['ETag'] = f'"{etag}"'
        return response

class AvailableVenueListView(APIView):
    def get(self, request):
        start_time_str = request.query_params.get('start')
        end_time_str = request.query_params.get('end')

        if not start_time_str or not end_time_str:
            return Response({'error': 'Please provide start and end times.'}, status=status.HTTP_400_BAD_REQUEST)

        start_time = parse_datetime(start_time_str)
        end_time = parse_datetime(end_time_str)

        if not start_time or not end_time or start_time >= end_time:
            return Response({'error': 'Invalid date/time range.'}, status=status.HTTP_400_BAD_REQUEST)

        resources = Resource.objects.select_related().filter(resource_type='ROOM', is_active=True)
        available_venues = []

        for resource in resources:
            if not ResourceAllocationService.check_conflict(resource, start_time, end_time):
                venue = resource.venue
                if venue and venue.is_active:
                    available_venues.append({
                        'id': venue.id,
                        'name': venue.name,
                        'capacity': venue.capacity,
                        'resource_id': resource.id
                    })

        # ETag implementation
        etag = generate_etag(available_venues)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        response = Response({'available_venues': available_venues})
        response['ETag'] = f'"{etag}"'
        return response

class AllocateResourceView(APIView):
    def post(self, request):
        resource_id = request.data.get('resource_id')
        start_time_str = request.data.get('start_time')
        end_time_str = request.data.get('end_time')
        allocation_type = request.data.get('allocation_type', 'EVENT')
        source_app = request.data.get('source_app', 'rest_api')
        source_id = int(request.data.get('source_id', 0))

        if not all([resource_id, start_time_str, end_time_str]):
            return Response({'error': 'Missing required fields.'}, status=status.HTTP_400_BAD_REQUEST)

        start_time = parse_datetime(start_time_str)
        end_time = parse_datetime(end_time_str)

        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

        result = ResourceAllocationService.allocate(
            resource=resource,
            start_time=start_time,
            end_time=end_time,
            allocation_type=allocation_type,
            source_app=source_app,
            source_id=source_id
        )

        if result['success']:
            return Response({'success': True, 'allocation_id': result['allocation'].id})
        else:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

class AdminRoomCreateView(APIView):
    """
    API for admin to create building, floor, venue, and resource in one go.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # RBAC Check (Temporary manual check until middleware/permissions are finalized)
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        required_fields = ['building_name', 'building_code', 'floor_number', 'venue_name', 'venue_type', 'capacity']
        if not all(field in data for field in required_fields):
            return Response({'error': 'Missing required fields.'}, status=status.HTTP_400_BAD_REQUEST)

        result = InfrastructureService.create_full_room_setup(
            building_name=data['building_name'],
            building_code=data['building_code'],
            floor_number=data['floor_number'],
            venue_name=data['venue_name'],
            venue_type=data['venue_type'],
            capacity=data['capacity']
        )

        if result['success']:
            return Response({'success': True, 'venue_id': result['venue_id']}, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': result.get('error', 'Failed to create room.')}, status=status.HTTP_400_BAD_REQUEST)

class AssignRoomToClassView(APIView):
    """
    API to assign a room to a specific timetable entry (class).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role.code != 'ADMIN':
             return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        timetable_entry_id = request.data.get('timetable_entry_id')
        venue_id = request.data.get('venue_id')

        if not timetable_entry_id or not venue_id:
            return Response({'error': 'timetable_entry_id and venue_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        result = TimetableIntegrationService.assign_room_to_timetable_entry(
            timetable_entry_id=timetable_entry_id,
            room_venue_id=venue_id
        )

        if result['success']:
            return Response({'success': True, 'timetable_entry_id': result['timetable_entry']})
        else:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

class AdminBuildingCreateView(APIView):
    """
    API for admin to create a standalone building.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get('name')
        code = request.data.get('code')
        if not name or not code:
            return Response({'error': 'name and code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        result = InfrastructureService.create_building(name, code)
        return Response({'success': True, 'id': result['id']})

class AdminBuildingListView(APIView):
    """
    API for admin to list all buildings.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        buildings = InfrastructureService.get_buildings_list()
        
        # ETag implementation
        etag = generate_etag(buildings)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
            
        response = Response({'buildings': buildings})
        response['ETag'] = f'"{etag}"'
        return response

class AdminBuildingDetailView(APIView):
    """
    API for admin to edit or delete a specific building.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get('name')
        code = request.data.get('code')
        result = InfrastructureService.update_building(pk, name, code)
        
        if result['success']:
            return Response({'success': True, 'message': 'Building updated successfully.'})
        else:
            return Response({'error': result['error']}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        result = InfrastructureService.delete_building(pk)
        if result['success']:
            return Response({'success': True, 'message': 'Building deleted successfully.'})
        else:
            return Response({'error': result['error']}, status=status.HTTP_404_NOT_FOUND)

