"""
GraphQL Queries for HOD Attendance Reports
Provides comprehensive attendance reporting and analytics for HODs
"""
import strawberry
from typing import Optional
from datetime import datetime, date
from strawberry.types import Info
from django.db.models import Avg, Count, Q, F
from django.utils import timezone

from attendance.models import AttendanceReport, StudentAttendance, AttendanceSession
from attendance.graphql.hod_types import (
    HODAttendanceReportData,
    AttendanceReportSummaryStats,
    StudentAttendanceSummary,
    ClassAttendanceSummary,
    DepartmentAttendanceSummary,
    SubjectClassAttendance,
    AttendanceRiskLevel,
    PeriodSlot,
    SemesterOption,
    SubjectOption,
    StudentAttendanceDetail,
    SubjectAttendanceDetail,
    StudentPeriodRecord,
    AttendanceRecordStatus,
    ClassAttendanceDetail
)
from core.graphql.auth import require_auth


def get_risk_level(percentage: float) -> AttendanceRiskLevel:
    """Determine risk level based on attendance percentage"""
    if percentage >= 75.0:
        return AttendanceRiskLevel.GOOD
    elif percentage >= 60.0:
        return AttendanceRiskLevel.WARNING
    else:
        return AttendanceRiskLevel.CRITICAL


def format_period_filter(subject_id: Optional[int], period_number: Optional[int], 
                         subject_name: Optional[str], period_info: Optional[str]) -> str:
    """Format a human-readable filter description"""
    parts = []
    
    if period_number and period_info:
        parts.append(period_info)
    elif period_number:
        parts.append(f"Period {period_number}")
    else:
        parts.append("All Periods")
    
    if subject_id and subject_name:
        parts.append(subject_name)
    else:
        parts.append("All Subjects")
    
    return " · ".join(parts)


@strawberry.type
class HODAttendanceQuery:
    """HOD-specific attendance queries"""
    
    @strawberry.field
    @require_auth
    def hod_attendance_report(
        self,
        info: Info,
        department_id: Optional[int] = None,
        semester_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        period_number: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> HODAttendanceReportData:
        """
        Returns a full attendance report for the HOD's department.
        Supports filtering by semester, subject, period, and date range.
        """
        user = info.context.request.user
        
        # Permission check: Only HOD, PRINCIPAL, and ADMIN
        if user.role.code not in ['HOD', 'PRINCIPAL', 'ADMIN']:
            raise Exception("Access denied. Only HOD, Principal, or Admin can access attendance reports.")
        
        # Determine department based on role
        if user.role.code in ['PRINCIPAL', 'ADMIN']:
            # PRINCIPAL/ADMIN can access any department
            if department_id:
                from core.models import Department
                try:
                    department = Department.objects.get(id=department_id)
                except Department.DoesNotExist:
                    raise Exception("Department not found")
            else:
                # If no department specified, they need to provide one
                raise Exception("Principal/Admin must specify a department_id")
        else:
            # HOD role - must have faculty profile with department
            from profile_management.models import FacultyProfile
            try:
                faculty_profile = FacultyProfile.objects.select_related('department').get(user=user)
            except FacultyProfile.DoesNotExist:
                raise Exception("HOD user must have a faculty profile. Please contact administrator.")
            
            if not faculty_profile.department:
                raise Exception("HOD faculty profile must be assigned to a department. Please contact administrator.")
            
            # HOD can only access their own department
            department = faculty_profile.department
            
            # If department_id is specified by HOD, verify it matches their department
            if department_id and department_id != department.id:
                raise Exception("Access denied. HOD can only access their own department's data.")
        
        # Get current academic year and semester if not specified
        from profile_management.models import Semester, AcademicYear
        
        if semester_id:
            try:
                semester = Semester.objects.get(id=semester_id)
            except Semester.DoesNotExist:
                raise Exception("Semester not found")
        else:
            # Get current semester
            semester = Semester.objects.filter(is_current=True).first()
            if not semester:
                # Fallback to most recent semester
                semester = Semester.objects.order_by('-start_date').first()
        
        if not semester:
            raise Exception("No semester found")
        
        # Parse date range
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else semester.start_date
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else semester.end_date
        
        # Build base queryset for attendance reports
        reports_qs = AttendanceReport.objects.filter(
            student__department=department,
            semester=semester
        ).select_related('student', 'subject', 'semester', 'student__section', 'student__section__course')
        
        if subject_id:
            reports_qs = reports_qs.filter(subject_id=subject_id)
        
        # Get all students in department
        from profile_management.models import StudentProfile
        students_qs = StudentProfile.objects.filter(
            department=department,
            section__year__lte=4  # Limit to valid years
        ).select_related('user', 'section', 'section__course')
        
        # Build student summaries
        students_list = []
        total_students = 0
        critical_count = 0
        warning_count = 0
        good_count = 0
        total_percentage_sum = 0.0
        
        for student in students_qs:
            # Get student's reports
            student_reports = reports_qs.filter(student=student)
            
            if not student_reports.exists():
                continue
            
            # Calculate aggregates
            total_classes = sum(r.total_classes for r in student_reports)
            attended = sum(r.present_count + r.late_count for r in student_reports)
            absent = sum(r.absent_count for r in student_reports)
            late = sum(r.late_count for r in student_reports)
            
            percentage = round((attended / total_classes * 100), 1) if total_classes > 0 else 0.0
            risk_level = get_risk_level(percentage)
            
            # Get last absent date
            last_absent = StudentAttendance.objects.filter(
                student=student,
                status='ABSENT',
                session__date__gte=date_from_obj,
                session__date__lte=date_to_obj
            ).order_by('-session__date').first()
            
            last_absent_date = last_absent.session.date.isoformat() if last_absent else None
            
            students_list.append(StudentAttendanceSummary(
                student_id=student.id,
                student_name=student.full_name,
                register_number=student.register_number,
                roll_number=student.roll_number or "",
                class_name=f"{student.section.name} · Sem {student.section.year}",
                section_id=student.section.id,
                year=student.section.year,
                semester=semester.number,
                total_classes=total_classes,
                attended=attended,
                absent=absent,
                late=late,
                percentage=percentage,
                risk_level=risk_level,
                last_absent_date=last_absent_date
            ))
            
            total_students += 1
            total_percentage_sum += percentage
            
            if risk_level == AttendanceRiskLevel.CRITICAL:
                critical_count += 1
            elif risk_level == AttendanceRiskLevel.WARNING:
                warning_count += 1
            else:
                good_count += 1
        
        # Build class summaries
        from core.models import Section
        sections = Section.objects.filter(
            course__department=department
        ).prefetch_related('student_profiles')
        
        classes_list = []
        for section in sections:
            section_students = [s for s in students_list if s.section_id == section.id]
            
            if not section_students:
                continue
            
            section_avg = sum(s.percentage for s in section_students) / len(section_students) if section_students else 0.0
            section_critical = len([s for s in section_students if s.risk_level == AttendanceRiskLevel.CRITICAL])
            section_warning = len([s for s in section_students if s.risk_level == AttendanceRiskLevel.WARNING])
            section_good = len([s for s in section_students if s.risk_level == AttendanceRiskLevel.GOOD])
            section_total_classes = sum(s.total_classes for s in section_students) // len(section_students) if section_students else 0
            
            # Subject breakdown for this section (regular + combined)
            from timetable.models import Subject, TimetableEntry, CombinedClassSession
            subjects = Subject.objects.filter(
                Q(timetable_entries__section=section, timetable_entries__is_active=True)
                | Q(combined_class_sessions__sections=section, combined_class_sessions__is_active=True)
            ).distinct()
            
            subject_breakdown = []
            for subj in subjects:
                # Get faculty teaching this subject in this section
                timetable_entry = TimetableEntry.objects.filter(
                    section=section,
                    subject=subj,
                    is_active=True
                ).select_related('faculty').first()

                combined = None
                if not timetable_entry:
                    combined = CombinedClassSession.objects.filter(
                        subject=subj,
                        sections=section,
                        is_active=True
                    ).select_related('faculty').first()

                faculty_obj = timetable_entry.faculty if timetable_entry and timetable_entry.faculty else (combined.faculty if combined and combined.faculty else None)
                faculty_name = (getattr(getattr(faculty_obj, 'faculty_profile', None), 'full_name', None) or faculty_obj.email or 'Unknown') if faculty_obj else "Unknown"
                
                # Calculate subject stats
                subject_reports = reports_qs.filter(
                    subject=subj,
                    student__section=section
                )
                
                if subject_reports.exists():
                    subj_total_classes = subject_reports.aggregate(avg=Avg('total_classes'))['avg'] or 0
                    subj_avg_percentage = subject_reports.aggregate(avg=Avg('attendance_percentage'))['avg'] or 0.0
                else:
                    subj_total_classes = 0
                    subj_avg_percentage = 0.0
                
                subject_breakdown.append(SubjectClassAttendance(
                    subject_id=subj.id,
                    subject_name=subj.name,
                    subject_code=subj.code,
                    faculty_name=faculty_name,
                    total_classes=int(subj_total_classes),
                    avg_percentage=round(float(subj_avg_percentage), 1)
                ))
            
            classes_list.append(ClassAttendanceSummary(
                section_id=section.id,
                class_name=section.name,
                semester=section.year,
                year=section.year,
                total_students=len(section_students),
                avg_percentage=round(section_avg, 1),
                critical_count=section_critical,
                warning_count=section_warning,
                good_count=section_good,
                total_classes_conducted=section_total_classes,
                subject_breakdown=subject_breakdown
            ))
        
        # Build department summary
        departments_list = [
            DepartmentAttendanceSummary(
                department_id=department.id,
                department_name=department.name,
                department_code=department.code,
                total_students=total_students,
                avg_percentage=round(total_percentage_sum / total_students, 1) if total_students > 0 else 0.0,
                critical_count=critical_count,
                warning_count=warning_count,
                good_count=good_count,
                class_breakdown=classes_list
            )
        ]
        
        # Get available periods
        from timetable.models import PeriodDefinition
        periods = PeriodDefinition.objects.filter(
            timetable_entries__section__course__department=department
        ).distinct().order_by('period_number')
        
        available_periods = [
            PeriodSlot(
                period_number=p.period_number,
                start_time=p.start_time.strftime('%H:%M'),
                end_time=p.end_time.strftime('%H:%M'),
                label=f"Period {p.period_number} ({p.start_time.strftime('%H:%M')}–{p.end_time.strftime('%H:%M')})"
            )
            for p in periods
        ]
        
        # Get available semesters
        semesters = Semester.objects.all().order_by('-start_date')
        available_semesters = [
            SemesterOption(
                id=s.id,
                label=f"Semester {s.number} — {s.start_date.strftime('%b %Y')}–{s.end_date.strftime('%b %Y')}"
            )
            for s in semesters
        ]
        
        # Get available subjects
        from timetable.models import Subject
        subjects = Subject.objects.filter(
            department=department
        ).distinct().order_by('name')
        
        available_subjects = [
            SubjectOption(
                id=s.id,
                name=s.name,
                code=s.code
            )
            for s in subjects
        ]
        
        # Format filter description
        subject_name = None
        period_info = None
        
        if subject_id:
            subj = Subject.objects.filter(id=subject_id).first()
            subject_name = f"{subj.code} - {subj.name}" if subj else None
        
        if period_number:
            period = periods.filter(period_number=period_number).first()
            if period:
                period_info = f"Period {period.period_number} ({period.start_time.strftime('%H:%M')}–{period.end_time.strftime('%H:%M')})"
        
        period_filter = format_period_filter(subject_id, period_number, subject_name, period_info)
        
        # Calculate total classes conducted
        total_classes_conducted = AttendanceSession.objects.filter(
            Q(timetable_entry__section__course__department=department)
            | Q(combined_session__sections__course__department=department),
            date__gte=date_from_obj,
            date__lte=date_to_obj,
            status='CLOSED'
        ).distinct().count()
        
        # Build summary stats
        summary_stats = AttendanceReportSummaryStats(
            total_students=total_students,
            overall_avg_percentage=round(total_percentage_sum / total_students, 1) if total_students > 0 else 0.0,
            critical_count=critical_count,
            warning_count=warning_count,
            good_count=good_count,
            total_classes_conducted=total_classes_conducted,
            department_name=department.name,
            semester_label=f"Semester {semester.number} — {semester.start_date.strftime('%b')}–{semester.end_date.strftime('%b %Y')}",
            period_filter=period_filter
        )
        
        return HODAttendanceReportData(
            summary_stats=summary_stats,
            students=students_list,
            classes=classes_list,
            departments=departments_list,
            available_periods=available_periods,
            available_semesters=available_semesters,
            available_subjects=available_subjects
        )
    
    @strawberry.field
    @require_auth
    def hod_student_attendance_detail(
        self,
        info: Info,
        student_id: int,
        semester_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> StudentAttendanceDetail:
        """
        Drill-down for a single student showing per-subject breakdown
        and period-level records.
        """
        user = info.context.request.user
        
        # Permission check
        if user.role.code not in ['HOD', 'PRINCIPAL', 'ADMIN']:
            raise Exception("Access denied. Only HOD, Principal, or Admin can access student attendance details.")
        
        # Get student
        from profile_management.models import StudentProfile
        try:
            student = StudentProfile.objects.select_related(
                'user', 'section', 'section__course', 'department'
            ).get(id=student_id)
        except StudentProfile.DoesNotExist:
            raise Exception("Student not found")
        
        # Department access check for HOD
        if user.role.code == 'HOD':
            from profile_management.models import FacultyProfile
            try:
                faculty_profile = FacultyProfile.objects.select_related('department').get(user=user)
            except FacultyProfile.DoesNotExist:
                raise Exception("HOD user must have a faculty profile. Please contact administrator.")
            
            if not faculty_profile.department:
                raise Exception("HOD faculty profile must be assigned to a department. Please contact administrator.")
            
            # Verify student belongs to HOD's department
            if student.department != faculty_profile.department:
                raise Exception("Access denied. HOD can only access students from their own department.")
        
        # Get semester
        from profile_management.models import Semester
        if semester_id:
            try:
                semester = Semester.objects.get(id=semester_id)
            except Semester.DoesNotExist:
                raise Exception("Semester not found")
        else:
            semester = Semester.objects.filter(is_current=True).first()
        
        if not semester:
            raise Exception("No semester found")
        
        # Parse dates
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else semester.start_date
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else semester.end_date
        
        # Get subject summaries
        reports = AttendanceReport.objects.filter(
            student=student,
            semester=semester
        ).select_related('subject')
        
        subject_summaries = []
        for report in reports:
            # Get faculty teaching this subject
            from timetable.models import TimetableEntry, CombinedClassSession
            timetable_entry = TimetableEntry.objects.filter(
                subject=report.subject,
                section=student.section,
                is_active=True
            ).select_related('faculty').first()

            combined = None
            if not timetable_entry:
                combined = CombinedClassSession.objects.filter(
                    subject=report.subject,
                    sections=student.section,
                    is_active=True
                ).select_related('faculty').first()

            faculty_obj = timetable_entry.faculty if timetable_entry and timetable_entry.faculty else (combined.faculty if combined and combined.faculty else None)
            faculty_name = (getattr(getattr(faculty_obj, 'faculty_profile', None), 'full_name', None) or faculty_obj.email or 'Unknown') if faculty_obj else "Unknown"
            
            attended = report.present_count + report.late_count
            percentage = float(report.attendance_percentage)
            
            subject_summaries.append(SubjectAttendanceDetail(
                subject_id=report.subject.id,
                subject_name=report.subject.name,
                subject_code=report.subject.code,
                faculty_name=faculty_name,
                total_classes=report.total_classes,
                attended=attended,
                absent=report.absent_count,
                late=report.late_count,
                percentage=percentage,
                risk_level=get_risk_level(percentage)
            ))
        
        # Get period records (limit to 200 most recent)
        attendances = StudentAttendance.objects.filter(
            student=student,
            session__date__gte=date_from_obj,
            session__date__lte=date_to_obj
        ).select_related(
            'session__timetable_entry__subject',
            'session__timetable_entry__period_definition',
            'session__combined_session__subject',
            'session__combined_session__period_definition',
            'marked_by'
        ).order_by(
            '-session__date',
            'session__timetable_entry__period_definition__period_number',
            'session__combined_session__period_definition__period_number'
        )[:200]
        
        period_records = []
        for att in attendances:
            period_def = att.session.period_definition
            subject = att.session.subject
            
            # Get marked by
            if att.is_manually_marked and att.marked_by:
                marked_by = getattr(getattr(att.marked_by, 'faculty_profile', None), 'full_name', None) or att.marked_by.email or att.marked_by.register_number or 'Faculty'
            else:
                marked_by = "System"
            
            # Map status
            status_map = {
                'PRESENT': AttendanceRecordStatus.PRESENT,
                'ABSENT': AttendanceRecordStatus.ABSENT,
                'LATE': AttendanceRecordStatus.LATE
            }
            
            period_records.append(StudentPeriodRecord(
                date=att.session.date.isoformat(),
                subject_name=subject.name,
                subject_code=subject.code,
                period_label=f"Period {period_def.period_number} ({period_def.start_time.strftime('%H:%M')}–{period_def.end_time.strftime('%H:%M')})",
                status=status_map.get(att.status, AttendanceRecordStatus.ABSENT),
                marked_by=marked_by,
                is_manually_marked=att.is_manually_marked
            ))
        
        return StudentAttendanceDetail(
            student_id=student.id,
            student_name=student.full_name,
            register_number=student.register_number,
            roll_number=student.roll_number or "",
            class_name=f"{student.section.name} · Sem {student.section.year}",
            semester=semester.number,
            year=student.section.year,
            subject_summaries=subject_summaries,
            period_records=period_records
        )
    
    @strawberry.field
    @require_auth
    def hod_class_attendance_detail(
        self,
        info: Info,
        section_id: int,
        semester_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> ClassAttendanceDetail:
        """
        Drill-down for a class/section showing all students and subject breakdown.
        """
        user = info.context.request.user
        
        # Permission check
        if user.role.code not in ['HOD', 'PRINCIPAL', 'ADMIN']:
            raise Exception("Access denied. Only HOD, Principal, or Admin can access class attendance details.")
        
        # Get section
        from core.models import Section
        try:
            section = Section.objects.select_related('course', 'course__department').get(id=section_id)
        except Section.DoesNotExist:
            raise Exception("Section not found")
        
        # Department access check for HOD
        if user.role.code == 'HOD':
            from profile_management.models import FacultyProfile
            try:
                faculty_profile = FacultyProfile.objects.select_related('department').get(user=user)
            except FacultyProfile.DoesNotExist:
                raise Exception("HOD user must have a faculty profile. Please contact administrator.")
            
            if not faculty_profile.department:
                raise Exception("HOD faculty profile must be assigned to a department. Please contact administrator.")
            
            # Verify section belongs to HOD's department
            if section.course.department != faculty_profile.department:
                raise Exception("Access denied. HOD can only access sections from their own department.")
        
        # Get semester
        from profile_management.models import Semester
        if semester_id:
            try:
                semester = Semester.objects.get(id=semester_id)
            except Semester.DoesNotExist:
                raise Exception("Semester not found")
        else:
            semester = Semester.objects.filter(is_current=True).first()
        
        if not semester:
            raise Exception("No semester found")
        
        # Parse dates
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else semester.start_date
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else semester.end_date
        
        # Get students in this section
        from profile_management.models import StudentProfile
        students = StudentProfile.objects.filter(section=section).select_related('user')
        
        students_list = []
        for student in students.order_by('roll_number'):
            # Get student reports
            reports_qs = AttendanceReport.objects.filter(
                student=student,
                semester=semester
            )
            
            if subject_id:
                reports_qs = reports_qs.filter(subject_id=subject_id)
            
            if not reports_qs.exists():
                continue
            
            total_classes = sum(r.total_classes for r in reports_qs)
            attended = sum(r.present_count + r.late_count for r in reports_qs)
            absent = sum(r.absent_count for r in reports_qs)
            late = sum(r.late_count for r in reports_qs)
            
            percentage = round((attended / total_classes * 100), 1) if total_classes > 0 else 0.0
            
            # Get last absent date
            last_absent = StudentAttendance.objects.filter(
                student=student,
                status='ABSENT',
                session__date__gte=date_from_obj,
                session__date__lte=date_to_obj
            ).order_by('-session__date').first()
            
            students_list.append(StudentAttendanceSummary(
                student_id=student.id,
                student_name=student.full_name,
                register_number=student.register_number,
                roll_number=student.roll_number or "",
                class_name=f"{section.name} · Sem {section.year}",
                section_id=section.id,
                year=section.year,
                semester=semester.number,
                total_classes=total_classes,
                attended=attended,
                absent=absent,
                late=late,
                percentage=percentage,
                risk_level=get_risk_level(percentage),
                last_absent_date=last_absent.session.date.isoformat() if last_absent else None
            ))
        
        # Get subject breakdown (regular + combined)
        from timetable.models import Subject, TimetableEntry, CombinedClassSession
        
        if subject_id:
            subjects = Subject.objects.filter(id=subject_id)
        else:
            subjects = Subject.objects.filter(
                Q(timetable_entries__section=section, timetable_entries__is_active=True)
                | Q(combined_class_sessions__sections=section, combined_class_sessions__is_active=True)
            ).distinct()
        
        subject_breakdown = []
        for subj in subjects:
            # Get faculty
            timetable_entry = TimetableEntry.objects.filter(
                section=section,
                subject=subj,
                is_active=True
            ).select_related('faculty').first()

            combined = None
            if not timetable_entry:
                combined = CombinedClassSession.objects.filter(
                    subject=subj,
                    sections=section,
                    is_active=True
                ).select_related('faculty').first()

            faculty_obj = timetable_entry.faculty if timetable_entry and timetable_entry.faculty else (combined.faculty if combined and combined.faculty else None)
            faculty_name = (getattr(getattr(faculty_obj, 'faculty_profile', None), 'full_name', None) or faculty_obj.email or 'Unknown') if faculty_obj else "Unknown"
            
            # Get stats
            subject_reports = AttendanceReport.objects.filter(
                subject=subj,
                student__section=section,
                semester=semester
            )
            
            if subject_reports.exists():
                subj_total_classes = subject_reports.aggregate(avg=Avg('total_classes'))['avg'] or 0
                subj_avg_percentage = subject_reports.aggregate(avg=Avg('attendance_percentage'))['avg'] or 0.0
            else:
                subj_total_classes = 0
                subj_avg_percentage = 0.0
            
            subject_breakdown.append(SubjectClassAttendance(
                subject_id=subj.id,
                subject_name=subj.name,
                subject_code=subj.code,
                faculty_name=faculty_name,
                total_classes=int(subj_total_classes),
                avg_percentage=round(float(subj_avg_percentage), 1)
            ))
        
        return ClassAttendanceDetail(
            section_id=section.id,
            class_name=section.name,
            semester=section.year,
            year=section.year,
            students=students_list,
            subject_breakdown=subject_breakdown
        )
