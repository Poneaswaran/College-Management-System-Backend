from typing import List, Dict, Union
from django.core.exceptions import ObjectDoesNotExist
from core.models import Role, Permission, RolePermission, Department, Course, Section, User
from timetable.models import PeriodDefinition

class AcademicStructureService:
    @staticmethod
    def create_department(name, code, is_active=True):
        dept, created = Department.objects.get_or_create(code=code, defaults={'name': name, 'is_active': is_active})
        return {'success': True, 'id': dept.id, 'created': created}

    @staticmethod
    def create_course(dept_id, name, code, duration_years=4):
        try:
            dept = Department.objects.get(id=dept_id)
            course, created = Course.objects.get_or_create(
                department=dept, code=code, 
                defaults={'name': name, 'duration_years': duration_years}
            )
            return {'success': True, 'id': course.id, 'created': created}
        except Department.DoesNotExist:
            return {'success': False, 'error': 'Department not found.'}

    @staticmethod
    def create_section(course_id, name, code, year=1):
        try:
            course = Course.objects.get(id=course_id)
            section, created = Section.objects.get_or_create(
                course=course, code=code, year=year,
                defaults={'name': name}
            )
            return {'success': True, 'id': section.id, 'created': created}
        except Course.DoesNotExist:
            return {'success': False, 'error': 'Course not found.'}

    @staticmethod
    def update_department(dept_id, name=None, code=None, is_active=None):
        try:
            dept = Department.objects.get(id=dept_id)
            if name: dept.name = name
            if code: dept.code = code
            if is_active is not None: dept.is_active = is_active
            dept.save()
            return {'success': True}
        except Department.DoesNotExist:
            return {'success': False, 'error': 'Department not found.'}

    @staticmethod
    def delete_department(dept_id):
        try:
            dept = Department.objects.get(id=dept_id)
            dept.delete()
            return {'success': True}
        except Department.DoesNotExist:
            return {'success': False, 'error': 'Department not found.'}

    @staticmethod
    def update_course(course_id, name=None, code=None, duration_years=None):
        try:
            course = Course.objects.get(id=course_id)
            if name: course.name = name
            if code: course.code = code
            if duration_years: course.duration_years = duration_years
            course.save()
            return {'success': True}
        except Course.DoesNotExist:
            return {'success': False, 'error': 'Course not found.'}

    @staticmethod
    def delete_course(course_id):
        try:
            course = Course.objects.get(id=course_id)
            course.delete()
            return {'success': True}
        except Course.DoesNotExist:
            return {'success': False, 'error': 'Course not found.'}

    @staticmethod
    def update_section(section_id, name=None, code=None, year=None):
        try:
            section = Section.objects.get(id=section_id)
            if name: section.name = name
            if code: section.code = code
            if year: section.year = year
            section.save()
            return {'success': True}
        except Section.DoesNotExist:
            return {'success': False, 'error': 'Section not found.'}

    @staticmethod
    def delete_section(section_id):
        try:
            section = Section.objects.get(id=section_id)
            section.delete()
            return {'success': True}
        except Section.DoesNotExist:
            return {'success': False, 'error': 'Section not found.'}

    @staticmethod
    def get_departments():
        return list(Department.objects.filter(is_active=True).values('id', 'name', 'code'))

    @staticmethod
    def get_courses():
        return [{
            'id': c.id, 'name': c.name, 'code': c.code,
            'department_name': c.department.name,
            'duration_years': c.duration_years
        } for c in Course.objects.select_related('department').all()]
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
    def get_assignment_filters():
        """
        Fetch essential data for room assignment: All sections and rooms.
        """
        sections = Section.objects.select_related('course').all()
        rooms = Venue.objects.select_related('floor__building').all()
        
        return {
            'sections': [
                {'id': s.id, 'name': f"{s.course.name} - {s.code}"} 
                for s in sections
            ],
            'rooms': [
                {'id': r.id, 'name': f"{r.name} ({r.floor.building.code})"} 
                for r in rooms
            ]
        }

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

    @staticmethod
    def get_timetable_filters(semester_id=None):
        """
        Fetch all filters required to build a timetable:
        Sections, Faculty, Rooms, and Periods.
        """
        # 1. Sections
        sections = Section.objects.select_related('course').all()
        
        # 2. Faculty (Users with role code 'FACULTY')
        faculties = User.objects.filter(role__code='FACULTY', is_active=True)
        
        # 3. Rooms (Venues)
        rooms = Venue.objects.select_related('floor__building').filter(is_active=True)
        
        # 4. Periods (Filtered by semester_id if provided)
        periods_query = PeriodDefinition.objects.all()
        if semester_id:
            periods_query = periods_query.filter(semester_id=semester_id)
        
        periods = periods_query.select_related('semester', 'semester__academic_year').order_by('day_of_week', 'period_number')

        return {
            'sections': [
                {'section_id': s.id, 'section_name': f"{s.course.code} {s.year}-{s.name}"} 
                for s in sections
            ],
            'faculties': [
                {'faculty_id': f.id, 'faculty_name': f.get_full_name() or f.username} 
                for f in faculties
            ],
            'rooms': [
                {'room_id': r.id, 'room_name': r.name, 'building': r.floor.building.name} 
                for r in rooms
            ],
            'periods': [
                {
                    'id': p.id,
                    'period_number': p.period_number,
                    'day_name': p.get_day_of_week_display(),
                    'start_time': p.start_time.strftime('%H:%M:%S'),
                    'end_time': p.end_time.strftime('%H:%M:%S')
                } for p in periods
            ]
        }
