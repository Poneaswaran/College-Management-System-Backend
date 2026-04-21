from rest_framework import serializers

from core.models import Section

from .models import Period, TimetableSlot


class HODClassSerializer(serializers.ModelSerializer):
    section = serializers.CharField(source="code", read_only=True)
    semester = serializers.IntegerField(source="year", read_only=True)

    class Meta:
        model = Section
        fields = ["id", "name", "section", "semester"]


class HODPeriodSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(format="%H:%M")
    end_time = serializers.TimeField(format="%H:%M")

    class Meta:
        model = Period
        fields = ["id", "label", "start_time", "end_time", "order", "is_break"]


class HODTimetableSlotSerializer(serializers.ModelSerializer):
    slot_id = serializers.IntegerField(source="id", read_only=True)
    period_id = serializers.IntegerField(source="period_id", read_only=True)
    subject_id = serializers.IntegerField(source="subject_id", read_only=True, allow_null=True)
    subject_name = serializers.SerializerMethodField()
    faculty_id = serializers.IntegerField(source="faculty_id", read_only=True, allow_null=True)
    faculty_name = serializers.SerializerMethodField()
    is_assigned = serializers.SerializerMethodField()

    class Meta:
        model = TimetableSlot
        fields = [
            "slot_id",
            "day",
            "period_id",
            "subject_id",
            "subject_name",
            "faculty_id",
            "faculty_name",
            "is_assigned",
        ]

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None

    def get_faculty_name(self, obj):
        return obj.faculty.full_name if obj.faculty else None

    def get_is_assigned(self, obj):
        return bool(obj.subject_id and obj.faculty_id)


class HODSubjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class HODFacultySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class HODAssignSlotRequestSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField(min_value=1)
    faculty_id = serializers.IntegerField(min_value=1)
    subject_id = serializers.IntegerField(min_value=1)
