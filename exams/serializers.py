from rest_framework import serializers
from .models import ExamResult, ExamSchedule
from profile_management.models import StudentProfile
from timetable.models import Subject

class MarkAttendanceItemSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    is_present = serializers.BooleanField()

class InvigilationAttendanceSerializer(serializers.Serializer):
    schedule_id = serializers.IntegerField()
    attendance_data = MarkAttendanceItemSerializer(many=True)

class ArrearStudentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = ['id', 'full_name', 'register_number', 'semester']
        
class ArrearSubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code']

class ArrearResultSerializer(serializers.ModelSerializer):
    student = ArrearStudentSerializer()
    subject = serializers.SerializerMethodField()
    exam_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamResult
        fields = ['id', 'student', 'subject', 'exam_name', 'marks_obtained', 'percentage', 'grade_letter', 'status']

    def get_subject(self, obj):
        return ArrearSubjectSerializer(obj.schedule.subject).data
        
    def get_exam_name(self, obj):
        return obj.schedule.exam.name
