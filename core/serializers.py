"""
Serializers for core application REST endpoints.
"""
from rest_framework import serializers

class LoginSerializer(serializers.Serializer):
    """Serializer for user login request.
    
    Accepts email or register number as username, and password.
    """
    username = serializers.CharField(required=True, allow_blank=False)
    password = serializers.CharField(required=True, write_only=True)
