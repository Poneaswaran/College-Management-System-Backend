from typing import List, Dict, Union
from django.core.exceptions import ObjectDoesNotExist
from core.models import Role, Permission, RolePermission
from campus_management.models import Building, Floor, Venue
from django.db.models import Count, Sum
from django.db import transaction

class RolePermissionService:
    @staticmethod
    def assign_permissions_to_role(role_id: int, permission_codes: List[str]) -> Dict[str, Union[bool, str]]:
        """
        Assigns a list of permissions to a specific role.
        Creates permissions if they do not exist.
        """
        try:
            role = Role.objects.get(id=role_id)
            
            permissions = []
            for code in permission_codes:
                permission, _ = Permission.objects.get_or_create(code=code)
                permissions.append(permission)
            
            # create role-permissions mapping
            for permission in permissions:
                RolePermission.objects.get_or_create(role=role, permission=permission)
                
            return {'success': True, 'message': f'Successfully assigned {len(permission_codes)} permission(s) to {role.name}.'}
            
        except Role.DoesNotExist:
            return {'success': False, 'error': 'Role not found.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

class CoreFilterService:
    @staticmethod
    def get_room_filters(building_name=None):
        """
        Fetch room/infrastructure filters.
        Optimized with prefetch_related to avoid N+1 queries.
        """
        # Prefetch the entire tree: Building -> Floor -> Venue
        query = Building.objects.prefetch_related('floors__venues')

        if building_name:
            query = query.filter(name__icontains=building_name)

        buildings_data = []
        for b in query:
            # We calculate totals in-memory from prefetched data to avoid N+1
            total_venues = 0
            total_capacity = 0
            all_floors = b.floors.all()
            
            floors_data = []
            for f in all_floors:
                floor_venues = f.venues.all()
                total_venues += len(floor_venues)
                v_list = []
                for v in floor_venues:
                    total_capacity += v.capacity
                    v_list.append({'name': v.name, 'capacity': v.capacity})
                
                floors_data.append({
                    'floor_number': f.floor_number,
                    'venues': v_list
                })

            building_entry = {
                'building_name': b.name,
                'building_code': b.code,
            }
            
            if building_name:
                # Summary fields requested for building filter
                building_entry.update({
                    'total_floors': len(all_floors),
                    'total_venues': total_venues,
                    'total_capacity': total_capacity,
                    'details': floors_data
                })
            else:
                # Default listing format
                building_entry['floors'] = floors_data
                
            buildings_data.append(building_entry)
            
        return buildings_data
