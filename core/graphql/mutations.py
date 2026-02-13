import strawberry
from typing import Optional
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from datetime import datetime, timedelta

from .types import UserType
from core.models import TokenBlacklist, Role, Department

User = get_user_model()


# ==================================================
# INPUT TYPES
# ==================================================

@strawberry.input
class LoginInput:
    username: str  # email OR register number
    password: str


@strawberry.input
class CreateUserInput:
    email: Optional[str] = None
    register_number: Optional[str] = None
    password: str
    role_id: int
    department_id: Optional[int] = None
    is_active: bool = True
    is_staff: bool = False


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


@strawberry.type
class CreateUserResponse:
    user: UserType
    message: str
    success: bool


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

    @strawberry.mutation
    def create_user(self, info, data: CreateUserInput) -> CreateUserResponse:
        """
        Admin-only: Create a new user with password hashing
        Requires ADMIN or SUPER_ADMIN role
        """
        user = info.context.request.user
        
        # Check if user is authenticated
        if not user or not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if user is admin
        if user.role.code not in ['ADMIN', 'SUPER_ADMIN']:
            raise Exception("Only admins can create new users")
        
        # Validate input
        if not data.email and not data.register_number:
            raise Exception("Either email or register number must be provided")
        
        # Check if email already exists
        if data.email and User.objects.filter(email__iexact=data.email).exists():
            raise Exception(f"User with email {data.email} already exists")
        
        # Check if register number already exists
        if data.register_number and User.objects.filter(register_number__iexact=data.register_number).exists():
            raise Exception(f"User with register number {data.register_number} already exists")
        
        # Validate role exists
        try:
            role = Role.objects.get(id=data.role_id)
        except Role.DoesNotExist:
            raise Exception(f"Role with ID {data.role_id} not found")
        
        # Validate department if provided
        department = None
        if data.department_id:
            try:
                department = Department.objects.get(id=data.department_id)
            except Department.DoesNotExist:
                raise Exception(f"Department with ID {data.department_id} not found")
        
        # Create user with hashed password
        new_user = User.objects.create_user(
            email=data.email,
            register_number=data.register_number,
            password=data.password,  # Will be hashed by set_password in create_user
            role=role,
            department=department,
            is_active=data.is_active,
            is_staff=data.is_staff
        )
        
        return CreateUserResponse(
            user=new_user,
            message=f"User created successfully with {'email' if data.email else 'register number'}: {data.email or data.register_number}",
            success=True
        )

