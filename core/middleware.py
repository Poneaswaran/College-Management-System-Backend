"""
JWT Authentication Middleware for Bearer Token Authentication
"""
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin
from core.models import TokenBlacklist

User = get_user_model()


class JWTAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to authenticate requests using JWT Bearer tokens.
    Extracts token from Authorization header: "Bearer <token>"
    and attaches authenticated user to request.user
    
    Usage:
        Add 'Authorization: Bearer <access_token>' header to requests
        
    Features:
        - Validates JWT access tokens
        - Attaches authenticated user to request
        - Works alongside Django session authentication
        - Provides detailed error messages via request.jwt_error
    """
    
    def process_request(self, request):
        """
        Process incoming request and authenticate via JWT if Bearer token present
        
        Args:
            request: Django HttpRequest object
        """
        # Get Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        # Check if it's a Bearer token
        if auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1].strip()
            
            # Check if token is blacklisted (logged out)
            if TokenBlacklist.is_blacklisted(token):
                request.user = AnonymousUser()
                request.jwt_error = 'Token has been logged out'
                return
            
            try:
                # Decode JWT token
                payload = jwt.decode(
                    token,
                    settings.SECRET_KEY,
                    algorithms=[settings.JWT_ALGORITHM]
                )
                
                # Verify token type (must be 'access' token, not 'refresh')
                if payload.get('type') != 'access':
                    request.user = AnonymousUser()
                    request.jwt_error = 'Invalid token type. Expected access token.'
                    return
                
                # Get user from database
                user_id = payload.get('user_id')
                if user_id:
                    try:
                        # Fetch user with related data for performance
                        user = User.objects.select_related(
                            'role',
                            'department'
                        ).prefetch_related(
                            'student_profile',
                            'faculty_profile'
                        ).get(id=user_id, is_active=True)
                        
                        # Attach authenticated user to request
                        request.user = user
                        
                        # Store JWT payload for additional context if needed
                        request.jwt_payload = payload
                        
                    except User.DoesNotExist:
                        request.user = AnonymousUser()
                        request.jwt_error = 'User not found or inactive'
                else:
                    request.user = AnonymousUser()
                    request.jwt_error = 'No user_id in token payload'
                    
            except jwt.ExpiredSignatureError:
                # Token has expired - client should refresh or re-login
                request.user = AnonymousUser()
                request.jwt_error = 'Token has expired'
                
            except jwt.InvalidTokenError as e:
                # Invalid token format or signature
                request.user = AnonymousUser()
                request.jwt_error = f'Invalid token: {str(e)}'
        
        # If no Bearer token, Django's session auth middleware handles authentication
        # This allows both session-based and token-based auth to work together
