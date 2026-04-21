from rest_framework import serializers

from core.models import Section

from .models import Period, TimetableSlot
from profile_management.models import SectionIncharge


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
    period_id = serializers.IntegerField(read_only=True)
    subject_id = serializers.IntegerField(read_only=True, allow_null=True)
    subject_name = serializers.SerializerMethodField()
    faculty_id = serializers.IntegerField(read_only=True, allow_null=True)
    faculty_name = serializers.SerializerMethodField()
    faculty_profile_photo = serializers.SerializerMethodField()
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
            "faculty_profile_photo",
            "is_assigned",
        ]

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None

    def get_faculty_name(self, obj):
        return obj.faculty.user.get_full_name() if obj.faculty else None

    def get_faculty_profile_photo(self, obj):
        if obj.faculty and obj.faculty.profile_photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.faculty.profile_photo.url)
            return obj.faculty.profile_photo.url
        return None

    def get_is_assigned(self, obj):
        return bool(obj.subject_id and obj.faculty_id)


class HODSubjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class HODFacultySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="user_id")
    name = serializers.CharField(source="full_name")
    profile_photo = serializers.SerializerMethodField()

    def get_profile_photo(self, obj):
        # The 'obj' in HODFacultyBySubjectView is a dict (see hod_views.py)
        # We need to handle both models and dicts
        profile_photo_url = None
        if isinstance(obj, dict):
            # In HODFacultyBySubjectView, we pass list of dicts directly
            # This is a bit messy, let's fix the view to pass profiles instead
            profile_photo_url = obj.get('profile_photo')
        else:
            if hasattr(obj, 'profile_photo') and obj.profile_photo:
                profile_photo_url = obj.profile_photo.url
        
        if profile_photo_url:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(profile_photo_url)
            return profile_photo_url
        return None


class HODAssignSlotRequestSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField(min_value=1)
    faculty_id = serializers.IntegerField(min_value=1)
    subject_id = serializers.IntegerField(min_value=1)


class HODSectionInchargeSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source="faculty.get_full_name", read_only=True)
    faculty_email = serializers.EmailField(source="faculty.email", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = SectionIncharge
        fields = ["id", "section", "section_name", "faculty", "faculty_name", "faculty_email"]


class HODAssignInchargeSerializer(serializers.Serializer):
    section_id = serializers.IntegerField()
    faculty_id = serializers.IntegerField()
