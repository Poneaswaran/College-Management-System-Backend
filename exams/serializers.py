from rest_framework import serializers

class MarkAttendanceItemSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    is_present = serializers.BooleanField()

class InvigilationAttendanceSerializer(serializers.Serializer):
    schedule_id = serializers.IntegerField()
    attendance_data = MarkAttendanceItemSerializer(many=True)
