"""
GraphQL Types for HOD Attendance Reports
Provides comprehensive attendance reporting and analytics for HODs
"""
import strawberry
from typing import List, Optional
from enum import Enum


@strawberry.enum
class AttendanceRiskLevel(Enum):
    """Risk level based on attendance percentage"""
    GOOD = "GOOD"          # >= 75%
    WARNING = "WARNING"    # 60-74%
    CRITICAL = "CRITICAL"  # < 60%


@strawberry.enum
class AttendanceRecordStatus(Enum):
    """Status of an attendance record"""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"


@strawberry.type
class AttendanceReportSummaryStats:
    """Summary statistics for the entire report"""
    total_students: int
    overall_avg_percentage: float         # 0-100
    critical_count: int                   # students < 60%
    warning_count: int                    # students 60-74%
    good_count: int                       # students >= 75%
    total_classes_conducted: int
    department_name: str
    semester_label: str                   # e.g. "Semester III — July–Nov 2025"
    period_filter: str                    # human-readable description of active filters


@strawberry.type
class StudentAttendanceSummary:
    """Individual student attendance summary"""
    student_id: int
    student_name: str
    register_number: str
    roll_number: str
    class_name: str                       # "CSE-A · Sem 3"
    section_id: int
    year: int
    semester: int
    total_classes: int
    attended: int
    absent: int
    late: int
    percentage: float                     # 0-100
    risk_level: AttendanceRiskLevel
    last_absent_date: Optional[str]       # ISO date, nullable


@strawberry.type
class SubjectClassAttendance:
    """Subject-level attendance for a class"""
    subject_id: int
    subject_name: str
    subject_code: str
    faculty_name: str
    total_classes: int
    avg_percentage: float


@strawberry.type
class ClassAttendanceSummary:
    """Aggregated attendance for a class/section"""
    section_id: int
    class_name: str
    semester: int
    year: int
    total_students: int
    avg_percentage: float
    critical_count: int
    warning_count: int
    good_count: int
    total_classes_conducted: int
    subject_breakdown: List[SubjectClassAttendance]


@strawberry.type
class DepartmentAttendanceSummary:
    """Department-level attendance rollup"""
    department_id: int
    department_name: str
    department_code: str
    total_students: int
    avg_percentage: float
    critical_count: int
    warning_count: int
    good_count: int
    class_breakdown: List[ClassAttendanceSummary]


@strawberry.type
class PeriodSlot:
    """Timetable period slot information"""
    period_number: int
    start_time: str                       # "09:00"
    end_time: str                         # "09:50"
    label: str                            # "Period 1 (09:00–09:50)"


@strawberry.type
class SemesterOption:
    """Available semester option for filtering"""
    id: int
    label: str


@strawberry.type
class SubjectOption:
    """Available subject option for filtering"""
    id: int
    name: str
    code: str


@strawberry.type
class HODAttendanceReportData:
    """Complete HOD attendance report with all views"""
    summary_stats: AttendanceReportSummaryStats
    students: List[StudentAttendanceSummary]
    classes: List[ClassAttendanceSummary]
    departments: List[DepartmentAttendanceSummary]
    available_periods: List[PeriodSlot]
    available_semesters: List[SemesterOption]
    available_subjects: List[SubjectOption]


@strawberry.type
class SubjectAttendanceDetail:
    """Per-subject attendance detail for a student"""
    subject_id: int
    subject_name: str
    subject_code: str
    faculty_name: str
    total_classes: int
    attended: int
    absent: int
    late: int
    percentage: float
    risk_level: AttendanceRiskLevel


@strawberry.type
class StudentPeriodRecord:
    """Individual period attendance record"""
    date: str                             # "YYYY-MM-DD"
    subject_name: str
    subject_code: str
    period_label: str                     # "Period 3 (10:55–11:45)"
    status: AttendanceRecordStatus
    marked_by: str                        # faculty name or "System"
    is_manually_marked: bool


@strawberry.type
class StudentAttendanceDetail:
    """Detailed attendance for a single student"""
    student_id: int
    student_name: str
    register_number: str
    roll_number: str
    class_name: str
    semester: int
    year: int
    subject_summaries: List[SubjectAttendanceDetail]
    period_records: List[StudentPeriodRecord]


@strawberry.type
class ClassAttendanceDetail:
    """Detailed attendance for a class/section"""
    section_id: int
    class_name: str
    semester: int
    year: int
    students: List[StudentAttendanceSummary]
    subject_breakdown: List[SubjectClassAttendance]
