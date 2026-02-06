import strawberry
from typing import Optional
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from datetime import datetime, timedelta

from .types import UserType

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
