"""Custom exceptions for AI integration flows in study materials."""

from rest_framework import status
from rest_framework.exceptions import APIException


class AIServiceUnavailableError(APIException):
    """Raised when the external AI service is temporarily unavailable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "AI tutor is currently unavailable. Please try again later."
    default_code = "ai_service_unavailable"
