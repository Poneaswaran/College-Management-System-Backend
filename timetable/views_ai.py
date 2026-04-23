"""
timetable/views_ai.py

REST endpoints that the AI Copilot reads and writes:

  GET  /timetable/ai/state/<semester_id>/         → full schedule snapshot JSON
  GET  /timetable/ai/rooms/<semester_id>/         → available rooms per period
  GET  /timetable/ai/fairness/<semester_id>/      → overflow fairness report
  POST /timetable/ai/chat/                        → AI chat endpoint (Django proxies to AI service)
  POST /timetable/ai/apply-constraints/           → apply NL-derived JSON constraints (saves snapshot)
  POST /timetable/ai/undo/<action_id>/            → undo a previous AI action batch
  GET  /timetable/ai/snapshots/<semester_id>/     → list recent AI action snapshots
  POST /timetable/ai/swap-slots/                  → swap two timetable entries
  POST /timetable/ai/audit/                       → schedule soft-preference audit
  POST /timetable/ai/explain-why-not/             → explain why a section/room conflict exists
"""

import json
import logging

import httpx
from django.conf import settings as django_settings
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from core.models import Section
from profile_management.models import Semester
from timetable.models import (
    AIActionSnapshot,
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


def get_user_context(request):
    """
    Builds a standard context object from the authenticated user
    for the AI service to use in RAG filtering and memory scoping.
    """
    user = request.user
    role_code = "GUEST"
    department_id = None
    
    if user.is_authenticated:
        if hasattr(user, "role") and user.role:
            role_code = user.role.code
        if hasattr(user, "department") and user.department:
            department_id = user.department.id
            
    # Tenant identification for multi-tenant support
    tenant_id = None
    tenant = getattr(request, "tenant", None)
    if tenant and hasattr(tenant, "id"):
        tenant_id = tenant.id
        
    return {
        "role": role_code,
        "department_id": str(department_id) if department_id else None,
        "tenant_id": str(tenant_id) if tenant_id else None
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
        {"type": "move_entry",   "entry_id": <int>, "target_period_id": <int>},
        {"type": "assign_room",  "entry_id": <int>, "room_id": <int>},
        {"type": "swap_entries", "entry1_id": <int>, "entry2_id": <int>}
      ]
    }

    Workflow
    --------
    1. Collect all TimetableEntry PKs that would be touched by the constraint batch.
    2. Snapshot their current state (period_definition_id, room_id, allocation_id)
       into AIActionSnapshot BEFORE applying anything.
    3. Apply all constraints atomically — any failure rolls the whole batch back.
    4. Return the snapshot's action_id so the UI can offer an "Undo" button.
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _collect_affected_pks(constraints: list) -> list[int]:
        """Return the set of TimetableEntry PKs that will be modified."""
        pks: list[int] = []
        for c in constraints:
            ctype = c.get("type")
            if ctype in ("move_entry", "assign_room"):
                pk = c.get("entry_id")
                if pk:
                    pks.append(int(pk))
            elif ctype == "swap_entries":
                for key in ("entry1_id", "entry2_id"):
                    pk = c.get(key)
                    if pk:
                        pks.append(int(pk))
        return list(set(pks))

    @staticmethod
    def _build_snapshot(pks: list[int]) -> list[dict]:
        """Fetch current state of each entry and return as a serialisable list."""
        rows = []
        for entry in TimetableEntry.objects.filter(pk__in=pks).select_related(
            "section", "subject", "faculty", "room", "period_definition"
        ):
            rows.append(
                {
                    "entry_id": entry.pk,
                    "section_id": entry.section_id,
                    "subject_id": entry.subject_id,
                    "faculty_id": entry.faculty_id,
                    "period_definition_id": entry.period_definition_id,
                    "room_id": entry.room_id,
                    "allocation_id": entry.allocation_id,
                    "notes": entry.notes,
                    # Human-readable labels for the UI
                    "section_name": str(entry.section),
                    "subject_code": entry.subject.code,
                    "room_number": entry.room.room_number if entry.room else None,
                    "period_label": str(entry.period_definition),
                }
            )
        return rows

    # ── main handler ─────────────────────────────────────────────────────────

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

        # ── Step 1: Snapshot BEFORE applying ─────────────────────────────────
        affected_pks = self._collect_affected_pks(constraints)
        snapshot_rows = self._build_snapshot(affected_pks)

        # Save the snapshot in its own transaction so it always commits,
        # even if the apply transaction below rolls back.
        from django.db import transaction
        from timetable.services import TimetableService

        snapshot_obj = None
        try:
            with transaction.atomic():
                snapshot_obj = AIActionSnapshot.objects.create(
                    semester_id=semester_id,
                    snapshot_data=snapshot_rows,
                    constraints_applied=constraints,
                )
        except Exception as exc:
            logger.error("Failed to save AI action snapshot: %s", exc)
            # Non-fatal: proceed without undo capability

        # ── Step 2: Apply constraints atomically ──────────────────────────────
        results: list[dict] = []
        errors:  list[dict] = []

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
                            entry = TimetableEntry.objects.select_related(
                                "period_definition"
                            ).get(pk=c["entry_id"])
                            TimetableService.assign_room_to_entry(entry, c.get("room_id"))
                            results.append({"index": idx, "status": "ok", "type": ctype})

                        elif ctype == "swap_entries":
                            e1 = TimetableEntry.objects.get(pk=c["entry1_id"])
                            e2 = TimetableEntry.objects.get(pk=c["entry2_id"])
                            p1, p2 = e1.period_definition_id, e2.period_definition_id
                            TimetableEntry.objects.filter(pk=e1.pk).update(
                                period_definition=None
                            )
                            TimetableEntry.objects.filter(pk=e2.pk).update(
                                period_definition_id=p1
                            )
                            TimetableEntry.objects.filter(pk=e1.pk).update(
                                period_definition_id=p2
                            )
                            results.append({"index": idx, "status": "ok", "type": ctype})

                        else:
                            raise ValueError(f"Unknown constraint type: {ctype!r}")

                    except Exception as exc:
                        msg = f"{label} failed: {exc}"
                        logger.warning(msg)
                        errors.append({"index": idx, "error": str(exc), "type": ctype})
                        raise  # triggers rollback

        except Exception:
            # If apply failed, mark the snapshot as 'reverted' so the UI
            # knows there is nothing to undo (constraints were never applied).
            if snapshot_obj is not None:
                try:
                    snapshot_obj.reverted = True
                    snapshot_obj.reverted_at = timezone.now()
                    snapshot_obj.save(update_fields=["reverted", "reverted_at"])
                except Exception:
                    pass
            return JsonResponse(
                {"success": False, "applied": results, "errors": errors}, status=422
            )

        return JsonResponse(
            {
                "success": True,
                "applied": results,
                "errors": [],
                "action_id": str(snapshot_obj.action_id) if snapshot_obj else None,
                "undo_url": (
                    f"/timetable/ai/undo/{snapshot_obj.action_id}/"
                    if snapshot_obj else None
                ),
            }
        )


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
            "user_context": get_user_context(request),
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
            "user_context": get_user_context(request),
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


# ─── Undo Last AI Action ───────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class UndoAIActionView(View):
    """
    POST /timetable/ai/undo/<action_id>/

    Reverts the TimetableEntry rows affected by a previous AI constraint batch
    back to their state as of the AIActionSnapshot identified by action_id.

    Workflow
    --------
    1. Look up the AIActionSnapshot by action_id (UUID).
    2. Verify it hasn't already been reverted.
    3. Inside a single atomic transaction, restore each entry's
       period_definition_id, room_id, and allocation_id to the snapshot values.
    4. Mark the snapshot as reverted so it cannot be undone twice.
    5. Return a summary of restored entries.

    The undo is intentionally shallow: it restores period slot and room
    assignments. If the original action also modified a ResourceAllocation
    record via assign_room_to_entry, the release/re-allocation is handled
    by setting allocation_id directly from the snapshot (sufficient for
    the common swap/move case).
    """

    def post(self, request, action_id: str):
        try:
            snapshot = AIActionSnapshot.objects.select_related("semester").get(
                action_id=action_id
            )
        except AIActionSnapshot.DoesNotExist:
            return JsonResponse(
                {"error": f"No AI action snapshot found with id {action_id}."},
                status=404,
            )
        except Exception:
            return JsonResponse({"error": "Invalid action_id format."}, status=400)

        if snapshot.reverted:
            return JsonResponse(
                {
                    "error": "This AI action has already been undone.",
                    "reverted_at": snapshot.reverted_at.isoformat()
                    if snapshot.reverted_at
                    else None,
                },
                status=409,
            )

        from django.db import transaction

        restored: list[dict] = []
        errors:   list[dict] = []

        try:
            with transaction.atomic():
                for row in snapshot.snapshot_data:
                    entry_id = row["entry_id"]
                    try:
                        entry = TimetableEntry.objects.select_for_update().get(pk=entry_id)
                        entry.period_definition_id = row["period_definition_id"]
                        entry.room_id              = row["room_id"]
                        entry.allocation_id        = row["allocation_id"]
                        entry.notes               = row.get("notes", entry.notes)
                        # Use update() to skip full_clean (snapshot was valid state)
                        TimetableEntry.objects.filter(pk=entry_id).update(
                            period_definition_id=row["period_definition_id"],
                            room_id=row["room_id"],
                            allocation_id=row["allocation_id"],
                        )
                        restored.append(
                            {
                                "entry_id": entry_id,
                                "section_name": row.get("section_name"),
                                "restored_period_id": row["period_definition_id"],
                                "restored_room_id": row["room_id"],
                            }
                        )
                    except TimetableEntry.DoesNotExist:
                        errors.append(
                            {
                                "entry_id": entry_id,
                                "error": "Entry no longer exists — may have been deleted.",
                            }
                        )
                    except Exception as exc:
                        errors.append({"entry_id": entry_id, "error": str(exc)})
                        raise  # rollback

                # Mark snapshot as reverted
                snapshot.reverted    = True
                snapshot.reverted_at = timezone.now()
                snapshot.save(update_fields=["reverted", "reverted_at"])

        except Exception:
            return JsonResponse(
                {
                    "success": False,
                    "restored": restored,
                    "errors": errors,
                    "message": "Undo failed and was rolled back.",
                },
                status=422,
            )

        return JsonResponse(
            {
                "success": True,
                "action_id": str(snapshot.action_id),
                "entries_restored": len(restored),
                "restored": restored,
                "errors": errors,
                "message": (
                    f"Successfully reverted {len(restored)} entry/entries to their "
                    f"pre-AI-action state."
                ),
            }
        )


# ─── AI Action Snapshot List ───────────────────────────────────────────────────

class AIActionSnapshotListView(View):
    """
    GET /timetable/ai/snapshots/<semester_id>/

    Returns recent AI action snapshots for the given semester so the UI can
    display a history panel with each action's summary and an "Undo" button
    for those that haven't been reverted yet.

    Query params
    ------------
    limit  : max number of snapshots to return (default 20, max 100)
    """

    def get(self, request, semester_id: int):
        limit = min(int(request.GET.get("limit", 20)), 100)

        snapshots_qs = (
            AIActionSnapshot.objects.filter(semester_id=semester_id)
            .order_by("-applied_at")[:limit]
        )

        data = []
        for s in snapshots_qs:
            constraints = s.constraints_applied or []
            affected_sections = list(
                {row.get("section_name") for row in s.snapshot_data if row.get("section_name")}
            )
            data.append(
                {
                    "action_id": str(s.action_id),
                    "applied_at": s.applied_at.isoformat(),
                    "reverted": s.reverted,
                    "reverted_at": s.reverted_at.isoformat() if s.reverted_at else None,
                    "constraint_count": len(constraints),
                    "affected_sections": affected_sections,
                    "constraint_types": list({c.get("type") for c in constraints}),
                    "undo_url": (
                        f"/timetable/ai/undo/{s.action_id}/"
                        if not s.reverted else None
                    ),
                }
            )

        return JsonResponse(
            {"semester_id": semester_id, "snapshots": data, "count": len(data)},
            safe=False,
        )


# ─── Explain Why Not ───────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class ExplainWhyNotView(View):
    """
    POST /timetable/ai/explain-why-not/

    Answers diagnostic negative-space questions like:
      "Why couldn't Section CSE-4A get Room P3 on Monday?"
      "Why is Dr. Smith scheduled against CSE-3B on Wednesday P5?"

    The key difference from the regular chat endpoint: this view enriches the
    payload with the FULL timetable state (not the lightweight chat context)
    and adds pre-computed diagnostic facts about the requested room/period so
    the LLM doesn't have to guess — it reasons on structured data.

    Body:
    {
      "message":  "Why couldn't Section CSE-4A get Room 101 on Monday P3?",
      "semester_id": <int>,
      "history": [...optional multi-turn...],
      // Optional structured hints — Django computes these automatically:
      "section_name": "CSE-4A",            // optional
      "room_number":  "101",               // optional
      "day":          "Monday",            // optional
      "period_number": 3                   // optional
    }
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)

        message     = body.get("message", "").strip()
        semester_id = body.get("semester_id")
        history     = body.get("history", [])

        if not message:
            return JsonResponse({"error": "message is required."}, status=400)
        if not semester_id:
            return JsonResponse({"error": "semester_id is required."}, status=400)

        try:
            semester = Semester.objects.select_related("academic_year").get(pk=semester_id)
        except Semester.DoesNotExist:
            return JsonResponse({"error": f"Semester {semester_id} not found."}, status=404)

        # Build FULL timetable state (not the lightweight chat version)
        from django.test import RequestFactory
        state_view = TimetableStateView()
        fake_get = RequestFactory().get("/")
        state_response = state_view.get(fake_get, semester_id=semester_id)
        timetable_state = json.loads(state_response.content)
        if state_response.status_code != 200:
            return state_response

        # ── Compute structured diagnostic facts ──────────────────────────────
        # Try to extract the room and period from optional params or body text.
        section_name  = body.get("section_name")
        room_number   = body.get("room_number")
        day_hint      = body.get("day")
        period_number = body.get("period_number")

        diagnostic_context: dict = {}

        day_map = {1: "Monday", 2: "Tuesday", 3: "Wednesday",
                   4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}

        if room_number:
            # Find every entry occupying this room in the semester
            room_occupants = []
            try:
                room_obj = Room.objects.get(room_number=room_number, is_active=True)
                entries = (
                    TimetableEntry.objects
                    .filter(room=room_obj, semester_id=semester_id, is_active=True)
                    .select_related("section", "subject", "faculty", "period_definition")
                )
                for e in entries:
                    pd = e.period_definition
                    room_occupants.append({
                        "day": day_map.get(pd.day_of_week, str(pd.day_of_week)),
                        "period_number": pd.period_number,
                        "section_name": str(e.section),
                        "faculty_name": e.faculty.get_full_name() if e.faculty else None,
                        "subject_code": e.subject.code,
                    })
                diagnostic_context["room_occupancy"] = {
                    "room_number": room_number,
                    "capacity": room_obj.capacity,
                    "room_type": room_obj.room_type,
                    "all_bookings_this_semester": room_occupants,
                }
            except Room.DoesNotExist:
                diagnostic_context["room_not_found"] = room_number

        if section_name:
            # Find all entries for this section
            section_schedule = []
            for entry in timetable_state.get("schedule", []):
                if entry.get("section_name") == section_name:
                    section_schedule.append(entry)
            diagnostic_context["section_schedule"] = {
                "section_name": section_name,
                "current_entries": section_schedule,
                "overflow_info": next(
                    (
                        o for o in timetable_state.get("overflow_summary", [])
                        if o.get("section_name") == section_name
                    ),
                    None,
                ),
            }

        payload = {
            "message": message,
            "semester_id": semester_id,
            "timetable_state": timetable_state,
            "diagnostic_context": diagnostic_context,
            "history": history,
            "user_context": get_user_context(request),
        }

        try:
            with httpx.Client(timeout=90.0) as client:
                response = client.post(
                    f"{AI_BASE_URL}/timetable/explain-why-not",
                    json=payload,
                    headers=AI_HEADERS,
                )
                response.raise_for_status()
                return JsonResponse(response.json(), safe=False)
        except httpx.HTTPStatusError as exc:
            logger.error("AI explain-why-not error: %s", exc.response.text)
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


# ─── Explain Conflicts (Scheduler Errors) ──────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class ExplainConflictView(View):
    """
    POST /timetable/ai/explain-conflict/

    Translates raw scheduler validation errors into friendly advice.
    Body: {"error": "...", "context": {...}}
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)

        error_msg = body.get("error")
        context = body.get("context", {})

        if not error_msg:
            return JsonResponse({"error": "error message is required."}, status=400)

        # Enforce semester_id from context if available, else find an active one
        semester_id = context.get("semester_id")
        if not semester_id:
            active_semester = Semester.objects.filter(is_active=True).first()
            if active_semester:
                semester_id = active_semester.id

        if not semester_id:
            return JsonResponse({"error": "No active semester found for context."}, status=400)

        # Fetch state for context
        from django.test import RequestFactory
        state_view = TimetableStateView()
        fake_get = RequestFactory().get("/")
        state_response = state_view.get(fake_get, semester_id=semester_id)
        state_json = json.loads(state_response.content)

        payload = {
            "message": error_msg,
            "semester_id": semester_id,
            "timetable_state": state_json,
            "error_messages": [error_msg],
            "user_context": get_user_context(request),
        }

        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(
                    f"{AI_BASE_URL}/timetable/explain-conflicts",
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


# ─── Grid AI Chat Proxy ────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class GridAIChatView(View):
    """
    POST /timetable/admin/ai-chat/
    
    Proxies to the FastAPI AI service endpoint /timetable/grid-chat
    to handle the conversational state machine for grid generation.
    """
    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)

        session_id = body.get("session_id")
        message = body.get("message", "").strip()
        department_id = body.get("department_id")

        if not session_id or not message or not department_id:
            return JsonResponse({"error": "session_id, message, and department_id are required."}, status=400)

        # Get department name for context
        try:
            from core.models import Department
            department = Department.objects.get(pk=department_id)
            department_name = department.name
        except:
            department_name = f"Department {department_id}"

        # Maintain state in Django cache
        from django.core.cache import cache
        cache_key = f"grid_ai_chat_{session_id}"
        session = cache.get(cache_key)

        if not session:
            session = {
                "department_id": department_id,
                "state": "collecting",
                "collected": {
                    "day_start": None,
                    "day_end": None,
                    "lunch_start": None,
                    "lunch_duration_mins": None,
                    "period_duration_mins": None,
                    "num_periods": None,
                    "short_breaks": []
                },
                "history": []
            }

        if session['state'] == 'complete':
            return JsonResponse({"reply": "Configuration already complete.", "state": "complete", "resolved_grid": session.get('resolved_grid')})

        # Add user message to history
        session['history'].append({"role": "user", "parts": [{"text": message}]})

        payload = {
            "message": message,
            "session_id": session_id,
            "department_name": department_name,
            "collected_fields": session["collected"],
            "history": session["history"],
            "user_context": get_user_context(request),
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{AI_BASE_URL}/timetable/grid-chat",
                    json=payload,
                    headers=AI_HEADERS,
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Add assistant reply to history
                reply_text = data.get("reply", "")
                session['history'].append({"role": "model", "parts": [{"text": reply_text}]})
                
                # Update collected fields if AI provided incremental updates
                if data.get("updated_fields"):
                    session['collected'].update(data["updated_fields"])
                
                # Check if it's complete, if so validate the resolved_grid
                if data.get("state") == "complete" and data.get("resolved_grid"):
                    from timetable.grid_serializers import TimetableGridSerializer
                    grid_data = data.get("resolved_grid")
                    grid_data["department"] = department_id
                    
                    if "academic_year" not in grid_data:
                        grid_data["academic_year"] = "2025-26"
                    if "effective_from" not in grid_data:
                        from datetime import date
                        grid_data["effective_from"] = date.today().isoformat()
                        
                    serializer = TimetableGridSerializer(data=grid_data)
                    if not serializer.is_valid():
                        data["reply"] += "\n\nBackend Validation Error: " + json.dumps(serializer.errors)
                        data["state"] = "confirming" 
                        data["resolved_grid"] = None
                        session['state'] = "confirming"
                    else:
                        data["resolved_grid"] = grid_data
                        session['state'] = "complete"
                        session['resolved_grid'] = grid_data
                else:
                    session['state'] = data.get("state", "collecting")
                    
                # Save session back to cache (1 hour expiry)
                cache.set(cache_key, session, timeout=3600)

                return JsonResponse(data, safe=False)
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


