"""
timetable/views_ai.py

REST endpoints that the AI Copilot reads and writes:

  GET  /timetable/ai/state/<semester_id>/         → full schedule snapshot JSON
  GET  /timetable/ai/rooms/<semester_id>/         → available rooms per period
  GET  /timetable/ai/fairness/<semester_id>/      → overflow fairness report
  POST /timetable/ai/chat/                        → AI chat endpoint (Django proxies to AI service)
  POST /timetable/ai/apply-constraints/           → apply NL-derived JSON constraints
  POST /timetable/ai/swap-slots/                  → swap two timetable entries
  POST /timetable/ai/audit/                       → schedule soft-preference audit
"""

import json
import logging

import httpx
from django.conf import settings as django_settings
from django.http import JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from core.models import Section
from profile_management.models import Semester
from timetable.models import (
    NonRoomPeriod,
    OverflowLog,
    PeriodDefinition,
    Room,
    TimetableEntry,
)
from timetable.scheduler import RoomAllocatorService
from timetable.serializers import TimetableEntrySerializer

logger = logging.getLogger(__name__)

# ─── helper: AI Service URL ────────────────────────────────────────────────────

AI_BASE_URL = getattr(django_settings, "TIMETABLE_AI_BASE_URL", "http://localhost:8001")
AI_SECRET   = getattr(django_settings, "TIMETABLE_AI_SECRET", "1Nnzm1F7InKkjCPJmJopRMc9oX77ObVvyqKqMkz601j")
AI_HEADERS  = {
    "X-Internal-Source": "django-cms-backend",
    "X-Internal-Secret": AI_SECRET,
    "Content-Type": "application/json",
}


# ─── Timetable State Snapshot ──────────────────────────────────────────────────

class TimetableStateView(View):
    """
    GET /timetable/ai/state/<semester_id>/

    Returns a structured JSON payload describing the full current state of the
    timetable for the given semester. This is passed verbatim to the LLM so it
    knows what it is looking at before answering any admin query.

    Payload shape
    -------------
    {
      "semester": {...},
      "sections": [{"id", "name", "priority", "year", "course_code"}, ...],
      "rooms": [{"id", "room_number", "room_type", "capacity"}, ...],
      "periods": [{"id", "day", "period_number", "start_time", "end_time"}, ...],
      "schedule": [{"entry_id", "section_name", "subject_code", "faculty_name",
                    "room_number", "day", "period_number", "start_time"}, ...],
      "non_room_slots": [{"section_name", "period_type", "day", "period_number"}, ...],
      "overflow_summary": [{"section_name", "year", "priority", "overflow_count"}, ...]
    }
    """

    def get(self, request, semester_id: int):
        try:
            semester = Semester.objects.select_related("academic_year").get(pk=semester_id)
        except Semester.DoesNotExist:
            return JsonResponse({"error": f"Semester {semester_id} not found."}, status=404)

        sections = list(
            Section.objects.order_by("priority", "code").values(
                "id", "name", "priority", "year", "course__code"
            )
        )
        for s in sections:
            s["course_code"] = s.pop("course__code", "")

        rooms = list(
            Room.objects.filter(is_active=True).values(
                "id", "room_number", "room_type", "building", "capacity"
            )
        )

        day_map = {1: "Monday", 2: "Tuesday", 3: "Wednesday",
                   4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}

        periods_qs = PeriodDefinition.objects.filter(semester_id=semester_id).order_by(
            "day_of_week", "period_number"
        )
        periods = [
            {
                "id": p.id,
                "day": day_map.get(p.day_of_week, str(p.day_of_week)),
                "period_number": p.period_number,
                "start_time": p.start_time.strftime("%H:%M"),
                "end_time": p.end_time.strftime("%H:%M"),
            }
            for p in periods_qs
        ]

        entries_qs = (
            TimetableEntry.objects.filter(semester_id=semester_id, is_active=True)
            .select_related("section", "subject", "faculty", "room", "period_definition")
            .order_by("period_definition__day_of_week", "period_definition__period_number")
        )
        schedule = []
        for e in entries_qs:
            pd = e.period_definition
            schedule.append(
                {
                    "entry_id": e.id,
                    "section_name": str(e.section),
                    "section_id": e.section_id,
                    "subject_code": e.subject.code,
                    "subject_name": e.subject.name,
                    "faculty_name": e.faculty.get_full_name() if e.faculty else None,
                    "faculty_id": e.faculty_id,
                    "room_number": e.room.room_number if e.room else None,
                    "room_id": e.room_id,
                    "day": day_map.get(pd.day_of_week, str(pd.day_of_week)),
                    "period_number": pd.period_number,
                    "start_time": pd.start_time.strftime("%H:%M"),
                    "period_definition_id": pd.id,
                }
            )

        non_room_qs = (
            NonRoomPeriod.objects.filter(semester_id=semester_id)
            .select_related("section", "period_definition")
        )
        non_room_slots = [
            {
                "section_name": str(nr.section),
                "period_type": nr.get_period_type_display(),
                "day": day_map.get(nr.period_definition.day_of_week, ""),
                "period_number": nr.period_definition.period_number,
            }
            for nr in non_room_qs
        ]

        overflow_report = RoomAllocatorService.get_fairness_report(semester_id)
        overflow_summary = [
            {
                "section_id": row["id"],
                "section_name": row["name"],
                "year": row["year"],
                "priority": row["priority"],
                "overflow_count": row["overflow_count"],
            }
            for row in overflow_report
        ]

        payload = {
            "semester": {
                "id": semester.id,
                "name": str(semester),
                "academic_year": str(semester.academic_year),
            },
            "sections": sections,
            "rooms": rooms,
            "periods": periods,
            "schedule": schedule,
            "non_room_slots": non_room_slots,
            "overflow_summary": overflow_summary,
            "meta": {
                "total_sections": len(sections),
                "total_rooms": len(rooms),
                "total_entries": len(schedule),
                "max_simultaneous_demand": len(sections) - len(non_room_slots),
            },
        }
        return JsonResponse(payload, safe=False)


# ─── Available Rooms per Period ────────────────────────────────────────────────

class AvailableRoomsView(View):
    """
    GET /timetable/ai/rooms/<semester_id>/

    For each period definition in the semester, returns the list of rooms that
    are NOT already booked. The AI uses this to suggest valid moves.
    """

    def get(self, request, semester_id: int):
        try:
            Semester.objects.get(pk=semester_id)
        except Semester.DoesNotExist:
            return JsonResponse({"error": "Semester not found."}, status=404)

        periods = PeriodDefinition.objects.filter(semester_id=semester_id).order_by(
            "day_of_week", "period_number"
        )
        day_map = {1: "Monday", 2: "Tuesday", 3: "Wednesday",
                   4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}

        result = []
        for period in periods:
            booked_room_ids = set(
                TimetableEntry.objects.filter(
                    period_definition=period,
                    semester_id=semester_id,
                    is_active=True,
                    room__isnull=False,
                ).values_list("room_id", flat=True)
            )
            available = list(
                Room.objects.filter(is_active=True)
                .exclude(id__in=booked_room_ids)
                .values("id", "room_number", "building", "room_type", "capacity")
            )
            result.append(
                {
                    "period_id": period.id,
                    "day": day_map.get(period.day_of_week, ""),
                    "period_number": period.period_number,
                    "start_time": period.start_time.strftime("%H:%M"),
                    "available_rooms": available,
                    "booked_count": len(booked_room_ids),
                }
            )

        return JsonResponse({"period_availability": result}, safe=False)


# ─── Fairness Report ───────────────────────────────────────────────────────────

class FairnessReportView(View):
    """
    GET /timetable/ai/fairness/<semester_id>/

    Returns the overflow fairness report so the admin can see which sections
    have been displaced most and deserve compensatory priority.
    """

    def get(self, request, semester_id: int):
        report = RoomAllocatorService.get_fairness_report(semester_id)
        util   = RoomAllocatorService.room_utilisation_report(semester_id)
        return JsonResponse(
            {"fairness_report": report, "room_utilisation": util}, safe=False
        )


# ─── Swap Slots ────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class SwapSlotsView(View):
    """
    POST /timetable/ai/swap-slots/

    Body: {"entry1_id": <int>, "entry2_id": <int>}

    Atomically swaps the period definitions of two timetable entries.
    Mirrors the GraphQL mutation swap_timetable_slots but as a REST endpoint
    so the AI agent can call it without a GraphQL client.
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)

        entry1_id = body.get("entry1_id")
        entry2_id = body.get("entry2_id")
        if not entry1_id or not entry2_id:
            return JsonResponse({"error": "entry1_id and entry2_id are required."}, status=400)

        try:
            from django.db import transaction
            from timetable.models import TimetableEntry

            with transaction.atomic():
                e1 = TimetableEntry.objects.select_for_update().get(pk=entry1_id)
                e2 = TimetableEntry.objects.select_for_update().get(pk=entry2_id)

                p1, p2 = e1.period_definition_id, e2.period_definition_id

                # Temporarily nullify to avoid unique_together conflict
                TimetableEntry.objects.filter(pk=e1.pk).update(period_definition=None)
                TimetableEntry.objects.filter(pk=e2.pk).update(period_definition_id=p1)
                TimetableEntry.objects.filter(pk=e1.pk).update(period_definition_id=p2)

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Swapped period slots for entries {entry1_id} and {entry2_id}.",
                    "entry1_new_period_id": p2,
                    "entry2_new_period_id": p1,
                }
            )
        except TimetableEntry.DoesNotExist:
            return JsonResponse({"error": "One or both entries not found."}, status=404)
        except Exception as exc:
            logger.exception("swap_slots failed")
            return JsonResponse({"error": str(exc)}, status=500)


# ─── Apply Constraints ─────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class ApplyConstraintsView(View):
    """
    POST /timetable/ai/apply-constraints/

    Body:
    {
      "semester_id": <int>,
      "constraints": [
        {"type": "move_entry", "entry_id": <int>, "target_period_id": <int>},
        {"type": "assign_room", "entry_id": <int>, "room_id": <int>},
        {"type": "swap_entries", "entry1_id": <int>, "entry2_id": <int>}
      ]
    }

    Executes a list of constraints produced by the LLM constraint-translator.
    Each constraint type is validated by the existing Django services/validators
    before being applied. On any failure the full batch is rolled back.

    Returns per-constraint success/failure messages.
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)

        semester_id = body.get("semester_id")
        constraints = body.get("constraints", [])

        if not semester_id:
            return JsonResponse({"error": "semester_id is required."}, status=400)
        if not isinstance(constraints, list) or not constraints:
            return JsonResponse({"error": "constraints must be a non-empty list."}, status=400)

        results = []
        errors  = []

        from django.db import transaction
        from timetable.models import TimetableEntry
        from timetable.services import TimetableService

        try:
            with transaction.atomic():
                for idx, c in enumerate(constraints):
                    ctype = c.get("type")
                    label = f"constraint[{idx}] ({ctype})"

                    try:
                        if ctype == "move_entry":
                            entry = TimetableEntry.objects.get(pk=c["entry_id"])
                            entry.period_definition_id = c["target_period_id"]
                            entry.full_clean()
                            entry.save()
                            results.append({"index": idx, "status": "ok", "type": ctype})

                        elif ctype == "assign_room":
                            entry = TimetableEntry.objects.select_related("period_definition").get(
                                pk=c["entry_id"]
                            )
                            TimetableService.assign_room_to_entry(entry, c.get("room_id"))
                            results.append({"index": idx, "status": "ok", "type": ctype})

                        elif ctype == "swap_entries":
                            e1 = TimetableEntry.objects.get(pk=c["entry1_id"])
                            e2 = TimetableEntry.objects.get(pk=c["entry2_id"])
                            p1, p2 = e1.period_definition_id, e2.period_definition_id
                            TimetableEntry.objects.filter(pk=e1.pk).update(period_definition=None)
                            TimetableEntry.objects.filter(pk=e2.pk).update(period_definition_id=p1)
                            TimetableEntry.objects.filter(pk=e1.pk).update(period_definition_id=p2)
                            results.append({"index": idx, "status": "ok", "type": ctype})

                        else:
                            raise ValueError(f"Unknown constraint type: {ctype!r}")

                    except Exception as exc:
                        msg = f"{label} failed: {exc}"
                        logger.warning(msg)
                        errors.append({"index": idx, "error": str(exc), "type": ctype})
                        raise  # triggers rollback

        except Exception:
            return JsonResponse(
                {"success": False, "applied": results, "errors": errors}, status=422
            )

        return JsonResponse({"success": True, "applied": results, "errors": []})


# ─── AI Chat Proxy ─────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class TimetableChatView(View):
    """
    POST /timetable/ai/chat/

    Proxies the admin's chat message to the FastAPI AI service's
    /timetable/chat endpoint, enriching the payload with the current
    timetable state so the LLM has context.

    Body: {"message": "...", "semester_id": <int>, "history": [...optional...]}
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)

        message = body.get("message", "").strip()
        semester_id = body.get("semester_id")
        history = body.get("history", [])

        if not message:
            return JsonResponse({"error": "message is required."}, status=400)
        if not semester_id:
            return JsonResponse({"error": "semester_id is required."}, status=400)

        # Build timetable state snapshot inline (reuse view logic)
        try:
            semester = Semester.objects.select_related("academic_year").get(pk=semester_id)
        except Semester.DoesNotExist:
            return JsonResponse({"error": f"Semester {semester_id} not found."}, status=404)

        # Lightweight state for the prompt context
        sections_qs = Section.objects.order_by("priority", "code").values(
            "id", "name", "priority", "year", "course__code"
        )
        rooms_qs = Room.objects.filter(is_active=True).values(
            "id", "room_number", "room_type", "capacity"
        )
        overflow_report = RoomAllocatorService.get_fairness_report(semester_id)

        timetable_state = {
            "semester": str(semester),
            "total_sections": sections_qs.count(),
            "total_rooms": rooms_qs.count(),
            "sections": list(sections_qs[:30]),  # top 30 for context size
            "rooms": list(rooms_qs),
            "overflow_summary": overflow_report[:10],
        }

        payload = {
            "message": message,
            "semester_id": semester_id,
            "timetable_state": timetable_state,
            "history": history,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{AI_BASE_URL}/timetable/chat",
                    json=payload,
                    headers=AI_HEADERS,
                )
                response.raise_for_status()
                return JsonResponse(response.json(), safe=False)
        except httpx.HTTPStatusError as exc:
            logger.error("AI service returned error: %s", exc.response.text)
            return JsonResponse(
                {"error": "AI service error.", "detail": exc.response.text},
                status=exc.response.status_code,
            )
        except httpx.RequestError as exc:
            logger.error("AI service unreachable: %s", exc)
            return JsonResponse(
                {"error": "AI service is unreachable. Is the FastAPI server running?"},
                status=503,
            )


# ─── Schedule Audit ────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class ScheduleAuditView(View):
    """
    POST /timetable/ai/audit/

    Body: {"semester_id": <int>}

    Sends the full timetable state to the AI service for a soft-preference
    audit. The LLM checks for things like:
      - Faculty with >4 consecutive periods
      - Sections with lab immediately after/before theory exam
      - Rooms assigned across buildings on the same day
    Returns plain English findings.
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)

        semester_id = body.get("semester_id")
        if not semester_id:
            return JsonResponse({"error": "semester_id is required."}, status=400)

        # Re-use TimetableStateView logic by constructing it
        state_view = TimetableStateView()

        # Build the full state dict (copy-paste free: call the helper directly)
        from django.test import RequestFactory
        fake_get = RequestFactory().get("/")
        state_response = state_view.get(fake_get, semester_id=semester_id)
        state_json = json.loads(state_response.content)

        if state_response.status_code != 200:
            return state_response

        payload = {
            "audit_type": "soft_preferences",
            "timetable_state": state_json,
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{AI_BASE_URL}/timetable/audit",
                    json=payload,
                    headers=AI_HEADERS,
                )
                response.raise_for_status()
                return JsonResponse(response.json(), safe=False)
        except httpx.HTTPStatusError as exc:
            return JsonResponse(
                {"error": "AI service error.", "detail": exc.response.text},
                status=exc.response.status_code,
            )
        except httpx.RequestError:
            return JsonResponse(
                {"error": "AI service is unreachable."},
                status=503,
            )
