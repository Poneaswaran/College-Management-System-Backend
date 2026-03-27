from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
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

    def get(self, request):
        filter_type = request.query_params.get('type')
        building_name = request.query_params.get('building_name')

        if filter_type == 'room' or building_name:
            data = CoreFilterService.get_room_filters(building_name)
        elif filter_type == 'assign_room':
            data = CoreFilterService.get_assignment_filters()
        elif filter_type == 'timetable':
            semester_id = request.query_params.get('semester_id')
            data = CoreFilterService.get_timetable_filters(semester_id)
        else:
            return Response({'error': 'Invalid filter type'}, status=status.HTTP_400_BAD_REQUEST)
            
        # ETag implementation
        etag = generate_etag(data)
        if check_etag(request, etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED)
                
        response = Response({'filters': data})
        response['ETag'] = f'"{etag}"'
        return response

from core.models import User, Section

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
            'department_code': s.course.department.code
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
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = AcademicStructureService.get_departments()
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

from core.models import Department, Course

class AdminDepartmentCreateView(APIView):
    """
    API for admin to create a new department.
    Sample payload: {"name": "Physics", "code": "PHY"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role.code != 'ADMIN':
            return Response({'error': 'Unauthorized. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)

        name = request.data.get('name')
        code = request.data.get('code')
        if not name or not code:
            return Response({'error': 'name and code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        result = AcademicStructureService.create_department(name, code)
        return Response(result, status=status.HTTP_201_CREATED if result['created'] else status.HTTP_200_OK)

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
        is_active = request.data.get('is_active')
        result = AcademicStructureService.update_department(pk, name, code, is_active)
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
