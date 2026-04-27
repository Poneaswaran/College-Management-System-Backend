from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
from core.services import RolePermissionService, CoreFilterService, AcademicStructureService

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

from core.services import CoreFilterService, AcademicStructureService
from core.utils import generate_etag, check_etag

class FilterOptionsAPIView(APIView):
    """
    General filters endpoint.
    Ex: /api/core/filters/?type=room
    Ex: /api/core/filters/?building_name=CampusA
    """
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _parse_optional_int_param(request, key):
        value = request.query_params.get(key)
        if value in (None, ''):
            return None, None
        try:
            return int(value), None
        except (TypeError, ValueError):
            return None, f'{key} must be an integer.'

    def get(self, request):
        filter_type = request.query_params.get('type')
        building_name = request.query_params.get('building_name')

        if filter_type == 'room' or building_name:
            data = CoreFilterService.get_room_filters(building_name)
        elif filter_type == 'assign_room':
            data = CoreFilterService.get_assignment_filters()
        elif filter_type == 'timetable':
            param_keys = [
                'semester_id',
                'subject_id',
                'section_id',
                'faculty_id',
                'room_id',
                'period_definition_id',
            ]

            parsed_params = {}
            for key in param_keys:
                parsed_value, error = self._parse_optional_int_param(request, key)
                if error:
                    return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
                parsed_params[key] = parsed_value

            data = CoreFilterService.get_timetable_filters(**parsed_params)
        else:
            return Response({'error': 'Invalid filter type'}, status=status.HTTP_400_BAD_REQUEST)
            
        # ETag implementation
        etag = generate_etag(data)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
                
        response = Response({'filters': data})
        response['ETag'] = f'"{etag}"'
        return response


class AcademicFiltersAPIView(APIView):
    """
    Unified academic-structure filter endpoint.

    GET /api/core/academic-filters/

    Query params:
      school_id    (int) — limit departments/courses/sections to this school
      department_id (int) — limit courses/sections to this department
      course_id    (int) — limit sections to this course
      include      (str) — comma-separated list of resources to include.
                           Allowed values: schools, departments, courses, sections
                           Default: schools,departments (if no school_id)
                                    departments,courses,sections (if school_id given)

    Response shape:
    {
        "schools":     [ {id, name, code, department_count}, ... ],
        "departments": [ {id, name, code, school_id, school_name, course_count}, ... ],
        "courses":     [ {id, name, code, department_id, department_name, duration_years}, ... ],
        "sections":    [ {id, name, code, year, course_id, course_name, department_id, department_name}, ... ]
    }

    Only the requested resources are returned in the response. Any resource not in
    `include` is omitted, keeping payloads small.
    """
    permission_classes = [IsAuthenticated]

    # ---------- helpers ----------

    @staticmethod
    def _parse_int(request, key):
        val = request.query_params.get(key)
        if val in (None, ''):
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    # ---------- data fetchers ----------

    @staticmethod
    def _schools(department_count_map):
        from core.models import School
        qs = School.objects.filter(is_active=True).order_by('name')
        return [
            {
                'id': s.id,
                'name': s.name,
                'code': s.code,
                'department_count': department_count_map.get(s.id, 0),
            }
            for s in qs
        ]

    @staticmethod
    def _departments(school_id=None):
        from core.models import Department
        qs = Department.objects.select_related('school').filter(is_active=True).order_by('name')
        if school_id:
            qs = qs.filter(school_id=school_id)
        return [
            {
                'id': d.id,
                'name': d.name,
                'code': d.code,
                'school_id': d.school_id,
                'school_name': d.school.name if d.school else None,
            }
            for d in qs
        ]

    @staticmethod
    def _courses(school_id=None, department_id=None):
        from core.models import Course
        qs = Course.objects.select_related('department', 'department__school').order_by('name')
        if department_id:
            qs = qs.filter(department_id=department_id)
        elif school_id:
            qs = qs.filter(department__school_id=school_id)
        return [
            {
                'id': c.id,
                'name': c.name,
                'code': c.code,
                'duration_years': c.duration_years,
                'department_id': c.department_id,
                'department_name': c.department.name,
            }
            for c in qs
        ]

    @staticmethod
    def _sections(school_id=None, department_id=None, course_id=None):
        from core.models import Section
        qs = Section.objects.select_related(
            'course', 'course__department', 'course__department__school'
        ).order_by('course__department__name', 'year', 'name')
        if course_id:
            qs = qs.filter(course_id=course_id)
        elif department_id:
            qs = qs.filter(course__department_id=department_id)
        elif school_id:
            qs = qs.filter(course__department__school_id=school_id)
        return [
            {
                'id': s.id,
                'name': s.name,
                'code': s.code,
                'year': s.year,
                'course_id': s.course_id,
                'course_name': s.course.name,
                'department_id': s.course.department_id,
                'department_name': s.course.department.name,
            }
            for s in qs
        ]

    # ---------- main handler ----------

    def get(self, request):
        school_id     = self._parse_int(request, 'school_id')
        department_id = self._parse_int(request, 'department_id')
        course_id     = self._parse_int(request, 'course_id')

        # Determine which resources to include
        include_param = request.query_params.get('include', '')
        if include_param:
            include = {r.strip() for r in include_param.split(',') if r.strip()}
        else:
            # Sensible defaults based on which filter is active
            if course_id:
                include = {'sections'}
            elif department_id:
                include = {'courses', 'sections'}
            elif school_id:
                include = {'departments', 'courses', 'sections'}
            else:
                include = {'schools', 'departments'}

        allowed = {'schools', 'departments', 'courses', 'sections'}
        invalid = include - allowed
        if invalid:
            return Response(
                {'error': f"Invalid include values: {', '.join(invalid)}. Allowed: {', '.join(allowed)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = {}

        if 'schools' in include:
            # Pre-compute dept counts per school in one query
            from core.models import Department
            from django.db.models import Count
            dept_counts = {
                row['school_id']: row['count']
                for row in Department.objects.filter(is_active=True)
                                             .values('school_id')
                                             .annotate(count=Count('id'))
            }
            result['schools'] = self._schools(dept_counts)

        if 'departments' in include:
            result['departments'] = self._departments(school_id=school_id)

        if 'courses' in include:
            result['courses'] = self._courses(school_id=school_id, department_id=department_id)

        if 'sections' in include:
            result['sections'] = self._sections(
                school_id=school_id,
                department_id=department_id,
                course_id=course_id,
            )

        etag = generate_etag(result)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)

        response = Response(result)
        response['ETag'] = f'"{etag}"'
        return response

from core.models import User, Section, School


class SchoolListView(APIView):
    """
    API to list all active schools.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = AcademicStructureService.get_schools()
        etag = generate_etag(data)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        response = Response({'schools': data})
        response['ETag'] = f'"{etag}"'
        return response


class SectionListView(APIView):
    """
    API to list all academic sections.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sections = Section.objects.select_related('course', 'course__department').all()
        data = [{
            'id': s.id,
            'name': s.name,
            'code': s.code,
            'year': s.year,
            'course_id': s.course.id,
            'course_name': s.course.name,
            'department_code': s.course.department.code,
            'school_name': s.course.department.get_school_name()
        } for s in sections]
        
        # ETag implementation
        etag = generate_etag(data)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
            
        response = Response({'sections': data})
        response['ETag'] = f'"{etag}"'
        return response

class DepartmentListView(APIView):
    """
    API to list all active departments.
    Optional query param: school_id
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school_id = request.query_params.get('school_id')
        if school_id:
            try:
                school_id = int(school_id)
            except (TypeError, ValueError):
                return Response({'error': 'school_id must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        data = AcademicStructureService.get_departments(school_id=school_id)
        etag = generate_etag(data)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        response = Response({'departments': data})
        response['ETag'] = f'"{etag}"'
        return response

class CourseListView(APIView):
    """
    API to list all courses with department details.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = AcademicStructureService.get_courses()
        etag = generate_etag(data)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        response = Response({'courses': data})
        response['ETag'] = f'"{etag}"'
        return response


class AcademicYearListView(APIView):
    """
    API to list academic years with pagination.
    Optional query params: page, page_size, is_current
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = request.query_params.get('page', '1')
        page_size = request.query_params.get('page_size', '20')
        is_current = request.query_params.get('is_current')

        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError):
            return Response({'error': 'page and page_size must be integers.'}, status=status.HTTP_400_BAD_REQUEST)

        if page < 1 or page_size < 1:
            return Response({'error': 'page and page_size must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)

        if is_current is not None:
            is_current_text = str(is_current).strip().lower()
            if is_current_text in ('true', '1', 'yes', 'y'):
                is_current = True
            elif is_current_text in ('false', '0', 'no', 'n'):
                is_current = False
            else:
                return Response({'error': 'is_current must be a boolean value.'}, status=status.HTTP_400_BAD_REQUEST)

        data = AcademicStructureService.get_academic_years(
            page=page,
            page_size=page_size,
            is_current=is_current,
        )
        etag = generate_etag(data)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        response = Response(data)
        response['ETag'] = f'"{etag}"'
        return response


class SemesterListView(APIView):
    """
    API to list semesters.
    Optional query params: academic_year_id, is_current
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        academic_year_id = request.query_params.get('academic_year_id')
        is_current = request.query_params.get('is_current')

        if academic_year_id:
            try:
                academic_year_id = int(academic_year_id)
            except (TypeError, ValueError):
                return Response({'error': 'academic_year_id must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        if is_current is not None:
            is_current_text = str(is_current).strip().lower()
            if is_current_text in ('true', '1', 'yes', 'y'):
                is_current = True
            elif is_current_text in ('false', '0', 'no', 'n'):
                is_current = False
            else:
                return Response({'error': 'is_current must be a boolean value.'}, status=status.HTTP_400_BAD_REQUEST)

        data = AcademicStructureService.get_semesters(
            academic_year_id=academic_year_id,
            is_current=is_current,
        )
        etag = generate_etag(data)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        response = Response({'semesters': data})
        response['ETag'] = f'"{etag}"'
        return response

from core.models import Department, Course

class AdminDepartmentCreateView(APIView):
    """
    API for admin to create a new department.
    Sample payload: {"name": "Physics", "code": "PHY", "school_id": 1}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get('name')
        code = request.data.get('code')
        school_id = request.data.get('school_id')
        if not name or not code:
            return Response({'error': 'name and code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        result = AcademicStructureService.create_department(name, code, school_id)
        if not result['success']:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(result, status=status.HTTP_201_CREATED if result.get('created') else status.HTTP_200_OK)

class AdminCourseCreateView(APIView):
    """
    API for admin to create a new course.
    Sample payload: {"department_id": 1, "name": "B.Sc Physics", "code": "BSC_PHY", "duration_years": 3}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        dept_id = request.data.get('department_id')
        name = request.data.get('name')
        code = request.data.get('code')
        duration = request.data.get('duration_years', 4)

        if not dept_id or not name or not code:
            return Response({'error': 'department_id, name and code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        result = AcademicStructureService.create_course(dept_id, name, code, duration)
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED if result['created'] else status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

class AdminSectionCreateView(APIView):
    """
    API for admin to create a new section.
    Sample payload: {"course_id": 1, "name": "B.Sc Physics A", "code": "A", "year": 1}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        course_id = request.data.get('course_id')
        name = request.data.get('name')
        code = request.data.get('code') # e.g. A, B
        year = request.data.get('year', 1)

        if not course_id or not name or not code:
            return Response({'error': 'course_id, name and code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        result = AcademicStructureService.create_section(course_id, name, code, year)
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED if result['created'] else status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class AdminAcademicYearCreateView(APIView):
    """
    API for admin to create a new academic year.
    Sample payload: {"year_code": "2026-27", "start_date": "2026-07-01", "end_date": "2027-06-30", "is_current": true}
    """
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _parse_date(date_value, key):
        try:
            return datetime.strptime(date_value, '%Y-%m-%d').date(), None
        except (TypeError, ValueError):
            return None, f'{key} must be in YYYY-MM-DD format.'

    @staticmethod
    def _parse_bool(value, key):
        if isinstance(value, bool):
            return value, None
        if isinstance(value, (int, float)):
            return bool(value), None
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ('true', '1', 'yes', 'y'):
                return True, None
            if lowered in ('false', '0', 'no', 'n'):
                return False, None
        return None, f'{key} must be a boolean value.'

    def post(self, request):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        year_code = request.data.get('year_code')
        start_date_raw = request.data.get('start_date')
        end_date_raw = request.data.get('end_date')
        is_current_raw = request.data.get('is_current', False)

        if not year_code or not start_date_raw or not end_date_raw:
            return Response(
                {'error': 'year_code, start_date, and end_date are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_date, start_error = self._parse_date(start_date_raw, 'start_date')
        if start_error:
            return Response({'error': start_error}, status=status.HTTP_400_BAD_REQUEST)

        end_date, end_error = self._parse_date(end_date_raw, 'end_date')
        if end_error:
            return Response({'error': end_error}, status=status.HTTP_400_BAD_REQUEST)

        is_current, is_current_error = self._parse_bool(is_current_raw, 'is_current')
        if is_current_error:
            return Response({'error': is_current_error}, status=status.HTTP_400_BAD_REQUEST)

        result = AcademicStructureService.create_academic_year(
            year_code=year_code,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
        )

        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED if result['created'] else status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class AdminSemesterCreateView(APIView):
    """
    API for admin to create a new semester.
    Sample payload: {"academic_year_id": 1, "number": 1, "start_date": "2026-07-01", "end_date": "2026-12-15", "is_current": true}
    """
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _parse_date(date_value, key):
        try:
            return datetime.strptime(date_value, '%Y-%m-%d').date(), None
        except (TypeError, ValueError):
            return None, f'{key} must be in YYYY-MM-DD format.'

    @staticmethod
    def _parse_bool(value, key):
        if isinstance(value, bool):
            return value, None
        if isinstance(value, (int, float)):
            return bool(value), None
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ('true', '1', 'yes', 'y'):
                return True, None
            if lowered in ('false', '0', 'no', 'n'):
                return False, None
        return None, f'{key} must be a boolean value.'

    def post(self, request):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        academic_year_id = request.data.get('academic_year_id')
        number = request.data.get('number')
        start_date_raw = request.data.get('start_date')
        end_date_raw = request.data.get('end_date')
        is_current_raw = request.data.get('is_current', False)

        if not academic_year_id or number is None or not start_date_raw or not end_date_raw:
            return Response(
                {'error': 'academic_year_id, number, start_date, and end_date are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            academic_year_id = int(academic_year_id)
            number = int(number)
        except (TypeError, ValueError):
            return Response({'error': 'academic_year_id and number must be integers.'}, status=status.HTTP_400_BAD_REQUEST)

        start_date, start_error = self._parse_date(start_date_raw, 'start_date')
        if start_error:
            return Response({'error': start_error}, status=status.HTTP_400_BAD_REQUEST)

        end_date, end_error = self._parse_date(end_date_raw, 'end_date')
        if end_error:
            return Response({'error': end_error}, status=status.HTTP_400_BAD_REQUEST)

        is_current, is_current_error = self._parse_bool(is_current_raw, 'is_current')
        if is_current_error:
            return Response({'error': is_current_error}, status=status.HTTP_400_BAD_REQUEST)

        result = AcademicStructureService.create_semester(
            academic_year_id=academic_year_id,
            number=number,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
        )

        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED if result['created'] else status.HTTP_200_OK)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

class AdminDepartmentDetailView(APIView):
    """
    API for admin to update or delete a department.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get('name')
        code = request.data.get('code')
        school_id = request.data.get('school_id')
        is_active = request.data.get('is_active')
        result = AcademicStructureService.update_department(pk, name, code, school_id, is_active)
        return Response(result if result['success'] else result, status=status.HTTP_200_OK if result['success'] else status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        result = AcademicStructureService.delete_department(pk)
        return Response(result if result['success'] else result, status=status.HTTP_200_OK if result['success'] else status.HTTP_404_NOT_FOUND)

class AdminCourseDetailView(APIView):
    """
    API for admin to update or delete a course.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get('name')
        code = request.data.get('code')
        duration = request.data.get('duration_years')
        result = AcademicStructureService.update_course(pk, name, code, duration)
        return Response(result if result['success'] else result, status=status.HTTP_200_OK if result['success'] else status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        result = AcademicStructureService.delete_course(pk)
        return Response(result if result['success'] else result, status=status.HTTP_200_OK if result['success'] else status.HTTP_404_NOT_FOUND)

class AdminSectionDetailView(APIView):
    """
    API for admin to update or delete a section.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get('name')
        code = request.data.get('code')
        year = request.data.get('year')
        result = AcademicStructureService.update_section(pk, name, code, year)
        return Response(result if result['success'] else result, status=status.HTTP_200_OK if result['success'] else status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        result = AcademicStructureService.delete_section(pk)
        return Response(result if result['success'] else result, status=status.HTTP_200_OK if result['success'] else status.HTTP_404_NOT_FOUND)
