"""
Notification preference service - manages user notification preferences.
"""
import logging
from typing import List, Optional
from django.contrib.auth import get_user_model
from django.db import transaction

from notifications.models import NotificationPreference
from notifications.constants import NotificationCategory


User = get_user_model()
logger = logging.getLogger(__name__)


def get_or_create_default_preferences(user: User) -> List[NotificationPreference]:
    """
    Get or create default notification preferences for a user.
    Creates one preference per category with default settings.
    
    Args:
        user: User to create preferences for
        
    Returns:
        List of NotificationPreference instances
    """
    try:
        preferences = []
        
        for category in NotificationCategory.values:
            preference, created = NotificationPreference.objects.get_or_create(
                user=user,
                category=category,
                defaults={
                    "is_enabled": True,
                    "is_sse_enabled": True,
                    "is_email_enabled": False,
                }
            )
            preferences.append(preference)
            
            if created:
                logger.info(
                    f"Created default notification preference for user {user.id}, "
                    f"category {category}"
                )
        
        return preferences
        
    except Exception as e:
        logger.error(f"Failed to get/create preferences for user {user.id}: {str(e)}")
        raise


def get_user_preferences(user: User) -> List[NotificationPreference]:
    """
    Get all notification preferences for a user.
    Creates defaults if none exist.
    
    Args:
        user: User whose preferences to retrieve
        
    Returns:
        List of NotificationPreference instances
    """
    try:
        preferences = list(
            NotificationPreference.objects.filter(user=user).order_by("category")
        )
        
        # If no preferences exist, create defaults
        if not preferences:
            preferences = get_or_create_default_preferences(user)
        
        return preferences
        
    except Exception as e:
        logger.error(f"Failed to get preferences for user {user.id}: {str(e)}")
        raise


def update_preference(
    user: User,
    category: str,
    is_enabled: Optional[bool] = None,
    is_sse_enabled: Optional[bool] = None,
    is_email_enabled: Optional[bool] = None,
) -> NotificationPreference:
    """
    Update notification preference for a user and category.
    
    Args:
        user: User whose preference to update
        category: Notification category
        is_enabled: Master toggle (if None, not updated)
        is_sse_enabled: SSE delivery toggle (if None, not updated)
        is_email_enabled: Email delivery toggle (if None, not updated)
        
    Returns:
        Updated NotificationPreference instance
        
    Raises:
        ValueError: If invalid category
    """
    try:
        # Validate category
        if category not in NotificationCategory.values:
            raise ValueError(f"Invalid category: {category}")
        
        # Get or create preference
        preference, created = NotificationPreference.objects.get_or_create(
            user=user,
            category=category,
            defaults={
                "is_enabled": True,
                "is_sse_enabled": True,
                "is_email_enabled": False,
            }
        )
        
        # Update fields that are provided
        update_fields = ["updated_at"]
        
        if is_enabled is not None:
            preference.is_enabled = is_enabled
            update_fields.append("is_enabled")
        
        if is_sse_enabled is not None:
            preference.is_sse_enabled = is_sse_enabled
            update_fields.append("is_sse_enabled")
        
        if is_email_enabled is not None:
            preference.is_email_enabled = is_email_enabled
            update_fields.append("is_email_enabled")
        
        # Save if any fields were updated
        if len(update_fields) > 1:  # More than just updated_at
            preference.save(update_fields=update_fields)
            logger.info(
                f"Updated notification preference for user {user.id}, "
                f"category {category}"
            )
        
        return preference
        
    except Exception as e:
        logger.error(
            f"Failed to update preference for user {user.id}, category {category}: {str(e)}"
        )
        raise


def is_category_enabled(user: User, category: str) -> bool:
    """
    Check if a notification category is enabled for a user.
    
    Args:
        user: User to check
        category: Notification category to check
        
    Returns:
        True if category is enabled, False otherwise
    """
    try:
        # Get preference or assume enabled by default
        preference = NotificationPreference.objects.filter(
            user=user,
            category=category
        ).first()
        
        if preference:
            return preference.is_enabled
        
        # Default to enabled if no preference exists
        return True
        
    except Exception as e:
        logger.error(
            f"Failed to check if category {category} is enabled for user {user.id}: {str(e)}"
        )
        # Default to enabled on error
        return True


def is_sse_enabled(user: User, category: str) -> bool:
    """
    Check if SSE delivery is enabled for a category.
    
    Args:
        user: User to check
        category: Notification category to check
        
    Returns:
        True if SSE is enabled for the category, False otherwise
    """
    try:
        preference = NotificationPreference.objects.filter(
            user=user,
            category=category
        ).first()
        
        if preference:
            # SSE enabled if category is enabled AND SSE flag is True
            return preference.is_enabled and preference.is_sse_enabled
        
        # Default to enabled if no preference exists
        return True
        
    except Exception as e:
        logger.error(
            f"Failed to check if SSE is enabled for user {user.id}, category {category}: {str(e)}"
        )
        return True


def bulk_update_preferences(
    user: User,
    preferences_data: List[dict]
) -> List[NotificationPreference]:
    """
    Bulk update multiple notification preferences.
    
    Args:
        user: User whose preferences to update
        preferences_data: List of dicts with category and preference values
            Example: [
                {"category": "ATTENDANCE", "is_enabled": True, "is_sse_enabled": False},
                {"category": "ASSIGNMENT", "is_enabled": False},
            ]
            
    Returns:
        List of updated NotificationPreference instances
    """
    try:
        updated_preferences = []
        
        with transaction.atomic():
            for pref_data in preferences_data:
                category = pref_data.get("category")
                if not category:
                    continue
                
                preference = update_preference(
                    user=user,
                    category=category,
                    is_enabled=pref_data.get("is_enabled"),
                    is_sse_enabled=pref_data.get("is_sse_enabled"),
                    is_email_enabled=pref_data.get("is_email_enabled"),
                )
                updated_preferences.append(preference)
        
        logger.info(f"Bulk updated {len(updated_preferences)} preferences for user {user.id}")
        
        return updated_preferences
        
    except Exception as e:
        logger.error(f"Failed to bulk update preferences for user {user.id}: {str(e)}")
        raise


def reset_to_defaults(user: User) -> List[NotificationPreference]:
    """
    Reset all notification preferences to defaults for a user.
    
    Args:
        user: User whose preferences to reset
        
    Returns:
        List of reset NotificationPreference instances
    """
    try:
        with transaction.atomic():
            # Delete existing preferences
            NotificationPreference.objects.filter(user=user).delete()
            
            # Create new defaults
            preferences = get_or_create_default_preferences(user)
        
        logger.info(f"Reset notification preferences to defaults for user {user.id}")
        
        return preferences
        
    except Exception as e:
        logger.error(f"Failed to reset preferences for user {user.id}: {str(e)}")
        raise
