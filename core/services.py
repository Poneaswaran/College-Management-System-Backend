from typing import List, Dict, Union
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from core.models import Role, Permission, RolePermission, Department, Course, Section, User
from timetable.models import PeriodDefinition, Subject
from profile_management.models import AcademicYear, Semester

class AcademicStructureService:
    @staticmethod
    def create_department(name, code, school_id, is_active=True):
        if not school_id:
            return {'success': False, 'error': 'school_id is required.'}
        defaults = {'name': name, 'is_active': is_active, 'school_id': school_id}
        dept, created = Department.objects.get_or_create(code=code, defaults=defaults)
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
    def create_academic_year(year_code, start_date, end_date, is_current=False):
        existing = AcademicYear.objects.filter(year_code=year_code).first()
        if existing:
            return {'success': True, 'id': existing.id, 'created': False}

        try:
            academic_year = AcademicYear(
                year_code=year_code,
                start_date=start_date,
                end_date=end_date,
                is_current=is_current,
            )
            academic_year.full_clean()
            academic_year.save()
            return {'success': True, 'id': academic_year.id, 'created': True}
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                return {'success': False, 'error': e.message_dict}
            return {'success': False, 'error': str(e)}

    @staticmethod
    def create_semester(academic_year_id, number, start_date, end_date, is_current=False):
        try:
            academic_year = AcademicYear.objects.get(id=academic_year_id)
        except AcademicYear.DoesNotExist:
            return {'success': False, 'error': 'Academic year not found.'}

        if number not in [1, 2]:
            return {'success': False, 'error': 'number must be 1 (Odd Semester) or 2 (Even Semester).'}

        existing = Semester.objects.filter(academic_year=academic_year, number=number).first()
        if existing:
            return {'success': True, 'id': existing.id, 'created': False}

        try:
            semester = Semester(
                academic_year=academic_year,
                number=number,
                start_date=start_date,
                end_date=end_date,
                is_current=is_current,
            )
            semester.full_clean()
            semester.save()
            return {'success': True, 'id': semester.id, 'created': True}
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                return {'success': False, 'error': e.message_dict}
            return {'success': False, 'error': str(e)}

    @staticmethod
    def update_department(dept_id, name=None, code=None, school_id=None, is_active=None):
        try:
            dept = Department.objects.get(id=dept_id)
            if name: dept.name = name
            if code: dept.code = code
            if school_id is not None: dept.school_id = school_id
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
    def get_departments(school_id=None):
        qs = Department.objects.select_related('school').filter(is_active=True)
        if school_id:
            qs = qs.filter(school_id=school_id)
        return [
            {
                'id': d.id, 
                'name': d.name, 
                'code': d.code,
                'school': {'id': d.school.id, 'name': d.school.name, 'code': d.school.code} if d.school else None
            } 
            for d in qs
        ]

    @staticmethod
    def get_schools():
        return [
            {
                'id': s.id,
                'name': s.name,
                'code': s.code,
                'is_active': s.is_active
            }
            for s in School.objects.filter(is_active=True)
        ]

    @staticmethod
    def get_courses():
        return [{
            'id': c.id, 'name': c.name, 'code': c.code,
            'department_name': c.department.name,
            'school_name': c.department.get_school_name(),
            'duration_years': c.duration_years
        } for c in Course.objects.select_related('department', 'department__school').all()]

    @staticmethod
    def get_academic_years(page=1, page_size=20, is_current=None):
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        qs = AcademicYear.objects.all().order_by('-start_date')
        if is_current is not None:
            qs = qs.filter(is_current=is_current)

        total_items = qs.count()
        start = (page - 1) * page_size
        end = start + page_size

        years = qs[start:end]
        data = [
            {
                'id': y.id,
                'year_code': y.year_code,
                'start_date': y.start_date.isoformat(),
                'end_date': y.end_date.isoformat(),
                'is_current': y.is_current,
            }
            for y in years
        ]

        return {
            'academic_years': data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total_items,
                'total_pages': (total_items + page_size - 1) // page_size,
            },
        }

    @staticmethod
    def get_semesters(academic_year_id=None, is_current=None):
        qs = Semester.objects.select_related('academic_year').all().order_by('-academic_year__start_date', 'number')
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        if is_current is not None:
            qs = qs.filter(is_current=is_current)

        return [
            {
                'id': s.id,
                'academic_year_id': s.academic_year_id,
                'academic_year_code': s.academic_year.year_code,
                'number': s.number,
                'number_display': s.get_number_display(),
                'start_date': s.start_date.isoformat(),
                'end_date': s.end_date.isoformat(),
                'is_current': s.is_current,
            }
            for s in qs
        ]
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
    def get_timetable_filters(
        semester_id=None,
        section_id=None,
        faculty_id=None,
        room_id=None,
        period_definition_id=None,
        subject_id=None,
    ):
        """
        Fetch all filters required to build a timetable:
        Subjects, Sections, Faculty, Rooms, and Periods.
        """
        # 1. Subjects
        subjects = Subject.objects.select_related('department').filter(is_active=True)
        if subject_id:
            subjects = subjects.filter(id=subject_id)

        # 1. Sections
        sections = Section.objects.select_related('course').all()
        if section_id:
            sections = sections.filter(id=section_id)
        
        # 2. Faculty (Users with role code 'FACULTY')
        faculties = User.objects.filter(role__code='FACULTY', is_active=True)
        if faculty_id:
            faculties = faculties.filter(id=faculty_id)
        
        # 3. Rooms (Venues)
        rooms = Venue.objects.select_related('floor__building').filter(is_active=True)
        if room_id:
            rooms = rooms.filter(id=room_id)
        
        # 4. Periods (Filtered by semester_id if provided)
        periods_query = PeriodDefinition.objects.all()
        if semester_id:
            periods_query = periods_query.filter(semester_id=semester_id)
        if period_definition_id:
            periods_query = periods_query.filter(id=period_definition_id)
        
        periods = periods_query.select_related('semester', 'semester__academic_year').order_by('day_of_week', 'period_number')

        return {
            'subjects': [
                {
                    'subject_id': s.id,
                    'subject_name': s.name,
                    'subject_code': s.code,
                    'department_code': s.department.code,
                    'semester_number': s.semester_number,
                }
                for s in subjects.order_by('code')
            ],
            'sections': [
                {'section_id': s.id, 'section_name': f"{s.course.code} {s.year}-{s.name}"} 
                for s in sections
            ],
            'faculties': [
                {
                    'faculty_id': f.id,
                    'faculty_name': f.get_full_name() or f.email or f.register_number or 'Faculty'
                }
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
