from rest_framework import serializers
from django.conf import settings

from .models import StudyMaterial
from .validators import StudyMaterialValidator


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


class AIChatRequestSerializer(serializers.Serializer):
    """Validate incoming payload for AI tutor chat endpoint."""

    material_id = serializers.IntegerField(min_value=1)
    message = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=getattr(settings, "AI_CHAT_MAX_MESSAGE_LENGTH", 1000),
    )


class StudyMaterialMutationResponseSerializer(serializers.ModelSerializer):
    """Compact material response payload for mutation-style REST endpoints."""

    class Meta:
        model = StudyMaterial
        fields = [
            'id',
            'title',
            'description',
            'material_type',
            'status',
            'subject',
            'section',
            'faculty',
            'file',
            'file_size',
            'view_count',
            'download_count',
            'uploaded_at',
            'updated_at',
        ]


class StudyMaterialUpdateSerializer(serializers.ModelSerializer):
    """Validate and update study material fields for REST mutation parity."""

    class Meta:
        model = StudyMaterial
        fields = [
            'title',
            'description',
            'material_type',
            'status',
            'file',
        ]
        extra_kwargs = {
            'title': {'required': False},
            'description': {'required': False},
            'material_type': {'required': False},
            'status': {'required': False},
            'file': {'required': False},
        }

    def validate_file(self, value):
        """Validate updated file extension and size."""
        is_valid_ext, ext_error = StudyMaterialValidator.validate_file_extension(value.name)
        if not is_valid_ext:
            raise serializers.ValidationError(ext_error)

        is_valid_size, size_error = StudyMaterialValidator.validate_file_size(value.size)
        if not is_valid_size:
            raise serializers.ValidationError(size_error)

        return value

    def update(self, instance, validated_data):
        """Replace file safely when a new file is provided."""
        new_file = validated_data.get('file')
        if new_file and instance.file:
            instance.file.delete(save=False)

        return super().update(instance, validated_data)
