from rest_framework import serializers
from .models import DepartmentNotice
from django.contrib.auth import get_user_model

User = get_user_model()

class DepartmentNoticeSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = DepartmentNotice
        fields = [
            'id', 'title', 'message', 'department', 'department_name',
            'created_by', 'created_by_name', 'target_audience',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'department', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
            # Assuming HOD has a department associated
            validated_data['department'] = request.user.department
        return super().create(validated_data)
