from rest_framework import serializers
from timetable.models import TimetableEntry, Subject, PeriodDefinition, Room
from core.models import Section, User
from profile_management.models import Semester

class TimetableEntrySerializer(serializers.ModelSerializer):
    """
    Standard serializer for timetable entries.
    """
    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'section_id', 'subject_id', 'faculty_id', 'period_definition_id', 
            'room_id', 'semester_id', 'notes', 'is_active', 'allocation_id'
        ]
        read_only_fields = ['id', 'allocation_id']

class TimetableDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer including relation data for displaying a timetable.
    """
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    faculty_name = serializers.CharField(source='faculty.get_full_name', read_only=True)
    period_number = serializers.IntegerField(source='period_definition.period_number', read_only=True)
    day_name = serializers.CharField(source='period_definition.get_day_of_week_display', read_only=True)
    start_time = serializers.TimeField(source='period_definition.start_time', read_only=True)
    end_time = serializers.TimeField(source='period_definition.end_time', read_only=True)
    room_name = serializers.CharField(source='room.room_number', read_only=True, allow_null=True)
    
    class Meta:
        model = TimetableEntry
        fields = [
            'id', 'subject_name', 'subject_code', 'faculty_name', 
            'period_number', 'day_name', 'start_time', 'end_time', 'room_name', 'notes'
        ]

class PeriodDefinitionSerializer(serializers.ModelSerializer):
    """
    Serializer for period slots.
    """
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    class Meta:
        model = PeriodDefinition
        fields = ['id', 'period_number', 'day_name', 'start_time', 'end_time']

class BulkTimetableEntryInputSerializer(serializers.Serializer):
    """
    Input serializer for individual items in a bulk request.
    """
    subject_id = serializers.IntegerField(required=True)
    faculty_id = serializers.IntegerField(required=True)
    period_definition_id = serializers.IntegerField(required=True)
    room_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

class SectionCreateTimetableSerializer(serializers.Serializer):
    """
    Serializer to handle creating multiple timetable entries for a specific section.
    """
    section_id = serializers.IntegerField(required=True)
    semester_id = serializers.IntegerField(required=True)
    entries = BulkTimetableEntryInputSerializer(many=True, required=True)
