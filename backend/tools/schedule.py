"""Schedule (日程) tools - LLM-callable tools for calendar events.

Eight focused tools that mirror the ScheduleService CRUD surface and are
designed to be the only interface the schedule-assistant subagent needs:

  - create_event    — create a new event
  - list_events     — list events in a time range
  - search_events   — free-text search
  - get_event       — fetch a single event by id
  - get_current_time — time oracle (saves the LLM the local-tz math)
  - update_event    — partial update of an existing event
  - cancel_event    — mark an event as cancelled (reversible)
  - delete_event    — move an event to the recycle bin (recoverable for 30
                      days; the bin is reachable from the schedule UI and
                      via the LLM via list_deleted_events / restore_event)

For destructive operations the subagent is instructed to confirm with the
user first (see ``SCHEDULE_ASSISTANT_SYSTEM_PROMPT``); the tool itself
does not enforce confirmation so the prompt is the single source of truth.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from backend.services.schedule.service import ScheduleService
from backend.tools.base import Tool


def _fmt_event_payload(events: list[Any]) -> str:
    return json.dumps([e.to_dict() for e in events], ensure_ascii=False)


class CreateEventTool(Tool):
    """Create a new calendar event."""

    def __init__(self, schedule_service: ScheduleService):
        self._service = schedule_service

    @property
    def name(self) -> str:
        return "create_event"

    @property
    def description(self) -> str:
        return (
            "Create a new calendar event. Times are absolute milliseconds since "
            "the Unix epoch (UTC). All times are interpreted in the user's local "
            "timezone on the client side. Always pass start_at_ms and end_at_ms. "
            "If the user says 'tomorrow at 3pm', compute that timestamp now and "
            "pass it in."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title for the event (required).",
                    "minLength": 1,
                },
                "start_at_ms": {
                    "type": "integer",
                    "description": (
                        "Event start time in absolute milliseconds since epoch (UTC)."
                    ),
                },
                "end_at_ms": {
                    "type": "integer",
                    "description": (
                        "Event end time in absolute milliseconds since epoch (UTC). "
                        "Must be greater than start_at_ms."
                    ),
                },
                "all_day": {
                    "type": "boolean",
                    "description": "Whether this is an all-day event. Default false.",
                    "default": False,
                },
                "location": {
                    "type": "string",
                    "description": "Optional location string.",
                    "default": "",
                },
                "description": {
                    "type": "string",
                    "description": "Optional longer description / notes.",
                    "default": "",
                },
                "color": {
                    "type": "string",
                    "description": "Optional hex color for the event (e.g. '#4F8EF7').",
                    "default": "#4F8EF7",
                },
            },
            "required": ["title", "start_at_ms", "end_at_ms"],
        }

    async def execute(
        self,
        title: str,
        start_at_ms: int,
        end_at_ms: int,
        all_day: bool = False,
        location: str = "",
        description: str = "",
        color: str = "#4F8EF7",
        **_: Any,
    ) -> str:
        try:
            ev = self._service.create_event(
                title=title,
                start_at_ms=int(start_at_ms),
                end_at_ms=int(end_at_ms),
                all_day=bool(all_day),
                location=location or "",
                description=description or "",
                color=color or "#4F8EF7",
            )
            # Broadcast so any open calendar client refetches in real time.
            # No-op when the service was constructed without a bus.
            await self._service.publish_change("created", ev.id)
            payload = ev.to_dict()
            payload["start_iso"] = _ms_to_iso(ev.start_at_ms)
            payload["end_iso"] = _ms_to_iso(ev.end_at_ms)
            return (
                f"Created event #{ev.id} '{ev.title}' "
                f"from {payload['start_iso']} to {payload['end_iso']}.\n"
                f"JSON: {json.dumps(payload, ensure_ascii=False)}"
            )
        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            logger.exception("create_event failed")
            return f"Error creating event: {e}"


class ListEventsTool(Tool):
    """List calendar events within a time range."""

    def __init__(self, schedule_service: ScheduleService):
        self._service = schedule_service

    @property
    def name(self) -> str:
        return "list_events"

    @property
    def description(self) -> str:
        return (
            "List all calendar events that overlap the given time range. "
            "Times are absolute milliseconds since the Unix epoch (UTC). "
            "Always pass both start_at_ms and end_at_ms covering the window "
            "the user asked about (e.g. this week = start of this Monday to "
            "start of next Monday)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start_at_ms": {
                    "type": "integer",
                    "description": "Range start (ms since epoch, UTC).",
                },
                "end_at_ms": {
                    "type": "integer",
                    "description": "Range end (ms since epoch, UTC). Must be > start_at_ms.",
                },
            },
            "required": ["start_at_ms", "end_at_ms"],
        }

    async def execute(self, start_at_ms: int, end_at_ms: int, **_: Any) -> str:
        if end_at_ms <= start_at_ms:
            return "Error: end_at_ms must be greater than start_at_ms"
        events = self._service.list_events(int(start_at_ms), int(end_at_ms))
        if not events:
            return f"No events between {_ms_to_iso(start_at_ms)} and {_ms_to_iso(end_at_ms)}."
        # Pretty, human-readable
        lines = [f"Found {len(events)} event(s):"]
        for ev in events:
            when = (
                f"all day {datetime.fromtimestamp(ev.start_at_ms / 1000).strftime('%Y-%m-%d')}"
                if ev.all_day
                else f"{_ms_to_iso(ev.start_at_ms)} → {_ms_to_iso(ev.end_at_ms)}"
            )
            loc = f" @ {ev.location}" if ev.location else ""
            lines.append(f"  #{ev.id} {ev.title} ({when}){loc}")
        return "\n".join(lines) + "\n\nJSON: " + _fmt_event_payload(events)


class SearchEventsTool(Tool):
    """Search calendar events by free-text query."""

    def __init__(self, schedule_service: ScheduleService):
        self._service = schedule_service

    @property
    def name(self) -> str:
        return "search_events"

    @property
    def description(self) -> str:
        return (
            "Search calendar events whose title, description, or location "
            "matches the given query. Optionally restrict to a time range. "
            "Returns at most 50 events."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text search query (matches title, description, location).",
                    "minLength": 1,
                },
                "start_at_ms": {
                    "type": "integer",
                    "description": "Optional range start (ms since epoch, UTC).",
                },
                "end_at_ms": {
                    "type": "integer",
                    "description": "Optional range end (ms since epoch, UTC).",
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        start_at_ms: int | None = None,
        end_at_ms: int | None = None,
        **_: Any,
    ) -> str:
        if not query or not query.strip():
            return "Error: query is required"
        if (start_at_ms is None) != (end_at_ms is None):
            return "Error: provide both start_at_ms and end_at_ms, or neither"
        events = self._service.search_events(
            query=query,
            start_ms=start_at_ms,
            end_ms=end_at_ms,
        )
        if not events:
            return f"No events match '{query}'."
        lines = [f"Found {len(events)} event(s) matching '{query}':"]
        for ev in events:
            when = _ms_to_iso(ev.start_at_ms)
            loc = f" @ {ev.location}" if ev.location else ""
            lines.append(f"  #{ev.id} {ev.title} ({when}){loc}")
        return "\n".join(lines) + "\n\nJSON: " + _fmt_event_payload(events)


def _ms_to_iso(ms: int) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ms)


# ---------- New tools (cancel / update / time / get) ----------


def _local_now() -> datetime:
    """Return the current local datetime, defensively.

    On Windows ``datetime.now()`` already returns local time but its tzinfo
    is None. ``astimezone()`` materialises the platform's local tz so we can
    read .strftime() cleanly and extract a tz name when available.
    """
    return datetime.now().astimezone()


def _tz_name() -> str:
    """Best-effort local timezone name; fall back to a short offset string."""
    try:
        return time.tzname[0] or "local"
    except Exception:
        return "local"


class GetCurrentTimeTool(Tool):
    """Return the current local date/time plus common range boundaries in ms.

    The assistant should call this whenever the user references a relative
    time ("tomorrow", "next Friday", "this morning") so the resulting
    ``start_at_ms`` / ``end_at_ms`` is correct for the user's local
    timezone — the wire format is always UTC ms.
    """

    def __init__(self, schedule_service: ScheduleService):
        self._service = schedule_service

    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return (
            "Return the current local date/time plus a few common range "
            "boundaries (today, this week) in absolute UTC milliseconds. "
            "ALWAYS call this before create_event / update_event / list_events "
            "when the user's request references relative time (明天, 下周三, "
            "this Friday morning). The wire format is always UTC ms."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **_: Any) -> str:
        now_local = _local_now()
        # Midnight today (local) and tomorrow midnight.
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        # Week start: Monday 00:00 local (matches the visibleRange helper
        # in the front-end; cron UI uses Monday-first weeks too).
        week_start = today_start - timedelta(days=now_local.weekday())
        week_end = week_start + timedelta(days=7)
        payload = {
            "now_ms": int(time.time() * 1000),
            "local_datetime": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "local_date": now_local.strftime("%Y-%m-%d"),
            "local_weekday": now_local.strftime("%A"),
            "timezone": _tz_name(),
            "day_start_ms": int(today_start.timestamp() * 1000),
            "day_end_ms": int(tomorrow_start.timestamp() * 1000),
            "week_start_ms": int(week_start.timestamp() * 1000),
            "week_end_ms": int(week_end.timestamp() * 1000),
        }
        pretty = (
            f"Now: {payload['local_date']} {payload['local_weekday']} "
            f"{now_local.strftime('%H:%M:%S')} ({payload['timezone']})\n"
            f"day_start_ms:    {payload['day_start_ms']}\n"
            f"day_end_ms:      {payload['day_end_ms']}\n"
            f"week_start_ms:   {payload['week_start_ms']}\n"
            f"week_end_ms:     {payload['week_end_ms']}"
        )
        return pretty + "\n\nJSON: " + json.dumps(payload, ensure_ascii=False)


class GetEventTool(Tool):
    """Fetch a single event by id."""

    def __init__(self, schedule_service: ScheduleService):
        self._service = schedule_service

    @property
    def name(self) -> str:
        return "get_event"

    @property
    def description(self) -> str:
        return (
            "Fetch a single calendar event by id. Use this when the user "
            "references an event by id (e.g. '#3') or when you need to "
            "confirm the current state of an event before updating it."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "The id of the event to fetch.",
                }
            },
            "required": ["event_id"],
        }

    async def execute(self, event_id: int, **_: Any) -> str:
        ev = self._service.get_event(int(event_id))
        if ev is None:
            return f"Event #{event_id} not found."
        payload = ev.to_dict()
        payload["start_iso"] = _ms_to_iso(ev.start_at_ms)
        payload["end_iso"] = _ms_to_iso(ev.end_at_ms)
        return (
            f"Event #{ev.id} '{ev.title}' "
            f"from {payload['start_iso']} to {payload['end_iso']}"
            f"{' [CANCELLED]' if ev.cancelled else ''}\n"
            f"JSON: {json.dumps(payload, ensure_ascii=False)}"
        )


class UpdateEventTool(Tool):
    """Partial update of an existing calendar event."""

    def __init__(self, schedule_service: ScheduleService):
        self._service = schedule_service

    @property
    def name(self) -> str:
        return "update_event"

    @property
    def description(self) -> str:
        return (
            "Partially update an existing calendar event. Only the fields "
            "you supply are changed. Times are absolute milliseconds since "
            "the Unix epoch (UTC). Use get_event first to confirm the id "
            "and current state before changing it."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "The id of the event to update.",
                },
                "title": {"type": "string", "minLength": 1},
                "start_at_ms": {"type": "integer"},
                "end_at_ms": {"type": "integer"},
                "all_day": {"type": "boolean"},
                "location": {"type": "string"},
                "description": {"type": "string"},
                "color": {
                    "type": "string",
                    "description": "Hex color, e.g. '#4F8EF7'.",
                },
            },
            "required": ["event_id"],
        }

    async def execute(
        self,
        event_id: int,
        title: str | None = None,
        start_at_ms: int | None = None,
        end_at_ms: int | None = None,
        all_day: bool | None = None,
        location: str | None = None,
        description: str | None = None,
        color: str | None = None,
        **_: Any,
    ) -> str:
        try:
            ev = self._service.update_event(
                event_id=int(event_id),
                title=title,
                start_at_ms=start_at_ms,
                end_at_ms=end_at_ms,
                all_day=all_day,
                location=location,
                description=description,
                color=color,
            )
            if ev is None:
                return f"Error: event #{event_id} not found"
            # Broadcast so any open calendar client refetches in real time.
            await self._service.publish_change("updated", ev.id)
            payload = ev.to_dict()
            payload["start_iso"] = _ms_to_iso(ev.start_at_ms)
            payload["end_iso"] = _ms_to_iso(ev.end_at_ms)
            return (
                f"Updated event #{ev.id} '{ev.title}' "
                f"now {payload['start_iso']} → {payload['end_iso']}.\n"
                f"JSON: {json.dumps(payload, ensure_ascii=False)}"
            )
        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:  # pragma: no cover
            logger.exception("update_event failed")
            return f"Error updating event: {e}"


class CancelEventTool(Tool):
    """Mark an event as cancelled (reversible, distinct from delete)."""

    def __init__(self, schedule_service: ScheduleService):
        self._service = schedule_service

    @property
    def name(self) -> str:
        return "cancel_event"

    @property
    def description(self) -> str:
        return (
            "Mark a calendar event as CANCELLED. This is reversible — the "
            "user can restore the event from the calendar modal. Prefer "
            "this over deletion for 'cancel / 不去了 / 改天再说' requests. "
            "Idempotent: calling it on an already-cancelled event is a no-op."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "The id of the event to cancel.",
                }
            },
            "required": ["event_id"],
        }

    async def execute(self, event_id: int, **_: Any) -> str:
        try:
            ev = self._service.cancel_event(int(event_id))
            if ev is None:
                return f"Error: event #{event_id} not found"
            await self._service.publish_change("updated", ev.id)
            return (
                f"Cancelled event #{ev.id} '{ev.title}'. "
                f"The user can restore it from the calendar."
            )
        except Exception as e:  # pragma: no cover
            logger.exception("cancel_event failed")
            return f"Error cancelling event: {e}"


class DeleteEventTool(Tool):
    """Move a calendar event to the recycle bin (recoverable for 30 days).

    The subagent is required by its system prompt to confirm with the user
    before calling this. The event is *soft-deleted* (stamped with
    ``deleted_at``) rather than removed from the database, so the user can
    recover it from the calendar's recycle bin within 30 days. After that
    window the row is permanently purged by the service's retention job.
    """

    def __init__(self, schedule_service: ScheduleService):
        self._service = schedule_service

    @property
    def name(self) -> str:
        return "delete_event"

    @property
    def description(self) -> str:
        return (
            "Move a calendar event to the RECYCLE BIN. This is RECOVERABLE for "
            "30 days (the user can restore it from the bin in the schedule UI). "
            "Prefer cancel_event for 'cancel / 不去了' requests; use this for "
            "'删掉 / delete' requests. The system prompt requires you to confirm "
            "with the user first."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "The id of the event to move to the recycle bin.",
                }
            },
            "required": ["event_id"],
        }

    async def execute(self, event_id: int, **_: Any) -> str:
        try:
            ev = self._service.get_event(int(event_id))
            if ev is None:
                return f"Error: event #{event_id} not found"
            title = ev.title
            moved = self._service.soft_delete_event(int(event_id))
            if not moved:
                # Already in the bin or vanished — surface the current state.
                return f"Event #{event_id} is already in the recycle bin."
            # Broadcast so any open calendar client refetches in real time.
            await self._service.publish_change("deleted", int(event_id))
            return (
                f"Moved event #{event_id} '{title}' to the recycle bin. "
                f"It can be restored within 30 days."
            )
        except Exception as e:  # pragma: no cover
            logger.exception("delete_event failed")
            return f"Error deleting event: {e}"
