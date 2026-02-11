"""
GraphQL types for Attendance System
"""
import strawberry
import strawberry_django
from typing import Optional, List
from datetime import date, time, datetime
from decimal import Decimal

from attendance.models import AttendanceSession, StudentAttendance, AttendanceReport


@strawberry_django.type(AttendanceSession)
class AttendanceSessionType:
    """GraphQL type for AttendanceSession"""
    
    id: strawberry.ID
    date: date
    status: str
    attendance_window_minutes: int
    cancellation_reason: Optional[str]
    notes: Optional[str]
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    blocked_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Properties
    is_active: bool
    can_mark_attendance: bool
    time_remaining: int
    total_students: int
    present_count: int
    attendance_percentage: float
    
    # Relationships
    @strawberry_django.field
    def timetable_entry(self) -> 'TimetableEntryType':
        return self.timetable_entry
    
    @strawberry_django.field
    def opened_by(self) -> Optional['UserType']:
        return self.opened_by
    
    @strawberry_django.field
    def blocked_by(self) -> Optional['UserType']:
        return self.blocked_by
    
    @strawberry_django.field
    def student_attendances(self) -> List['StudentAttendanceType']:
        return self.student_attendances.all()
    
    # Custom fields
    @strawberry.field
    def subject_name(self) -> str:
        """Get subject name"""
        return self.timetable_entry.subject.name
    
    @strawberry.field
    def section_name(self) -> str:
        """Get section name"""
        return self.timetable_entry.section.name
    
    @strawberry.field
    def faculty_name(self) -> str:
        """Get faculty name"""
        return self.timetable_entry.faculty.email or self.timetable_entry.faculty.register_number or "Unknown"
    
    @strawberry.field
    def period_info(self) -> str:
        """Get period information"""
        pd = self.timetable_entry.period_definition
        return f"Period {pd.period_number} ({pd.start_time.strftime('%H:%M')} - {pd.end_time.strftime('%H:%M')})"
    
    @strawberry.field
    def period_time(self) -> str:
        """Get period time (alias for period_info)"""
        pd = self.timetable_entry.period_definition
        return f"Period {pd.period_number} ({pd.start_time.strftime('%H:%M')} - {pd.end_time.strftime('%H:%M')})"
    
    @strawberry.field
    def status_message(self) -> str:
        """Get user-friendly status message"""
        if self.status == 'ACTIVE' and self.can_mark_attendance:
            return f"Active - {self.time_remaining} minutes remaining"
        elif self.status == 'ACTIVE' and not self.can_mark_attendance:
            return "Expired"
        elif self.status in ['BLOCKED', 'CANCELLED']:
            reason = self.cancellation_reason or "Not specified"
            return f"Cancelled - {reason}"
        elif self.status == 'CLOSED':
            return "Closed"
        return "Scheduled"

# Import types from other apps
from timetable.graphql.types import TimetableEntryType
from core.graphql.types import UserType


@strawberry_django.type(StudentAttendance)
class StudentAttendanceType:
    """GraphQL type for StudentAttendance"""
    
    id: strawberry.ID
    status: str
    marked_at: Optional[datetime]
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    device_info: strawberry.scalars.JSON
    is_manually_marked: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    # Properties
    is_present: bool
    is_late: bool
    
    # Relationships
    @strawberry_django.field
    def session(self) -> AttendanceSessionType:
        return self.session
    
    @strawberry_django.field
    def student(self) -> 'StudentProfileType':
        return self.student
    
    @strawberry_django.field
    def marked_by(self) -> Optional[UserType]:
        return self.marked_by
    
    # Custom fields
    @strawberry.field
    def student_name(self) -> str:
        """Get student full name"""
        return self.student.full_name
    
    @strawberry.field
    def register_number(self) -> str:
        """Get student register number"""
        return self.student.register_number
    
    @strawberry.field
    def subject_name(self) -> str:
        """Get subject name"""
        return self.session.timetable_entry.subject.name
    
    @strawberry.field
    def date(self) -> date:
        """Get session date"""
        return self.session.date
    
    @strawberry.field
    def has_image(self) -> bool:
        """Check if has attendance image"""
        return bool(self.attendance_image)
    
    @strawberry.field
    def image_url(self) -> Optional[str]:
        """Get image URL (secure, only for authorized users)"""
        if self.attendance_image:
            return self.attendance_image.url
        return None
    
    @strawberry.field
    def status_badge(self) -> str:
        """Get status with emoji"""
        badges = {
            'PRESENT': '✓ Present',
            'ABSENT': '✗ Absent',
            'LATE': '⚠ Late',
        }
        return badges.get(self.status, self.status)

# Import StudentProfileType
from profile_management.graphql.types import StudentProfileType


@strawberry_django.type(AttendanceReport)
class AttendanceReportType:
    """GraphQL type for AttendanceReport"""
    
    id: strawberry.ID
    total_classes: int
    present_count: int
    absent_count: int
    late_count: int
    attendance_percentage: Decimal
    is_below_threshold: bool
    last_calculated: datetime
    created_at: datetime
    
    # Relationships
    @strawberry_django.field
    def student(self) -> StudentProfileType:
        return self.student
    
    @strawberry_django.field
    def subject(self) -> 'SubjectType':
        return self.subject
    
    @strawberry_django.field
    def semester(self) -> 'SemesterType':
        return self.semester
    
    # Custom fields
    @strawberry.field
    def student_name(self) -> str:
        """Get student full name"""
        return self.student.full_name
    
    @strawberry.field
    def register_number(self) -> str:
        """Get student register number"""
        return self.student.register_number
    
    @strawberry.field
    def subject_name(self) -> str:
        """Get subject name"""
        return self.subject.name
    
    @strawberry.field
    def semester_info(self) -> str:
        """Get semester information"""
        return f"{self.semester.academic_year.year_code} - Semester {self.semester.number}"
    
    @strawberry.field
    def percentage_display(self) -> str:
        """Get formatted percentage"""
        return f"{float(self.attendance_percentage):.2f}%"
    
    @strawberry.field
    def status_message(self) -> str:
        """Get status message"""
        if self.is_below_threshold:
            return f"⚠ Below 75% - {self.percentage_display}"
        return f"✓ Good - {self.percentage_display}"
    
    @strawberry.field
    def classes_needed_for_75(self) -> int:
        """Calculate classes needed to reach minimum 75%"""
        if float(self.attendance_percentage) >= 75.0:
            return 0
        
        # Formula: (P + x) / (T + x) >= 0.75
        # Solve for x: x >= (0.75T - P) / 0.25
        target = 0.75
        present = self.present_count + self.late_count
        total = self.total_classes
        
        if total == 0:
            return 0
        
        needed = ((target * total) - present) / (1 - target)
        return max(0, int(needed) + 1)  # Round up

# Import SubjectType and SemesterType
from timetable.graphql.types import SubjectType, SemesterType


# Input Types for Mutations
@strawberry.input
class MarkAttendanceInput:
    """Input for marking attendance"""
    session_id: strawberry.ID
    image_data: str  # Base64 encoded image
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_info: Optional[strawberry.scalars.JSON] = None


@strawberry.input
class OpenSessionInput:
    """Input for opening attendance session"""
    timetable_entry_id: int
    date: date
    attendance_window_minutes: Optional[int] = 10


@strawberry.input
class BlockSessionInput:
    """Input for blocking/cancelling session"""
    session_id: int
    cancellation_reason: str


@strawberry.input
class ManualMarkAttendanceInput:
    """Input for manually marking attendance"""
    session_id: int
    student_id: int
    status: str  # PRESENT, ABSENT, LATE
    notes: Optional[str] = None


# Response Types
@strawberry.type
class MarkAttendanceResponse:
    """Response for mark attendance mutation"""
    attendance: StudentAttendanceType
    message: str
    success: bool = True


# Response Types
@strawberry.type
class MarkAttendanceResponse:
    """Response for mark attendance mutation"""
    attendance: StudentAttendanceType
    message: str
    success: bool = True
