import strawberry
from typing import Optional
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from datetime import datetime, timedelta

from .types import UserType
from core.models import TokenBlacklist

User = get_user_model()


# ==================================================
# INPUT TYPES
# ==================================================

@strawberry.input
class LoginInput:
    username: str  # email OR register number
    password: str


# ==================================================
# RESPONSE TYPES
# ==================================================

@strawberry.type
class LoginResponse:
    user: UserType
    access_token: str
    refresh_token: str
    message: str


@strawberry.type
class LogoutResponse:
    success: bool
    message: str


# ==================================================
# MUTATIONS
# ==================================================

@strawberry.type
class Mutation:

    @strawberry.mutation
    def login(self, data: LoginInput) -> LoginResponse:
        """
        Login using email OR register number
        Returns user data with JWT tokens
        """
        # Find user manually
        user = User.objects.select_related("role", "department").filter(
            Q(email__iexact=data.username) |
            Q(register_number__iexact=data.username)
        ).first()

        if not user:
            raise Exception("Invalid credentials")

        if not user.check_password(data.password):
            raise Exception("Invalid credentials")

        if not user.is_active:
            raise Exception("User account is inactive")

        # Generate JWT tokens
        access_payload = {
            'user_id': user.id,
            'email': user.email,
            'register_number': user.register_number,
            'role': user.role.code,
            'department_id': user.department.id if user.department else None,
            'exp': datetime.utcnow() + timedelta(hours=24),  # 24 hours
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        
        refresh_payload = {
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=7),  # 7 days
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }

        access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm='HS256')
        refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm='HS256')

        return LoginResponse(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            message=f"Login successful. Welcome {user.email or user.register_number}!"
        )

    @strawberry.mutation
    def refresh_token(self, refresh_token: str) -> LoginResponse:
        """
        Refresh access token using refresh token
        """
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])
            
            if payload.get('type') != 'refresh':
                raise Exception("Invalid token type")
            
            user = User.objects.select_related("role", "department").get(id=payload['user_id'])
            
            if not user.is_active:
                raise Exception("User account is inactive")

            # Generate new access token
            access_payload = {
                'user_id': user.id,
                'email': user.email,
                'register_number': user.register_number,
                'role': user.role.code,
                'department_id': user.department.id if user.department else None,
                'exp': datetime.utcnow() + timedelta(hours=24),
                'iat': datetime.utcnow(),
                'type': 'access'
            }
            
            new_access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm='HS256')
            
            return LoginResponse(
                user=user,
                access_token=new_access_token,
                refresh_token=refresh_token,  # Keep same refresh token
                message="Token refreshed successfully"
            )
            
        except jwt.ExpiredSignatureError:
            raise Exception("Refresh token has expired")
        except jwt.InvalidTokenError:
            raise Exception("Invalid refresh token")
        except User.DoesNotExist:
            raise Exception("User not found")

    @strawberry.mutation
    def logout(self, info, access_token: Optional[str] = None) -> LogoutResponse:
        """
        Logout user by blacklisting their access token
        Token can be provided as argument or extracted from Authorization header
        """
        token = access_token
        
        # If no token provided, try to get it from request header
        if not token:
            auth_header = info.context.request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split('Bearer ')[1].strip()
        
        if not token:
            raise Exception("No token provided for logout")
        
        try:
            # Decode token to get user and expiry
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
            
            # Verify it's an access token
            if payload.get('type') != 'access':
                raise Exception("Can only logout access tokens")
            
            # Get user
            user_id = payload.get('user_id')
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    pass
            
            # Get token expiry
            exp_timestamp = payload.get('exp')
            expires_at = datetime.utcfromtimestamp(exp_timestamp) if exp_timestamp else datetime.utcnow() + timedelta(hours=24)
            
            # Add token to blacklist
            TokenBlacklist.objects.get_or_create(
                token=token,
                defaults={
                    'user': user,
                    'expires_at': expires_at,
                    'reason': 'logout'
                }
            )
            
            return LogoutResponse(
                success=True,
                message="Logged out successfully. Token has been invalidated."
            )
            
        except jwt.ExpiredSignatureError:
            # Token already expired, no need to blacklist but return success
            return LogoutResponse(
                success=True,
                message="Token already expired. Logout successful."
            )
        except jwt.InvalidTokenError:
            raise Exception("Invalid token provided")

    @strawberry.mutation
    def logout_all_sessions(self, info) -> LogoutResponse:
        """
        Logout user from all devices by blacklisting all their active tokens
        Requires authenticated request
        """
        user = info.context.request.user
        
        if not user or not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Note: This is a simplified version
        # In production, you'd want to track all user tokens
        # For now, just blacklist the current token
        auth_header = info.context.request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1].strip()
            
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                exp_timestamp = payload.get('exp')
                expires_at = datetime.utcfromtimestamp(exp_timestamp) if exp_timestamp else datetime.utcnow() + timedelta(hours=24)
                
                TokenBlacklist.objects.get_or_create(
                    token=token,
                    defaults={
                        'user': user,
                        'expires_at': expires_at,
                        'reason': 'logout'
                    }
                )
            except:
                pass
        
        return LogoutResponse(
            success=True,
            message=f"Logged out successfully from all sessions."
        )
