"""
SSE authentication for token-based auth.
Handles JWT authentication from query parameters for EventSource connections.
"""
import logging
import jwt
from typing import Optional
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


User = get_user_model()
logger = logging.getLogger(__name__)


class SSETokenAuthentication(BaseAuthentication):
    """
    JWT authentication for SSE connections.
    Extracts token from query parameter (since EventSource can't send headers).
    """
    
    def authenticate(self, request):
        """
        Authenticate the request using JWT from query parameter.
        
        Returns:
            tuple: (user, token) if authenticated
            None: if no token provided
            
        Raises:
            AuthenticationFailed: if token is invalid or expired
        """
        # Get token from query parameter
        token = request.GET.get('token')
        
        if not token:
            return None
        
        try:
            # Decode JWT token
            secret_key = settings.SECRET_KEY
            algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
            
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            
            # Get user ID from payload
            user_id = payload.get('user_id') or payload.get('id')
            
            if not user_id:
                raise AuthenticationFailed('Invalid token payload')
            
            # Get user
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise AuthenticationFailed('User not found')
            
            # Check if user is active
            if not user.is_active:
                raise AuthenticationFailed('User is inactive')
            
            return (user, token)
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed(f'Invalid token: {str(e)}')
        except Exception as e:
            logger.error(f"SSE authentication error: {str(e)}")
            raise AuthenticationFailed('Authentication failed')


def authenticate_sse_request(token: str) -> Optional[User]:
    """
    Authenticate SSE request using JWT token.
    Convenience function for manual authentication.
    
    Args:
        token: JWT token string
        
    Returns:
        User instance if authenticated, None otherwise
    """
    try:
        secret_key = settings.SECRET_KEY
        algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
        
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        
        user_id = payload.get('user_id') or payload.get('id')
        
        if not user_id:
            return None
        
        user = User.objects.get(id=user_id, is_active=True)
        return user
        
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist):
        return None
    except Exception as e:
        logger.error(f"SSE token authentication error: {str(e)}")
        return None
