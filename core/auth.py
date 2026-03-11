import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication
from rest_framework import exceptions
from core.models import TokenBlacklist

User = get_user_model()

class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None
            
        token = auth_header.split('Bearer ')[1].strip()
        
        if TokenBlacklist.is_blacklisted(token):
            raise exceptions.AuthenticationFailed('Token has been logged out')
            
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            if payload.get('type') != 'access':
                raise exceptions.AuthenticationFailed('Invalid token type. Expected access token.')
                
            user_id = payload.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(id=user_id, is_active=True)
                    return (user, token)
                except User.DoesNotExist:
                    raise exceptions.AuthenticationFailed('User not found or inactive')
            else:
                raise exceptions.AuthenticationFailed('No user_id in token payload')
                
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError as e:
            raise exceptions.AuthenticationFailed(f'Invalid token: {str(e)}')
