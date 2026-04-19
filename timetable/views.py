"""
timetable/views.py

REST API views for the timetable application.

Existing views (preserved):
    SectionTimetableListView
    FacultyScheduleListView
    PeriodDefinitionListView
    TimetableEntryCreateView
    SectionCreateTimetableAPIView

New views:
    GenerateSemesterTimetableView — Item 3: full pipeline POST /timetable/generate/
    TimetableExportView           — Item 6: PDF export GET /timetable/export/
    GeneratePeriodsView           — Item 7: period generation POST /timetable/generate-periods/
"""

from datetime import date

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.db import transaction
from django.utils import timezone

from core.models import Section
from timetable.models import (
    PeriodDefinition,
    TimetableApprovalRequest,
    SectionSubjectRequirement,
    RoomMaintenanceBlock,
    Subject,
    CombinedClassSession,
    DepartmentSectionCombinePolicy,
    TimetableEntry,
)
from .serializers import (
    TimetableEntrySerializer,
    SectionCreateTimetableSerializer,
    TimetableDetailSerializer,
    PeriodDefinitionSerializer,
    TimetableApprovalRequestSerializer,
    TimetableApprovalRequestStatusUpdateSerializer,
    SectionSubjectRequirementSerializer,
    SectionSubjectRequirementBulkSerializer,
    RoomMaintenanceBlockSerializer,
    CombinedClassSessionSerializer,
    DepartmentSectionCombinePolicySerializer,
)
from .services import TimetableService


# ===========================================================================
# Existing views (preserved, unchanged)
# ===========================================================================

class SectionTimetableListView(APIView):
    """
    Get the full timetable for a specific section.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        section_id = request.query_params.get('section_id')
        semester_id = request.query_params.get('semester_id')
        include_combined = str(request.query_params.get('include_combined', '')).lower() in {'1', 'true', 'yes'}

        if not section_id or not semester_id:
            return Response(
                {'error': 'section_id and semester_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entries = TimetableService.get_section_timetable(section_id, semester_id)
        entries_data = TimetableDetailSerializer(entries, many=True).data

        if not include_combined:
            return Response(entries_data)

        combined = TimetableService.get_section_combined_sessions(section_id, semester_id)
        combined_data = CombinedClassSessionSerializer(combined, many=True).data
        return Response({"entries": entries_data, "combined_sessions": combined_data})


class FacultyScheduleListView(APIView):
    """
    Get the teaching schedule for a faculty member.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        faculty_id = request.query_params.get('faculty_id')
        semester_id = request.query_params.get('semester_id')
        include_combined = str(request.query_params.get('include_combined', '')).lower() in {'1', 'true', 'yes'}

        if not faculty_id or not semester_id:
            return Response(
                {'error': 'faculty_id and semester_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entries = TimetableService.get_faculty_timetable(faculty_id, semester_id)
        entries_data = TimetableDetailSerializer(entries, many=True).data

        if not include_combined:
            return Response(entries_data)

        combined = TimetableService.get_faculty_combined_sessions(faculty_id, semester_id)
        combined_data = CombinedClassSessionSerializer(combined, many=True).data
        return Response({"entries": entries_data, "combined_sessions": combined_data})


def _get_hod_department(user):
    role_code = getattr(getattr(user, 'role', None), 'code', '').upper()
    if role_code != 'HOD':
        return None

    department = getattr(user, 'department', None)
    if department:
        return department

    faculty_profile = getattr(user, 'faculty_profile', None)
    if faculty_profile and faculty_profile.department:
        return faculty_profile.department

    return None


class HODTimetableApprovalRequestListView(APIView):
    """
    List timetable approval requests scoped to the logged-in HOD's department.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        department = _get_hod_department(request.user)
        if not department:
            return Response(
                {'error': 'Only HOD users with a department can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = TimetableApprovalRequest.objects.select_related(
            'submitted_by',
            'semester',
            'semester__academic_year',
        ).filter(department=department)

        status_filter = request.query_params.get('status')
        semester_id = request.query_params.get('semester_id')

        if status_filter:
            status_filter = status_filter.upper()
            if status_filter in {'PENDING', 'APPROVED', 'REJECTED'}:
                qs = qs.filter(status=status_filter)

        if semester_id:
            qs = qs.filter(semester_id=semester_id)

        serializer = TimetableApprovalRequestSerializer(qs, many=True)
        return Response(serializer.data)


class HODTimetableApprovalRequestStatusUpdateView(APIView):
    """
    Update status (PENDING/APPROVED/REJECTED) of a timetable approval request.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int):
        department = _get_hod_department(request.user)
        if not department:
            return Response(
                {'error': 'Only HOD users with a department can update request status.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            request_obj = TimetableApprovalRequest.objects.get(pk=pk, department=department)
        except TimetableApprovalRequest.DoesNotExist:
            return Response({'error': 'Approval request not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TimetableApprovalRequestStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request_obj.status = serializer.validated_data['status']
        request_obj.review_note = serializer.validated_data.get('review_note', '')
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        request_obj.save(update_fields=['status', 'review_note', 'reviewed_by', 'reviewed_at', 'updated_at'])

        return Response(TimetableApprovalRequestSerializer(request_obj).data)


# ===========================================================================
# Section Combining (Option A) — Policies + Combined Sessions
# ===========================================================================


class DepartmentCombinePolicyListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        department_id = request.query_params.get('department_id')
        qs = DepartmentSectionCombinePolicy.objects.select_related('department').all().order_by('department__code')
        if department_id:
            qs = qs.filter(department_id=department_id)
        return Response(DepartmentSectionCombinePolicySerializer(qs, many=True).data)

    def post(self, request):
        serializer = DepartmentSectionCombinePolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        department = serializer.validated_data['department']

        policy, _created = DepartmentSectionCombinePolicy.objects.update_or_create(
            department=department,
            defaults={
                'enabled': serializer.validated_data.get('enabled', False),
                'max_sections': serializer.validated_data.get('max_sections', 2),
                'same_course_only': serializer.validated_data.get('same_course_only', True),
                'allow_cross_department': serializer.validated_data.get('allow_cross_department', False),
            },
        )

        partners = serializer.validated_data.get('allowed_partner_departments')
        if partners is not None:
            policy.allowed_partner_departments.set(partners)

        return Response(DepartmentSectionCombinePolicySerializer(policy).data, status=status.HTTP_201_CREATED)


class DepartmentCombinePolicyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        try:
            policy = DepartmentSectionCombinePolicy.objects.select_related('department').get(pk=pk)
        except DepartmentSectionCombinePolicy.DoesNotExist:
            return Response({'error': 'Policy not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(DepartmentSectionCombinePolicySerializer(policy).data)

    def patch(self, request, pk: int):
        try:
            policy = DepartmentSectionCombinePolicy.objects.get(pk=pk)
        except DepartmentSectionCombinePolicy.DoesNotExist:
            return Response({'error': 'Policy not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = DepartmentSectionCombinePolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        policy = serializer.save()
        return Response(DepartmentSectionCombinePolicySerializer(policy).data)

    def delete(self, request, pk: int):
        try:
            policy = DepartmentSectionCombinePolicy.objects.get(pk=pk)
        except DepartmentSectionCombinePolicy.DoesNotExist:
            return Response({'error': 'Policy not found.'}, status=status.HTTP_404_NOT_FOUND)
        policy.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CombinedClassSessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        semester_id = request.query_params.get('semester_id')
        section_id = request.query_params.get('section_id')
        faculty_id = request.query_params.get('faculty_id')

        qs = CombinedClassSession.objects.filter(is_active=True).select_related(
            'semester', 'period_definition', 'subject', 'faculty', 'room'
        ).prefetch_related('sections')

        if semester_id:
            qs = qs.filter(semester_id=semester_id)
        if section_id:
            qs = qs.filter(sections__id=section_id)
        if faculty_id:
            qs = qs.filter(faculty_id=faculty_id)

        qs = qs.order_by('period_definition__day_of_week', 'period_definition__start_time').distinct()
        return Response(CombinedClassSessionSerializer(qs, many=True).data)

    def post(self, request):
        serializer = CombinedClassSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        semester = serializer.validated_data['semester']
        period = serializer.validated_data['period_definition']
        subject = serializer.validated_data['subject']
        faculty = serializer.validated_data.get('faculty')
        room = serializer.validated_data.get('room')
        sections = serializer.validated_data['sections']
        supersede = serializer.validated_data.get('supersede_timetable_entries', True)

        if supersede:
            for s in sections:
                exists = TimetableEntry.objects.filter(
                    section=s,
                    semester=semester,
                    period_definition=period,
                    subject=subject,
                    is_active=True,
                ).exists()
                if not exists:
                    return Response(
                        {'error': f"Active TimetableEntry missing for section {s.id} at this slot/subject; cannot supersede."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        session = TimetableService.create_combined_class_session(
            semester_id=semester.id,
            period_definition_id=period.id,
            subject_id=subject.id,
            faculty_id=faculty.id if faculty else None,
            room_id=room.id if room else None,
            section_ids=[s.id for s in sections],
            notes=serializer.validated_data.get('notes', ""),
            created_by_id=request.user.id,
            supersede_timetable_entries=supersede,
        )

        return Response(CombinedClassSessionSerializer(session).data, status=status.HTTP_201_CREATED)


class CombinedClassSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        try:
            session = CombinedClassSession.objects.select_related(
                'semester', 'period_definition', 'subject', 'faculty', 'room'
            ).prefetch_related('sections').get(pk=pk)
        except CombinedClassSession.DoesNotExist:
            return Response({'error': 'Combined session not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CombinedClassSessionSerializer(session).data)

    def patch(self, request, pk: int):
        try:
            session = CombinedClassSession.objects.select_related('period_definition').get(pk=pk)
        except CombinedClassSession.DoesNotExist:
            return Response({'error': 'Combined session not found.'}, status=status.HTTP_404_NOT_FOUND)

        allowed_fields = {'faculty_id', 'room_id', 'notes', 'is_active'}
        unknown = set(request.data.keys()) - allowed_fields
        if unknown:
            return Response(
                {'error': f"Only {sorted(allowed_fields)} can be updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if 'room_id' in request.data:
            room_id = request.data.get('room_id')
            if room_id in (None, '', 'null'):
                TimetableService.assign_room_to_combined_session(session, None)
            else:
                try:
                    TimetableService.assign_room_to_combined_session(session, int(room_id))
                except (TypeError, ValueError):
                    return Response({'error': 'room_id must be an integer or null.'}, status=status.HTTP_400_BAD_REQUEST)

        if 'faculty_id' in request.data:
            faculty_id = request.data.get('faculty_id')
            session.faculty_id = int(faculty_id) if faculty_id not in (None, '', 'null') else None

        if 'notes' in request.data:
            session.notes = request.data.get('notes') or ""

        if 'is_active' in request.data:
            session.is_active = bool(request.data.get('is_active'))

        session.full_clean()
        session.save(update_fields=['faculty', 'notes', 'is_active', 'updated_at'])

        return Response(CombinedClassSessionSerializer(session).data)

    def delete(self, request, pk: int):
        try:
            session = CombinedClassSession.objects.get(pk=pk)
        except CombinedClassSession.DoesNotExist:
            return Response({'error': 'Combined session not found.'}, status=status.HTTP_404_NOT_FOUND)

        if session.allocation_id:
            TimetableService.assign_room_to_combined_session(session, None)

        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PeriodDefinitionListView(APIView):
    """
    Get all period definitions for a specific semester.
    Useful for populating creation forms.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        semester_id = request.query_params.get('semester_id')
        section_id  = request.query_params.get('section_id')

        if not semester_id or not section_id:
            return Response(
                {'error': 'semester_id and section_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not Section.objects.filter(id=section_id).exists():
            return Response({'error': 'Section not found.'}, status=status.HTTP_404_NOT_FOUND)

        periods = PeriodDefinition.objects.filter(
            semester_id=semester_id
        ).order_by('day_of_week', 'period_number')
        serializer = PeriodDefinitionSerializer(periods, many=True)
        return Response(serializer.data)


class TimetableEntryCreateView(APIView):
    """
    API view to create a standard timetable entry.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TimetableEntrySerializer(data=request.data)
        if serializer.is_valid():
            try:
                entry = TimetableService.create_timetable_entry(
                    section_id=serializer.validated_data.get('section_id'),
                    subject_id=serializer.validated_data.get('subject_id'),
                    faculty_id=serializer.validated_data.get('faculty_id'),
                    period_definition_id=serializer.validated_data.get('period_definition_id'),
                    semester_id=serializer.validated_data.get('semester_id'),
                    room_id=serializer.validated_data.get('room_id'),
                    notes=serializer.validated_data.get('notes', ""),
                )
                return Response(
                    TimetableEntrySerializer(entry).data,
                    status=status.HTTP_201_CREATED,
                )
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SectionCreateTimetableAPIView(APIView):
    """
    API for bulk creation of timetable entries for a specific section.
    Allows specifying a list of slots (subject, faculty, period, room) in one call.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SectionCreateTimetableSerializer(data=request.data)
        if serializer.is_valid():
            try:
                section_id  = serializer.validated_data.get('section_id')
                semester_id = serializer.validated_data.get('semester_id')
                entries_data = serializer.validated_data.get('entries')

                result = TimetableService.bulk_create_timetable_entries(
                    section_id=section_id,
                    semester_id=semester_id,
                    entries_data=entries_data,
                )

                return Response(
                    {
                        "success": True,
                        "count": len(result),
                        "message": "Successfully created timetable entries.",
                    },
                    status=status.HTTP_201_CREATED,
                )
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(
                    {'error': f"Failed to bulk create entries: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# Item 3 — Bulk Semester Timetable Generation
# ===========================================================================

class GenerateSemesterTimetableView(APIView):
    """
    POST /timetable/generate/

    Runs the full scheduling pipeline for a semester in one request:
      1. LabRotationGenerator.generate()
      2. SubjectDistributionService.distribute() + commit_distribution()
         for every Section
      3. RoomAllocatorService.allocate_period() for every PeriodDefinition

    Request body:
        { "semester_id": <int> }

    Response:
        {
            "lab_rotation_created": int,
            "entries_created": int,
            "overflow_count": int,
            "violations": [str, ...]
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        semester_id = request.data.get('semester_id')
        if not semester_id:
            return Response(
                {'error': 'semester_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            semester_id = int(semester_id)
        except (TypeError, ValueError):
            return Response(
                {'error': 'semester_id must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from timetable.scheduler import LabRotationGenerator, RoomAllocatorService
        from timetable.services import SubjectDistributionService, TimetableViolationNotifier
        from core.models import Section

        all_violations: list[str] = []
        entries_created = 0
        overflow_count  = 0

        try:
            # ── Step 1: Lab rotation ────────────────────────────────────────
            rotation_result = LabRotationGenerator.generate(semester_id)
            lab_rotation_created = rotation_result['created']

            # ── Step 2: Subject distribution for all sections ───────────────
            sections = Section.objects.all()
            for section in sections:
                try:
                    planned = SubjectDistributionService.distribute(
                        section_id=section.pk,
                        semester_id=semester_id,
                    )
                    saved = SubjectDistributionService.commit_distribution(planned)
                    entries_created += len(saved)
                except ValidationError as ex:
                    all_violations.append(
                        f"Section '{section.name}' distribution error: {ex}"
                    )

            # ── Step 3: Room allocation for every period ────────────────────
            periods = PeriodDefinition.objects.filter(semester_id=semester_id)
            today = date.today()
            for period in periods:
                result = RoomAllocatorService.allocate_period(
                    semester_id=semester_id,
                    period_definition_id=period.pk,
                    overflow_date=today,
                )
                all_violations.extend(result['violations'])
                overflow_count += len(result['overflow'])

            # ── Step 4: Push violation notifications (Item 8) ───────────────
            if all_violations:
                TimetableViolationNotifier.notify(all_violations, semester_id)

            return Response(
                {
                    'lab_rotation_created': lab_rotation_created,
                    'entries_created': entries_created,
                    'overflow_count': overflow_count,
                    'violations': all_violations,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f"Pipeline failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ===========================================================================
# Item 6 — Timetable PDF Export
# ===========================================================================

class TimetableExportView(APIView):
    """
    GET /timetable/export/?section_id=<int>&semester_id=<int>

    Returns the section's weekly timetable as a downloadable PDF file
    generated by ReportLab (pure Python, no WeasyPrint).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        section_id  = request.query_params.get('section_id')
        semester_id = request.query_params.get('semester_id')

        if not section_id or not semester_id:
            return Response(
                {'error': 'section_id and semester_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            section_id  = int(section_id)
            semester_id = int(semester_id)
        except (TypeError, ValueError):
            return Response(
                {'error': 'section_id and semester_id must be integers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from timetable.services import TimetableExportService
        from core.models import Section

        try:
            section = Section.objects.select_related('course').get(pk=section_id)
        except Section.DoesNotExist:
            return Response({'error': 'Section not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            pdf_bytes = TimetableExportService.generate_pdf(
                section_id=section_id,
                semester_id=semester_id,
            )
        except ImportError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response(
                {'error': f"PDF generation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        import io
        filename = f"timetable_{section.name.replace(' ', '_')}.pdf"
        response = FileResponse(
            io.BytesIO(pdf_bytes),
            content_type='application/pdf',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ===========================================================================
# Item 7 — Configuration-Driven Period Generation
# ===========================================================================

class GeneratePeriodsView(APIView):
    """
    POST /timetable/generate-periods/

    Calls generate_periods_for_config() for a given TimetableConfiguration.

    Request body:
        { "timetable_config_id": <int> }

    Response:
        { "periods_created": int, "semester_id": int }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        config_id = request.data.get('timetable_config_id')
        if not config_id:
            return Response(
                {'error': 'timetable_config_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            config_id = int(config_id)
        except (TypeError, ValueError):
            return Response(
                {'error': 'timetable_config_id must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from configuration.timetable.models import TimetableConfiguration
        from timetable.utils import generate_periods_for_config

        try:
            config = TimetableConfiguration.objects.select_related('semester').get(pk=config_id)
        except TimetableConfiguration.DoesNotExist:
            return Response(
                {'error': f'TimetableConfiguration {config_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            created_periods = generate_periods_for_config(config)
            return Response(
                {
                    'periods_created': len(created_periods),
                    'semester_id': config.semester_id,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {'error': f"Period generation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ===========================================================================
# SectionSubjectRequirement — List / Create / Bulk-upsert / Detail
# ===========================================================================

class SectionSubjectRequirementListCreateView(APIView):
    """
    GET  /timetable/requirements/?section_id=&semester_id=
         List all requirements for a section+semester.

    POST /timetable/requirements/
         Create a single requirement.
         Body: { section_id, semester_id, subject_id, faculty_id (opt), periods_per_week }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        section_id  = request.query_params.get('section_id')
        semester_id = request.query_params.get('semester_id')

        qs = SectionSubjectRequirement.objects.select_related(
            'section', 'semester', 'subject', 'faculty'
        )
        if section_id:
            qs = qs.filter(section_id=section_id)
        if semester_id:
            qs = qs.filter(semester_id=semester_id)

        serializer = SectionSubjectRequirementSerializer(qs.order_by('subject__code'), many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = SectionSubjectRequirementSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SectionSubjectRequirementDetailView(APIView):
    """
    GET    /timetable/requirements/<id>/  — retrieve
    PATCH  /timetable/requirements/<id>/  — partial update (periods_per_week, faculty)
    DELETE /timetable/requirements/<id>/  — remove
    """
    permission_classes = [IsAuthenticated]

    def _get_object(self, pk):
        try:
            return SectionSubjectRequirement.objects.select_related(
                'section', 'semester', 'subject', 'faculty'
            ).get(pk=pk)
        except SectionSubjectRequirement.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_object(pk)
        if obj is None:
            return Response({'error': f'Requirement {pk} not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SectionSubjectRequirementSerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get_object(pk)
        if obj is None:
            return Response({'error': f'Requirement {pk} not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SectionSubjectRequirementSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if obj is None:
            return Response({'error': f'Requirement {pk} not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SectionSubjectRequirementBulkCreateView(APIView):
    """
    POST /timetable/requirements/bulk/

    Upsert all subject requirements for one section+semester in a single call.
    Idempotent: existing rows are updated, new rows are created.

    Request body:
    {
        "section_id":  <int>,
        "semester_id": <int>,
        "requirements": [
            { "subject_id": 1, "faculty_id": 5, "periods_per_week": 3 },
            { "subject_id": 2, "faculty_id": 7, "periods_per_week": 2 }
        ]
    }

    Response:
    {
        "created": <int>,
        "updated": <int>,
        "ids": [<int>, ...]
    }
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = SectionSubjectRequirementBulkSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        section_id   = serializer.validated_data['section_id']
        semester_id  = serializer.validated_data['semester_id']
        requirements = serializer.validated_data['requirements']

        created_count = 0
        updated_count = 0
        result_ids: list[int] = []

        for item in requirements:
            obj, created = SectionSubjectRequirement.objects.update_or_create(
                section_id=section_id,
                semester_id=semester_id,
                subject_id=item['subject_id'],
                defaults={
                    'faculty_id':       item.get('faculty_id'),
                    'periods_per_week': item.get('periods_per_week', 1),
                },
            )
            result_ids.append(obj.pk)
            if created:
                created_count += 1
            else:
                updated_count += 1

        return Response(
            {
                'created': created_count,
                'updated': updated_count,
                'ids': result_ids,
            },
            status=status.HTTP_201_CREATED,
        )


# ===========================================================================
# RoomMaintenanceBlock — List / Create / Detail / Reschedule trigger
# ===========================================================================

class RoomMaintenanceBlockListCreateView(APIView):
    """
    GET  /timetable/maintenance/?room_id=&is_active=
         List maintenance blocks, optionally filtered.

    POST /timetable/maintenance/
         Create a new block.
         Body: { room_id, start_date, end_date, reason, is_active (opt) }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = RoomMaintenanceBlock.objects.select_related('room')
        room_id   = request.query_params.get('room_id')
        is_active = request.query_params.get('is_active')

        if room_id:
            qs = qs.filter(room_id=room_id)
        if is_active is not None:
            # Accept "true"/"false" as strings
            qs = qs.filter(is_active=(is_active.lower() == 'true'))

        serializer = RoomMaintenanceBlockSerializer(qs.order_by('-start_date'), many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = RoomMaintenanceBlockSerializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save()
            return Response(
                RoomMaintenanceBlockSerializer(obj).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RoomMaintenanceBlockDetailView(APIView):
    """
    GET    /timetable/maintenance/<id>/  — retrieve
    PATCH  /timetable/maintenance/<id>/  — update dates / reason / is_active
    DELETE /timetable/maintenance/<id>/  — remove
    """
    permission_classes = [IsAuthenticated]

    def _get_object(self, pk):
        try:
            return RoomMaintenanceBlock.objects.select_related('room').get(pk=pk)
        except RoomMaintenanceBlock.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_object(pk)
        if obj is None:
            return Response({'error': f'Maintenance block {pk} not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RoomMaintenanceBlockSerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get_object(pk)
        if obj is None:
            return Response({'error': f'Maintenance block {pk} not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RoomMaintenanceBlockSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if obj is None:
            return Response({'error': f'Maintenance block {pk} not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RescheduleMaintenanceView(APIView):
    """
    POST /timetable/maintenance/<id>/reschedule/

    Triggers RescheduleService for the given maintenance block immediately
    via the API (mirrors the admin trigger_reschedule action).

    Response:
    {
        "entries_nullified":   <int>,
        "periods_reallocated": <int>,
        "new_overflow_count":  <int>,
        "violations":          [str, ...]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            block = RoomMaintenanceBlock.objects.select_related('room').get(pk=pk)
        except RoomMaintenanceBlock.DoesNotExist:
            return Response({'error': f'Maintenance block {pk} not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not block.is_active:
            return Response(
                {'error': 'This maintenance block is not active. Activate it first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from timetable.services import RescheduleService
        try:
            summary = RescheduleService.reschedule_affected_periods(
                room_id=block.room_id,
                start_date=block.start_date,
                end_date=block.end_date,
            )
            return Response(summary, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f"Reschedule failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

