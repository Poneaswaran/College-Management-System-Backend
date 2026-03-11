from rest_framework import serializers
from .models import StudyMaterial

class StudyMaterialUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyMaterial
        fields = [
            'id', 'subject', 'section', 'title', 'description', 
            'material_type', 'file', 'status', 'view_count', 'download_count'
        ]
        read_only_fields = ['id', 'view_count', 'download_count']

    def validate(self, data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user
            if not user.is_authenticated or user.role.code not in ['FACULTY', 'HOD', 'ADMIN']:
                raise serializers.ValidationError("Only faculty can upload study materials.")
                
        # Validate file size (max 50MB)
        file_obj = data.get('file')
        if file_obj and file_obj.size > 50 * 1024 * 1024:
            raise serializers.ValidationError({"file": "File size cannot exceed 50MB"})
            
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['faculty'] = request.user
        return super().create(validated_data)
