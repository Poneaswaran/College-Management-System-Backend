from django.db import transaction
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import JWTAuthentication
from core.models import Section
from notifications.constants import NotificationType
from notifications.services.notification_service import create_notification
from profile_management.models import FacultyProfile, Semester, SectionIncharge

from .hod_serializers import (
    HODAssignSlotRequestSerializer,
    HODClassSerializer,
    HODFacultySerializer,
    HODPeriodSerializer,
    HODSubjectSerializer,
    HODTimetableSlotSerializer,
    HODSectionInchargeSerializer,
    HODAssignInchargeSerializer,
)
from .models import Period, Subject, TimetableSlot, SectionSubjectRequirement, TimetableEntry, PeriodDefinition
from .permissions import IsHOD
from .validators import TimetableConflictValidator
from rest_framework.pagination import PageNumberPagination

class HODFacultyPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DAY_ORDER = {day: index for index, day in enumerate(DAYS)}
DAY_NUMBER = {
    "Monday": 1, "Tuesday": 2, "Wednesday": 3,
    "Thursday": 4, "Friday": 5, "Saturday": 6, "Sunday": 7,
}


class HODClassesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsHOD]
    pagination_class = HODFacultyPagination

    def get(self, request):
        department = getattr(request.user, "department", None)
        search = request.query_params.get("search")
        
        if department is None:
            return Response([], status=status.HTTP_200_OK)

        classes_qs = (
            Section.objects.select_related("course")
            .filter(course__department=department)
        )

        if search:
            from django.db.models import Q
            classes_qs = classes_qs.filter(
                Q(name__icontains=search) | Q(course__name__icontains=search) | Q(code__icontains=search)
            )

        classes_qs = classes_qs.order_by("year", "name", "code")
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(classes_qs, request, view=self)
        if page is not None:
            serializer = HODClassSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

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
        
        # Consistent sorting for frontend grid
        ordered_slots = sorted(
            slots,
            key=lambda s: (DAY_ORDER.get(s.day, 999), s.period.order, s.period_id),
        )

        # 5. Fetch Class In-Charge (with inheritance logic)
        semester = Semester.objects.filter(is_current=True).first()
        incharge_data = None
        if semester:
            incharge = SectionIncharge.objects.filter(section=section, semester=semester).first()
            if not incharge:
                incharge = SectionIncharge.objects.filter(
                    section=section, 
                    semester__start_date__lt=semester.start_date
                ).order_by('-semester__start_date').first()
            
            if incharge:
                incharge_data = {
                    "faculty_id": incharge.faculty_id,
                    "faculty_name": incharge.faculty.get_full_name(),
                }

        return Response(
            {
                "days": DAYS,
                "periods": HODPeriodSerializer(periods, many=True, context={'request': request}).data,
                "slots": HODTimetableSlotSerializer(ordered_slots, many=True, context={'request': request}).data,
                "incharge": incharge_data,
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

        # Get subjects from SectionSubjectRequirement using efficient JOIN
        subjects = Subject.objects.filter(
            section_requirements__section=section,
            section_requirements__subject__department=department,
        ).distinct().order_by("name")
        
        return Response(HODSubjectSerializer(subjects, many=True).data)




class HODFacultyBySubjectView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsHOD]
    pagination_class = HODFacultyPagination

    def get(self, request):
        subject_id = request.query_params.get("subject_id")
        class_id = request.query_params.get("class_id")
        search = request.query_params.get("search")
        
        if not subject_id:
            return Response({"detail": "subject_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        department = getattr(request.user, "department", None)
        subject = get_object_or_404(Subject, id=subject_id)
        if department is None or subject.department_id != department.id:
            raise Http404

        # Return faculty with an active SectionSubjectRequirement for that subject
        # If class_id is provided, filter specifically for that class
        req_filter = {"subject": subject, "faculty__department": department}
        if class_id:
            req_filter["section_id"] = class_id

        faculty_users = SectionSubjectRequirement.objects.filter(
            **req_filter
        ).values_list('faculty_id', flat=True).distinct()

        profiles = (
            FacultyProfile.objects.select_related("user")
            .filter(user_id__in=faculty_users, department=department, is_active=True)
        )

        if search:
            from django.db.models import Q
            profiles = profiles.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )

        profiles = profiles.order_by("first_name", "last_name", "id")
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(profiles, request, view=self)
        if page is not None:
            serializer = HODFacultySerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        return Response(HODFacultySerializer(profiles, many=True, context={'request': request}).data)


class HODDepartmentFacultyView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsHOD]
    pagination_class = HODFacultyPagination

    def get(self, request):
        department = getattr(request.user, "department", None)
        search = request.query_params.get("search")
        
        if department is None:
            return Response([], status=status.HTTP_200_OK)

        profiles = (
            FacultyProfile.objects.select_related("user")
            .filter(department=department, is_active=True)
        )

        if search:
            from django.db.models import Q
            profiles = profiles.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )

        profiles = profiles.order_by("first_name", "last_name", "id")
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(profiles, request, view=self)
        if page is not None:
            serializer = HODFacultySerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        return Response(HODFacultySerializer(profiles, many=True, context={'request': request}).data)


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

        if slot.period.is_break:
            return Response({"detail": "Break periods cannot be assigned"}, status=status.HTTP_400_BAD_REQUEST)

        subject = get_object_or_404(
            Subject,
            id=data["subject_id"],
            department=department,
            is_active=True,
        )
        faculty_profile = get_object_or_404(
            FacultyProfile.objects.select_related("user"),
            id=data["faculty_id"],
            department=department,
            is_active=True,
        )

        # 1. Verify SectionSubjectRequirement
        has_requirement = SectionSubjectRequirement.objects.filter(
            section=slot.class_section,
            subject=subject,
            faculty=faculty_profile.user
        ).exists()

        if not has_requirement:
            return Response(
                {"detail": "Selected faculty is not assigned to this subject for this class in requirements."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Check Load Limit
        req = SectionSubjectRequirement.objects.filter(
            section=slot.class_section,
            subject=subject
        ).select_related("semester").first()
        if not req:
            return Response(
                {"detail": "No requirement found for this subject and class."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        semester = req.semester

        # teaching_load is a per-semester total limit, not a weekly cap 
        # (effectively limits number of recurring slots in the grid)
        current_load = TimetableEntry.objects.filter(
            faculty=faculty_profile.user,
            semester=semester,
            is_active=True
        ).count()

        if current_load >= faculty_profile.teaching_load:
             return Response(
                 {"detail": f"{faculty_profile.full_name} has reached their weekly load limit of {faculty_profile.teaching_load} periods"},
                 status=status.HTTP_400_BAD_REQUEST
             )

        # 3. Conflict Validation
        # Find the period_definition mapping for this slot
        pdef = PeriodDefinition.objects.filter(
            semester=semester,
            day_of_week=DAY_NUMBER.get(slot.day, 1),
            period_number=slot.period.order # Period.order maps to PeriodDefinition.period_number
        ).first()

        if not pdef:
             return Response({"detail": "No period definition found for this slot in the current semester."}, status=status.HTTP_400_BAD_REQUEST)

        is_valid, conflict_msg = TimetableConflictValidator.validate_entry({
            'id': None, # New entry
            'faculty_id': faculty_profile.user_id,
            'room_id': None, # Room assigned separately
            'section_id': slot.class_section_id,
            'period_definition_id': pdef.id,
            'semester_id': semester.id,
        })

        if not is_valid:
            if "already teaching" in conflict_msg or "already has a class" in conflict_msg:
                return Response({"detail": conflict_msg}, status=status.HTTP_409_CONFLICT)
            return Response({"detail": conflict_msg}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Update TimetableSlot
            slot.subject = subject
            slot.faculty = faculty_profile
            slot.save(update_fields=["subject", "faculty", "updated_at"])

            # Create or update TimetableEntry
            TimetableEntry.objects.update_or_create(
                section=slot.class_section,
                period_definition=pdef,
                semester=semester,
                defaults={
                    "subject": subject,
                    "faculty": faculty_profile.user,
                    "is_active": True,
                },
            )

        # 4. Notification
        if hasattr(request.user, 'faculty_profile'):
            hod_name = request.user.faculty_profile.full_name
        else:
            hod_name = request.user.get_full_name() or request.user.email
            
        message = (
            f"You have been assigned {subject.name} on {slot.day} {slot.period.label} "
            f"({slot.period.start_time.strftime('%H:%M')}–{slot.period.end_time.strftime('%H:%M')}) "
            f"for {slot.class_section.name} {slot.class_section.code} by HOD {hod_name}"
        )

        create_notification(
            recipient=faculty_profile.user,
            notification_type=NotificationType.ANNOUNCEMENT,
            title="New Timetable Assignment",
            message=message,
            actor=request.user,
            action_url="/faculty/timetable",
        )

        # Re-fetch slot with relations before serializing
        slot = TimetableSlot.objects.select_related(
            "period", "subject", "faculty", "faculty__user"
        ).get(id=slot.id)
        
        return Response(
            {
                "success": True,
                "slot": HODTimetableSlotSerializer(slot).data,
            },
            status=status.HTTP_200_OK,
        )


class HODSectionInchargeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsHOD]

    def get(self, request):
        department = getattr(request.user, "department", None)
        if department is None:
            return Response([], status=status.HTTP_200_OK)

        semester = Semester.objects.filter(is_current=True).first()
        if not semester:
             return Response({"detail": "No current semester found"}, status=status.HTTP_400_BAD_REQUEST)

        sections = Section.objects.select_related("course").filter(course__department=department).order_by("year", "name")
        results = []

        for section in sections:
            # 1. Look for current assignment
            incharge = SectionIncharge.objects.filter(section=section, semester=semester).first()
            
            # 2. If not found, look for LATEST previous assignment (Auto-Carry-Over Logic)
            is_inherited = False
            if not incharge:
                incharge = SectionIncharge.objects.filter(
                    section=section, 
                    semester__start_date__lt=semester.start_date
                ).order_by('-semester__start_date').first()
                if incharge:
                    is_inherited = True
            
            if incharge:
                data = HODSectionInchargeSerializer(incharge).data
                data["is_inherited"] = is_inherited
                data["section_full_name"] = f"{section.course.code} {section.year}-{section.name}"
                results.append(data)
            else:
                results.append({
                    "section": section.id,
                    "section_name": section.name,
                    "section_full_name": f"{section.course.code} {section.year}-{section.name}",
                    "faculty": None,
                    "faculty_name": "Unassigned",
                    "is_inherited": False
                })

        return Response(results)

    def post(self, request):
        serializer = HODAssignInchargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        department = getattr(request.user, "department", None)
        semester = Semester.objects.filter(is_current=True).first()
        if not semester:
             return Response({"detail": "No current semester found"}, status=status.HTTP_400_BAD_REQUEST)

        section = get_object_or_404(Section, id=data["section_id"])
        if department is None or section.course.department_id != department.id:
            raise Http404

        from django.contrib.auth import get_user_model
        User = get_user_model()
        faculty = get_object_or_404(User, id=data["faculty_id"], role__code='FACULTY')
        
        # Override inheritance or existing assignment for current semester
        incharge, created = SectionIncharge.objects.update_or_create(
            section=section,
            semester=semester,
            defaults={"faculty": faculty}
        )

        return Response(HODSectionInchargeSerializer(incharge).data)
