"""Schedule (日程) tools - LLM-callable tools for calendar events.

Three focused tools that mirror the ScheduleService CRUD surface and are
designed to be the only interface the schedule-assistant subagent needs.
"""

from __future__ import annotations

import json
from datetime import datetime
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
