from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from core.services import RolePermissionService

class AssignPermissionAPIView(APIView):
    # Depending on auth setup, IsAuthenticated might be required.
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role_id = request.data.get('role_id')
        permissions = request.data.get('permissions', [])
        
        if not role_id or not isinstance(permissions, list) or len(permissions) == 0:
            return Response(
                {'error': 'role_id and a non-empty permissions list are required.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        result = RolePermissionService.assign_permissions_to_role(role_id, permissions)
        
        if result['success']:
            return Response({'message': result['message']}, status=status.HTTP_200_OK)
        else:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

from core.services import CoreFilterService
from core.utils import generate_etag, check_etag

class FilterOptionsAPIView(APIView):
    """
    General filters endpoint.
    Ex: /api/core/filters/?type=room
    Ex: /api/core/filters/?building_name=CampusA
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filter_type = request.query_params.get('type')
        building_name = request.query_params.get('building_name')

        if filter_type == 'room' or building_name:
            data = CoreFilterService.get_room_filters(building_name)
            
            # ETag implementation
            etag = generate_etag(data)
            if check_etag(request, etag):
                return Response(status=status.HTTP_304_NOT_MODIFIED)
                
            response = Response({'filters': data})
            response['ETag'] = f'"{etag}"'
            return response

        return Response({'error': 'Unsupported or missing filter type.'}, status=status.HTTP_400_BAD_REQUEST)
