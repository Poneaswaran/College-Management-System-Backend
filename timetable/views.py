from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    TimetableEntrySerializer, SectionCreateTimetableSerializer,
    TimetableDetailSerializer, PeriodDefinitionSerializer
)
from .services import TimetableService
from django.core.exceptions import ValidationError
from core.models import Section


class SectionTimetableListView(APIView):
    """
    Get the full timetable for a specific section.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        section_id = request.query_params.get('section_id')
        semester_id = request.query_params.get('semester_id')
        
        if not section_id or not semester_id:
            return Response({'error': 'section_id and semester_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        entries = TimetableService.get_section_timetable(section_id, semester_id)
        serializer = TimetableDetailSerializer(entries, many=True)
        return Response(serializer.data)

class FacultyScheduleListView(APIView):
    """
    Get the teaching schedule for a faculty member.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        faculty_id = request.query_params.get('faculty_id')
        semester_id = request.query_params.get('semester_id')
        
        if not faculty_id or not semester_id:
            return Response({'error': 'faculty_id and semester_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        entries = TimetableService.get_faculty_timetable(faculty_id, semester_id)
        serializer = TimetableDetailSerializer(entries, many=True)
        return Response(serializer.data)

from timetable.models import PeriodDefinition

class PeriodDefinitionListView(APIView):
    """
    Get all period definitions for a specific semester.
    Useful for populating creation forms.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        semester_id = request.query_params.get('semester_id')
        section_id = request.query_params.get('section_id')

        if not semester_id or not section_id:
            return Response({'error': 'semester_id and section_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not Section.objects.filter(id=section_id).exists():
            return Response({'error': 'Section not found.'}, status=status.HTTP_404_NOT_FOUND)
            
        periods = PeriodDefinition.objects.filter(semester_id=semester_id).order_by('day_of_week', 'period_number')
        serializer = PeriodDefinitionSerializer(periods, many=True)
        return Response(serializer.data)

class TimetableEntryCreateView(APIView):
    """
    API view to create a standard timetable entry.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TimetableEntrySerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Delegate to business logic layer
                entry = TimetableService.create_timetable_entry(
                    section_id=serializer.validated_data.get('section_id'),
                    subject_id=serializer.validated_data.get('subject_id'),
                    faculty_id=serializer.validated_data.get('faculty_id'),
                    period_definition_id=serializer.validated_data.get('period_definition_id'),
                    semester_id=serializer.validated_data.get('semester_id'),
                    room_id=serializer.validated_data.get('room_id'),
                    notes=serializer.validated_data.get('notes', "")
                )
                return Response(TimetableEntrySerializer(entry).data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                # Handle standard Django ValidationError from service or model clean
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SectionCreateTimetableAPIView(APIView):
    """
    API for bulk creation of timetable entries for a specific section.
    Allows specifying a list of slots (subject, faculty, period, room) in one call.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SectionCreateTimetableSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Business logic in service
                section_id = serializer.validated_data.get('section_id')
                semester_id = serializer.validated_data.get('semester_id')
                entries_data = serializer.validated_data.get('entries')
                
                result = TimetableService.bulk_create_timetable_entries(
                    section_id=section_id,
                    semester_id=semester_id,
                    entries_data=entries_data
                )
                
                return Response({
                    "success": True, 
                    "count": len(result), 
                    "message": "Successfully created timetable entries."
                }, status=status.HTTP_201_CREATED)
                
            except ValidationError as e:
                # Handle list of errors from bulk logic
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'error': f"Failed to bulk create entries: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
