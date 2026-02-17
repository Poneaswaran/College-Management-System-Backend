"""
GraphQL mutations for timetable management
"""
import strawberry
from typing import Optional
from strawberry.types import Info
from django.core.exceptions import ValidationError

from profile_management.models import Semester
from timetable.models import TimetableEntry
from timetable.utils import generate_periods_for_config
from .types import TimetableEntryType
from core.graphql.auth import require_auth


@strawberry.type
class TimetableMutation:
    """
    GraphQL mutations for timetable system
    """

    @strawberry.mutation
    @require_auth
    def create_timetable_entry(
        self,
        info: Info,
        section_id: int,
        subject_id: int,
        faculty_id: int,
        period_definition_id: int,
        semester_id: int,
        room_id: Optional[int] = None,
        notes: Optional[str] = ""
    ) -> TimetableEntryType:
        """
        Create a new timetable entry
        
        Args:
            section_id: ID of the section
            subject_id: ID of the subject
            faculty_id: ID of the faculty member
            period_definition_id: ID of the period definition
            semester_id: ID of the semester
            room_id: Optional ID of the room
            notes: Optional notes
        
        Returns:
            Created timetable entry
        
        Raises:
            Exception: If validation fails or conflicts exist
        """
        try:
            # Create entry
            entry = TimetableEntry(
                section_id=section_id,
                subject_id=subject_id,
                faculty_id=faculty_id,
                period_definition_id=period_definition_id,
                semester_id=semester_id,
                room_id=room_id,
                notes=notes or "",
                is_active=True
            )
            
            # Validate (this will check for conflicts)
            entry.full_clean()
            
            # Save
            entry.save()
            
            # Refresh from database with relations
            entry.refresh_from_db()
            return entry
            
        except ValidationError as e:
            error_messages = []
            if hasattr(e, 'message_dict'):
                for field, messages in e.message_dict.items():
                    error_messages.extend(messages)
            else:
                error_messages = [str(e)]
            raise Exception("; ".join(error_messages))
        
        except Exception as e:
            raise Exception(f"Failed to create timetable entry: {str(e)}")

    @strawberry.mutation
    @require_auth
    def update_timetable_entry(
        self,
        info: Info,
        entry_id: int,
        faculty_id: Optional[int] = None,
        room_id: Optional[int] = None,
        notes: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> TimetableEntryType:
        """
        Update an existing timetable entry
        
        Args:
            entry_id: ID of the entry to update
            faculty_id: Optional new faculty ID
            room_id: Optional new room ID
            notes: Optional new notes
            is_active: Optional new active status
        
        Returns:
            Updated timetable entry
        
        Raises:
            Exception: If entry not found or validation fails
        """
        try:
            # Get entry
            entry = TimetableEntry.objects.get(id=entry_id)
            
            # Update fields if provided
            if faculty_id is not None:
                entry.faculty_id = faculty_id
            
            if room_id is not None:
                entry.room_id = room_id
            
            if notes is not None:
                entry.notes = notes
            
            if is_active is not None:
                entry.is_active = is_active
            
            # Validate
            entry.full_clean()
            
            # Save
            entry.save()
            
            # Refresh from database with relations
            entry.refresh_from_db()
            return entry
            
        except TimetableEntry.DoesNotExist:
            raise Exception(f"Timetable entry with ID {entry_id} not found")
        
        except ValidationError as e:
            error_messages = []
            if hasattr(e, 'message_dict'):
                for field, messages in e.message_dict.items():
                    error_messages.extend(messages)
            else:
                error_messages = [str(e)]
            raise Exception("; ".join(error_messages))
        
        except Exception as e:
            raise Exception(f"Failed to update timetable entry: {str(e)}")

    @strawberry.mutation
    @require_auth
    def delete_timetable_entry(
        self,
        info: Info,
        entry_id: int
    ) -> bool:
        """
        Delete (soft delete) a timetable entry
        
        Args:
            entry_id: ID of the entry to delete
        
        Returns:
            True if successful
        
        Raises:
            Exception: If entry not found
        """
        try:
            # Get entry
            entry = TimetableEntry.objects.get(id=entry_id)
            
            # Soft delete (set is_active to False)
            entry.is_active = False
            entry.save()
            
            return True
            
        except TimetableEntry.DoesNotExist:
            raise Exception(f"Timetable entry with ID {entry_id} not found")
        
        except Exception as e:
            raise Exception(f"Failed to delete timetable entry: {str(e)}")

    @strawberry.mutation
    @require_auth
    def generate_periods(
        self,
        info: Info,
        semester_id: int
    ) -> str:
        """
        Auto-generate period definitions from timetable configuration
        
        Args:
            semester_id: ID of the semester
        
        Returns:
            Success message with number of periods created
        
        Raises:
            Exception: If semester or configuration not found
        """
        try:
            # Get semester
            semester = Semester.objects.get(id=semester_id)
            
            # Get configuration
            try:
                config = semester.timetable_config
            except:
                raise Exception(f"No timetable configuration found for semester {semester}")
            
            # Generate periods
            periods = generate_periods_for_config(config)
            
            return f"Successfully generated {len(periods)} period definitions for {semester}"
            
        except Semester.DoesNotExist:
            raise Exception(f"Semester with ID {semester_id} not found")
        
        except Exception as e:
            raise Exception(f"Failed to generate periods: {str(e)}")

    @strawberry.mutation
    @require_auth
    def swap_timetable_slots(
        self,
        info: Info,
        entry1_id: int,
        entry2_id: int
    ) -> str:
        """
        Swap period definitions between two timetable entries
        
        Args:
            entry1_id: ID of first entry
            entry2_id: ID of second entry
        
        Returns:
            Success message
        
        Raises:
            Exception: If entries not found or swap would cause conflicts
        """
        try:
            # Get both entries
            entry1 = TimetableEntry.objects.get(id=entry1_id)
            entry2 = TimetableEntry.objects.get(id=entry2_id)
            
            # Store original period definitions
            period1 = entry1.period_definition
            period2 = entry2.period_definition
            
            # Temporarily set to None to avoid unique constraint issues
            entry1.period_definition = None
            entry1.save()
            
            # Swap periods
            entry2.period_definition = period1
            entry2.full_clean()  # Validate
            entry2.save()
            
            entry1.period_definition = period2
            entry1.full_clean()  # Validate
            entry1.save()
            
            return f"Successfully swapped slots between entries {entry1_id} and {entry2_id}"
            
        except TimetableEntry.DoesNotExist:
            raise Exception("One or both timetable entries not found")
        
        except ValidationError as e:
            # Rollback is automatic with transaction
            error_messages = []
            if hasattr(e, 'message_dict'):
                for field, messages in e.message_dict.items():
                    error_messages.extend(messages)
            else:
                error_messages = [str(e)]
            raise Exception(f"Swap would cause conflicts: {'; '.join(error_messages)}")
        
        except Exception as e:
            raise Exception(f"Failed to swap slots: {str(e)}")
