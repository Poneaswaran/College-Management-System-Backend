from rest_framework import serializers
from .models import FacultyAttendance

class FacultyPunchSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacultyAttendance
        fields = [
            'id', 'faculty', 'date', 
            'punch_in_time', 'punch_in_photo', 'punch_in_latitude', 'punch_in_longitude',
            'punch_out_time', 'punch_out_photo', 'punch_out_latitude', 'punch_out_longitude',
            'is_late', 'notes'
        ]
        read_only_fields = ['faculty', 'date', 'punch_in_time', 'punch_out_time']

class FacultyAttendanceReportSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.get_full_name', read_only=True)
    department = serializers.CharField(source='faculty.department.name', read_only=True)
    
    class Meta:
        model = FacultyAttendance
        fields = [
            'id', 'faculty', 'faculty_name', 'department', 'date',
            'punch_in_time', 'punch_in_photo', 'punch_in_latitude', 'punch_in_longitude',
            'punch_out_time', 'punch_out_photo', 'punch_out_latitude', 'punch_out_longitude',
            'is_late', 'notes'
        ]
