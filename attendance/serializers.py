from rest_framework import serializers
from .models import FacultyAttendance, AttendanceSession, StudentAttendance, AttendanceReport

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

class StudentAttendanceReportSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    semester_info = serializers.SerializerMethodField()
    percentage_display = serializers.SerializerMethodField()
    classes_needed_for_75 = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceReport
        fields = [
            'id', 'total_classes', 'present_count', 'absent_count', 'late_count',
            'attendance_percentage', 'is_below_threshold', 'last_calculated',
            'subject_code', 'subject_name', 'semester_info', 'percentage_display',
            'classes_needed_for_75'
        ]

    def get_semester_info(self, obj):
        return f"{obj.semester.academic_year.year_code} - Semester {obj.semester.number}"

    def get_percentage_display(self, obj):
        return f"{float(obj.attendance_percentage):.2f}%"

    def get_classes_needed_for_75(self, obj):
        if float(obj.attendance_percentage) >= 75.0:
            return 0
        target = 0.75
        present = obj.present_count + obj.late_count
        total = obj.total_classes
        if total == 0:
            return 0
        needed = ((target * total) - present) / (1 - target)
        return max(0, int(needed) + 1)

class ActiveAttendanceSessionSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(read_only=True)
    sections_name = serializers.CharField(read_only=True)
    faculty_name = serializers.CharField(read_only=True)
    period_info = serializers.CharField(read_only=True)
    time_remaining = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'date', 'status', 'attendance_window_minutes',
            'subject_name', 'sections_name', 'faculty_name', 'period_info',
            'time_remaining', 'is_active', 'can_mark_attendance'
        ]

class StudentAttendanceHistorySerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(read_only=True)
    date = serializers.DateField(source='session.date', read_only=True)
    period_info = serializers.CharField(source='session.period_info', read_only=True)
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentAttendance
        fields = [
            'id', 'status', 'marked_at', 'latitude', 'longitude',
            'device_info', 'is_manually_marked', 'notes',
            'subject_name', 'date', 'period_info', 'image_url'
        ]
        
    def get_image_url(self, obj):
        if obj.attendance_image:
            return obj.attendance_image.url
        return None

class StudentMarkAttendanceSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    image_data = serializers.ImageField()  # Multipart uploaded image file
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    device_info = serializers.JSONField(required=False, default=dict)

    def validate_device_info(self, value):
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("device_info must be a valid JSON string.")
        return value


