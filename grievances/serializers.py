from rest_framework import serializers
from .models import Grievance
from profile_management.models import StudentProfile

class StudentMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    class Meta:
        model = StudentProfile
        fields = ['id', 'register_number', 'full_name', 'profile_photo']

class GrievanceSerializer(serializers.ModelSerializer):
    student_details = StudentMinimalSerializer(source='student', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)

    class Meta:
        model = Grievance
        fields = [
            'id', 'student', 'student_details', 'department', 'subject', 
            'description', 'category', 'category_display', 'priority', 
            'priority_display', 'status', 'status_display', 'created_at', 
            'updated_at', 'resolved_by', 'resolved_by_name', 
            'resolution_note', 'resolved_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'resolved_at', 'resolved_by']
