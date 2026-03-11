"""
Service layer for Exam Management.
All business logic lives here — not in resolvers or models.
"""
import logging
import uuid
from typing import Optional
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Avg, Count, Q, F

from exams.models import (
    Exam, ExamSchedule, ExamSeatingArrangement,
    ExamResult, HallTicket
)

logger = logging.getLogger(__name__)


class ExamService:
    """Handles exam lifecycle operations."""

    @staticmethod
    @transaction.atomic
    def create_exam(
        name: str,
        exam_type: str,
        semester_id: int,
        start_date,
        end_date,
        created_by,
        department_id: int = None,
        max_marks: Decimal = Decimal('100'),
        pass_marks_percentage: Decimal = Decimal('40'),
        instructions: str = ''
    ) -> Exam:
        """Create a new exam cycle."""
        exam = Exam.objects.create(
            name=name,
            exam_type=exam_type,
            semester_id=semester_id,
            department_id=department_id,
            start_date=start_date,
            end_date=end_date,
            max_marks=max_marks,
            pass_marks_percentage=pass_marks_percentage,
            instructions=instructions,
            created_by=created_by,
            status='DRAFT'
        )
        logger.info("Exam created", extra={
            "exam_id": exam.id,
            "exam_type": exam_type,
            "created_by": created_by.id,
        })
        return exam

    @staticmethod
    @transaction.atomic
    def update_exam_status(exam_id: int, new_status: str, user) -> Exam:
        """Update exam cycle status with validation."""
        exam = Exam.objects.select_for_update().get(id=exam_id)

        valid_transitions = {
            'DRAFT': ['SCHEDULED', 'CANCELLED'],
            'SCHEDULED': ['ONGOING', 'CANCELLED'],
            'ONGOING': ['COMPLETED'],
            'COMPLETED': [],
            'CANCELLED': [],
        }

        allowed = valid_transitions.get(exam.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{exam.status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )

        exam.status = new_status
        exam.save(update_fields=['status', 'updated_at'])

        logger.info("Exam status updated", extra={
            "exam_id": exam.id,
            "old_status": exam.status,
            "new_status": new_status,
            "updated_by": user.id,
        })
        return exam


class ExamScheduleService:
    """Handles exam scheduling operations."""

    @staticmethod
    @transaction.atomic
    def create_schedule(
        exam_id: int,
        subject_id: int,
        section_id: int,
        date,
        start_time,
        end_time,
        shift: str = 'MORNING',
        duration_minutes: int = 180,
        room_id: int = None,
        invigilator_id: int = None,
        max_marks: Decimal = None,
        notes: str = ''
    ) -> ExamSchedule:
        """Create an exam schedule entry."""
        # Check for room conflicts
        if room_id:
            conflict = ExamSchedule.objects.filter(
                room_id=room_id,
                date=date,
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exists()
            if conflict:
                raise ValueError(
                    f"Room is already booked for the specified time slot on {date}"
                )

        # Check for invigilator conflicts
        if invigilator_id:
            conflict = ExamSchedule.objects.filter(
                invigilator_id=invigilator_id,
                date=date,
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exists()
            if conflict:
                raise ValueError(
                    f"Invigilator is already assigned to another exam at the specified time"
                )

        schedule = ExamSchedule.objects.create(
            exam_id=exam_id,
            subject_id=subject_id,
            section_id=section_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            shift=shift,
            duration_minutes=duration_minutes,
            room_id=room_id,
            invigilator_id=invigilator_id,
            max_marks=max_marks,
            notes=notes
        )

        logger.info("Exam schedule created", extra={
            "schedule_id": schedule.id,
            "exam_id": exam_id,
            "subject_id": subject_id,
        })
        return schedule

    @staticmethod
    def get_student_exam_schedule(student_profile, exam_id: int):
        """Get exam schedule for a specific student."""
        return ExamSchedule.objects.filter(
            exam_id=exam_id,
            section=student_profile.section
        ).select_related(
            'subject', 'room', 'exam', 'invigilator'
        ).order_by('date', 'start_time')


class SeatingService:
    """Handles seating arrangement operations."""

    @staticmethod
    @transaction.atomic
    def assign_seating(
        schedule_id: int,
        student_id: int,
        seat_number: str,
        room_id: int = None
    ) -> ExamSeatingArrangement:
        """Assign a seat to a student for a specific exam."""
        schedule = ExamSchedule.objects.get(id=schedule_id)
        # Use schedule's room if no override provided
        effective_room_id = room_id or (schedule.room_id if schedule.room else None)

        seating = ExamSeatingArrangement.objects.create(
            schedule_id=schedule_id,
            student_id=student_id,
            room_id=effective_room_id,
            seat_number=seat_number
        )
        return seating

    @staticmethod
    @transaction.atomic
    def bulk_assign_seating(schedule_id: int, student_ids: list, room_id: int = None):
        """Auto-assign seating for all students in a section."""
        schedule = ExamSchedule.objects.select_related('section', 'room').get(id=schedule_id)
        effective_room_id = room_id or (schedule.room_id if schedule.room else None)

        arrangements = []
        for idx, student_id in enumerate(student_ids, start=1):
            seat = f"S-{idx:03d}"
            arrangements.append(
                ExamSeatingArrangement(
                    schedule_id=schedule_id,
                    student_id=student_id,
                    room_id=effective_room_id,
                    seat_number=seat
                )
            )

        created = ExamSeatingArrangement.objects.bulk_create(
            arrangements, ignore_conflicts=True
        )
        logger.info("Bulk seating assigned", extra={
            "schedule_id": schedule_id,
            "count": len(created),
        })
        return created

    @staticmethod
    @transaction.atomic
    def mark_exam_attendance(schedule_id: int, student_id: int, is_present: bool):
        """Mark attendance for a student in an exam."""
        seating = ExamSeatingArrangement.objects.get(
            schedule_id=schedule_id,
            student_id=student_id
        )
        seating.is_present = is_present
        seating.marked_at = timezone.now()
        seating.save(update_fields=['is_present', 'marked_at'])
        return seating

    @staticmethod
    @transaction.atomic
    def bulk_mark_exam_attendance(schedule_id: int, attendance_data: list, marked_by):
        """
        Bulk mark attendance for an exam schedule.
        attendance_data: [{"student_id": int, "is_present": bool}, ...]
        """
        results = []
        now = timezone.now()
        
        for data in attendance_data:
            student_id = data.get('student_id')
            is_present = data.get('is_present', False)
            
            seating = ExamSeatingArrangement.objects.get(
                schedule_id=schedule_id,
                student_id=student_id
            )
            seating.is_present = is_present
            seating.marked_at = now
            seating.save(update_fields=['is_present', 'marked_at'])
            results.append(seating)
            
        logger.info("Bulk exam attendance marked", extra={
            "schedule_id": schedule_id,
            "count": len(results),
            "marked_by": marked_by.id,
        })
        return results


class ResultService:
    """Handles marks entry and result operations."""

    @staticmethod
    @transaction.atomic
    def enter_marks(
        schedule_id: int,
        student_id: int,
        marks_obtained: Decimal,
        entered_by,
        is_absent: bool = False,
        remarks: str = ''
    ) -> ExamResult:
        """Enter marks for a student."""
        result, created = ExamResult.objects.update_or_create(
            schedule_id=schedule_id,
            student_id=student_id,
            defaults={
                'marks_obtained': marks_obtained,
                'is_absent': is_absent,
                'entered_by': entered_by,
                'status': 'ENTERED',
                'remarks': remarks,
            }
        )

        logger.info("Exam result entered", extra={
            "result_id": result.id,
            "schedule_id": schedule_id,
            "student_id": student_id,
            "marks": str(marks_obtained),
            "entered_by": entered_by.id,
        })
        return result

    @staticmethod
    @transaction.atomic
    def bulk_enter_marks(schedule_id: int, results_data: list, entered_by):
        """
        Bulk enter marks.
        results_data: [{"student_id": int, "marks_obtained": Decimal, "is_absent": bool}, ...]
        """
        entered_results = []
        for data in results_data:
            result = ResultService.enter_marks(
                schedule_id=schedule_id,
                student_id=data['student_id'],
                marks_obtained=data.get('marks_obtained', Decimal('0')),
                entered_by=entered_by,
                is_absent=data.get('is_absent', False),
                remarks=data.get('remarks', '')
            )
            entered_results.append(result)

        return entered_results

    @staticmethod
    @transaction.atomic
    def verify_results(schedule_id: int, verified_by):
        """HOD/admin verifies all entered results for a schedule."""
        updated = ExamResult.objects.filter(
            schedule_id=schedule_id,
            status='ENTERED'
        ).update(
            status='VERIFIED',
            verified_by=verified_by,
            updated_at=timezone.now()
        )
        logger.info("Results verified", extra={
            "schedule_id": schedule_id,
            "count": updated,
            "verified_by": verified_by.id,
        })
        return updated

    @staticmethod
    @transaction.atomic
    def publish_results(exam_id: int, published_by):
        """Publish all verified results for an exam cycle."""
        now = timezone.now()
        updated = ExamResult.objects.filter(
            schedule__exam_id=exam_id,
            status='VERIFIED'
        ).update(
            status='PUBLISHED',
            published_at=now,
            updated_at=now
        )
        logger.info("Results published", extra={
            "exam_id": exam_id,
            "count": updated,
            "published_by": published_by.id,
        })
        return updated

    @staticmethod
    def get_result_statistics(schedule_id: int) -> dict:
        """Get statistics for a specific exam schedule."""
        results = ExamResult.objects.filter(schedule_id=schedule_id)
        total = results.count()
        if total == 0:
            return {
                'total_students': 0,
                'results_entered': 0,
                'passed': 0,
                'failed': 0,
                'absent': 0,
                'pass_percentage': 0,
                'average_marks': 0,
                'highest_marks': 0,
                'lowest_marks': 0,
            }

        entered = results.exclude(status='PENDING')
        passed = results.filter(is_pass=True, is_absent=False)
        failed = results.filter(is_pass=False, is_absent=False)
        absent = results.filter(is_absent=True)

        marks_stats = results.filter(
            is_absent=False,
            marks_obtained__isnull=False
        ).aggregate(
            avg=Avg('marks_obtained'),
            highest=models.Max('marks_obtained'),
            lowest=models.Min('marks_obtained'),
        )

        appeared = total - absent.count()

        return {
            'total_students': total,
            'results_entered': entered.count(),
            'passed': passed.count(),
            'failed': failed.count(),
            'absent': absent.count(),
            'pass_percentage': round((passed.count() / appeared * 100), 2) if appeared > 0 else 0,
            'average_marks': float(marks_stats['avg'] or 0),
            'highest_marks': float(marks_stats['highest'] or 0),
            'lowest_marks': float(marks_stats['lowest'] or 0),
        }


class HallTicketService:
    """Handles hall ticket generation."""

    @staticmethod
    @transaction.atomic
    def generate_hall_ticket(
        student_id: int,
        exam_id: int,
        generated_by,
        check_eligibility: bool = True
    ) -> HallTicket:
        """Generate a hall ticket for a student."""
        from profile_management.models import StudentProfile

        student = StudentProfile.objects.get(id=student_id)
        exam = Exam.objects.get(id=exam_id)

        # Check eligibility (attendance threshold)
        is_eligible = True
        reason = ''

        if check_eligibility:
            # Check attendance percentage
            from attendance.models import AttendanceReport
            reports = AttendanceReport.objects.filter(
                student=student,
                semester=exam.semester
            )
            low_attendance = reports.filter(is_below_threshold=True)
            if low_attendance.exists():
                subjects = ', '.join(
                    low_attendance.values_list('subject__name', flat=True)
                )
                is_eligible = False
                reason = f"Attendance below threshold in: {subjects}"

        # Generate unique ticket number
        ticket_number = f"HT-{exam.semester.number}-{exam.exam_type[:3]}-{student.register_number}-{uuid.uuid4().hex[:6].upper()}"

        hall_ticket, created = HallTicket.objects.update_or_create(
            student_id=student_id,
            exam_id=exam_id,
            defaults={
                'ticket_number': ticket_number,
                'is_eligible': is_eligible,
                'ineligibility_reason': reason,
                'generated_by': generated_by,
                'status': 'GENERATED',
            }
        )

        logger.info("Hall ticket generated", extra={
            "ticket_number": ticket_number,
            "student_id": student_id,
            "exam_id": exam_id,
            "is_eligible": is_eligible,
        })
        return hall_ticket

    @staticmethod
    @transaction.atomic
    def bulk_generate_hall_tickets(exam_id: int, section_id: int, generated_by):
        """Generate hall tickets for all students in a section."""
        from profile_management.models import StudentProfile

        students = StudentProfile.objects.filter(
            section_id=section_id,
            academic_status='ACTIVE'
        )

        tickets = []
        for student in students:
            ticket = HallTicketService.generate_hall_ticket(
                student_id=student.id,
                exam_id=exam_id,
                generated_by=generated_by,
                check_eligibility=True
            )
            tickets.append(ticket)

        logger.info("Bulk hall tickets generated", extra={
            "exam_id": exam_id,
            "section_id": section_id,
            "count": len(tickets),
        })
        return tickets
