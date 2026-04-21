from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import JWTAuthentication
from core.models import Section
from grades.models import CourseSectionAssignment
from notifications.constants import NotificationType
from notifications.services.notification_service import create_notification
from profile_management.models import FacultyProfile

from .hod_serializers import (
    HODAssignSlotRequestSerializer,
    HODClassSerializer,
    HODFacultySerializer,
    HODPeriodSerializer,
    HODSubjectSerializer,
    HODTimetableSlotSerializer,
)
from .models import Period, Subject, TimetableSlot
from .permissions import IsHOD


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DAY_ORDER = {day: index for index, day in enumerate(DAYS)}


class HODClassesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsHOD]

    def get(self, request):
        department = getattr(request.user, "department", None)
        if department is None:
            return Response([], status=status.HTTP_200_OK)

        classes_qs = (
            Section.objects.select_related("course")
            .filter(course__department=department)
            .order_by("year", "name", "code")
        )
        return Response(HODClassSerializer(classes_qs, many=True).data)


class HODTimetableView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsHOD]

    def get(self, request):
        class_id = request.query_params.get("class_id")
        if not class_id:
            return Response({"detail": "class_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        section = self._get_scoped_section(request, class_id)
        periods = list(Period.objects.order_by("order", "id"))

        with transaction.atomic():
            self._ensure_slots(section, periods)

        slots = (
            TimetableSlot.objects.select_related("period", "subject", "faculty", "faculty__user")
            .filter(class_section=section)
            .order_by("day", "period__order", "period_id")
        )
        ordered_slots = sorted(
            slots,
            key=lambda s: (DAY_ORDER.get(s.day, 999), s.period.order, s.period_id),
        )

        return Response(
            {
                "days": DAYS,
                "periods": HODPeriodSerializer(periods, many=True).data,
                "slots": HODTimetableSlotSerializer(ordered_slots, many=True).data,
            }
        )

    def _get_scoped_section(self, request, class_id):
        department = getattr(request.user, "department", None)
        section = get_object_or_404(
            Section.objects.select_related("course", "course__department"),
            id=class_id,
        )
        if department is None or section.course.department_id != department.id:
            raise Http404
        return section

    def _ensure_slots(self, section, periods):
        existing_keys = set(
            TimetableSlot.objects.filter(class_section=section).values_list("day", "period_id")
        )
        to_create = []
        for day in DAYS:
            for period in periods:
                if (day, period.id) not in existing_keys:
                    to_create.append(
                        TimetableSlot(
                            class_section=section,
                            day=day,
                            period=period,
                        )
                    )
        if to_create:
            TimetableSlot.objects.bulk_create(to_create)


class HODSubjectsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsHOD]

    def get(self, request):
        class_id = request.query_params.get("class_id")
        if not class_id:
            return Response({"detail": "class_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        department = getattr(request.user, "department", None)
        section = get_object_or_404(Section.objects.select_related("course"), id=class_id)
        if department is None or section.course.department_id != department.id:
            raise Http404

        subjects_qs = Subject.objects.filter(
            department=department,
            semester_number=section.year,
            is_active=True,
        ).order_by("name")

        data = [{"id": subject.id, "name": subject.name} for subject in subjects_qs]
        return Response(HODSubjectSerializer(data, many=True).data)


class HODFacultyBySubjectView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsHOD]

    def get(self, request):
        subject_id = request.query_params.get("subject_id")
        if not subject_id:
            return Response({"detail": "subject_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        department = getattr(request.user, "department", None)
        subject = get_object_or_404(Subject, id=subject_id)
        if department is None or subject.department_id != department.id:
            raise Http404

        faculty_ids = (
            CourseSectionAssignment.objects.filter(
                subject=subject,
                faculty__department=department,
                is_active=True,
            )
            .values_list("faculty_id", flat=True)
            .distinct()
        )

        faculties = (
            FacultyProfile.objects.select_related("user")
            .filter(id__in=faculty_ids, department=department, is_active=True)
            .order_by("first_name", "last_name", "id")
        )

        data = [{"id": faculty.id, "name": faculty.full_name} for faculty in faculties]
        return Response(HODFacultySerializer(data, many=True).data)


class HODAssignSlotView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsHOD]

    def post(self, request):
        serializer = HODAssignSlotRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        department = getattr(request.user, "department", None)

        slot = get_object_or_404(
            TimetableSlot.objects.select_related("class_section", "period", "class_section__course"),
            id=data["slot_id"],
        )
        if department is None or slot.class_section.course.department_id != department.id:
            raise Http404

        subject = get_object_or_404(
            Subject,
            id=data["subject_id"],
            department=department,
            is_active=True,
        )
        faculty = get_object_or_404(
            FacultyProfile.objects.select_related("user"),
            id=data["faculty_id"],
            department=department,
            is_active=True,
        )

        teaches_subject = CourseSectionAssignment.objects.filter(
            faculty=faculty,
            subject=subject,
            is_active=True,
        ).exists()
        if not teaches_subject:
            return Response(
                {"detail": "Selected faculty is not assigned to this subject."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slot.subject = subject
        slot.faculty = faculty
        slot.save(update_fields=["subject", "faculty", "updated_at"])

        class_name = slot.class_section.name
        section_name = slot.class_section.code
        period_label = slot.period.label
        message = (
            f"You have been assigned to {subject.name} on {slot.day} {period_label} "
            f"for {class_name} {section_name}"
        )

        create_notification(
            recipient=faculty.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title="New Timetable Assignment",
            message=message,
            actor=request.user,
            action_url="/faculty/timetable",
            metadata={
                "slot_id": slot.id,
                "day": slot.day,
                "period_label": period_label,
                "class_name": class_name,
                "section": section_name,
                "subject_id": subject.id,
                "faculty_id": faculty.id,
            },
        )

        return Response(
            {
                "success": True,
                "slot": HODTimetableSlotSerializer(slot).data,
            },
            status=status.HTTP_200_OK,
        )
