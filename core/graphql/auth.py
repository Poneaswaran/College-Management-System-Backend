"""
Utility functions for GraphQL authentication and authorization
"""
from functools import wraps
from typing import Any, Callable
import strawberry
from strawberry.types import Info


def is_authenticated(info: Info) -> bool:
    """
    Check if the user is authenticated
    
    Args:
        info: Strawberry Info object containing request context
        
    Returns:
        bool: True if user is authenticated, False otherwise
    """
    request = info.context.request
    return hasattr(request, 'user') and request.user.is_authenticated


def require_auth(func: Callable) -> Callable:
    """
    Decorator to require authentication for GraphQL resolvers
    Raises exception if user is not authenticated
    
    Usage:
        @strawberry.field
        @require_auth
        def my_query(self, info: Info) -> str:
            return "Authenticated"
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Find the Info object in args or kwargs
        info = None
        for arg in args:
            if isinstance(arg, Info):
                info = arg
                break
        if not info and 'info' in kwargs:
            info = kwargs['info']
        
        if not info:
            raise Exception("Authentication check requires Info parameter")
        
        if not is_authenticated(info):
            error_message = "Authentication required. Please login to access this resource."
            
            # Include JWT error if available
            request = info.context.request
            if hasattr(request, 'jwt_error'):
                error_message = f"Authentication failed: {request.jwt_error}"
            
            raise Exception(error_message)
        
        return func(*args, **kwargs)
    
    return wrapper


class IsAuthenticated(strawberry.permission.BasePermission):
    """
    Strawberry permission class to check authentication
    
    Usage:
        @strawberry.field(permission_classes=[IsAuthenticated])
        def my_query(self, info: Info) -> str:
            return "Authenticated"
    """
    message = "Authentication required. Please login to access this resource."

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        request = info.context.request
        
        # Check if user is authenticated
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            # Customize error message if JWT error exists
            if hasattr(request, 'jwt_error'):
                self.message = f"Authentication failed: {request.jwt_error}"
            return False
        
        return True


class IsStaff(strawberry.permission.BasePermission):
    """
    Permission class to check if user is staff (admin/HOD/faculty)
    """
    message = "Staff access required."

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        request = info.context.request
        
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            self.message = "Authentication required."
            return False
        
        if not request.user.is_staff:
            return False
        
        return True


class IsAdmin(strawberry.permission.BasePermission):
    """
    Permission class to check if user is admin
    """
    message = "Admin access required."

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        request = info.context.request
        
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            self.message = "Authentication required."
            return False
        
        if not (request.user.is_staff and request.user.is_superuser):
            return False
        
        return True


def check_role(info: Info, allowed_roles: list) -> bool:
    """
    Check if user has one of the allowed roles
    
    Args:
        info: Strawberry Info object
        allowed_roles: List of role codes (e.g., ['STUDENT', 'FACULTY'])
        
    Returns:
        bool: True if user has allowed role
    """
    if not is_authenticated(info):
        return False
    
    user = info.context.request.user
    return user.role.code in allowed_roles


def require_role(*allowed_roles):
    """
    Decorator to require specific roles for GraphQL resolvers
    
    Usage:
        @strawberry.field
        @require_role('FACULTY', 'HOD')
        def my_query(self, info: Info) -> str:
            return "Faculty or HOD only"
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Find the Info object
            info = None
            for arg in args:
                if isinstance(arg, Info):
                    info = arg
                    break
            if not info and 'info' in kwargs:
                info = kwargs['info']
            
            if not info:
                raise Exception("Role check requires Info parameter")
            
            if not is_authenticated(info):
                raise Exception("Authentication required")
            
            user = info.context.request.user
            if user.role.code not in allowed_roles:
                raise Exception(f"Access denied. Required roles: {', '.join(allowed_roles)}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
