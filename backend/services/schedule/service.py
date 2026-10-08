"""ScheduleService - CRUD over the schedule_events table."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from backend.core.events.types import AgentEvent
from backend.services.schedule.types import ScheduleEvent


def _now_ms() -> int:
    return int(time.time() * 1000)


# Event payload published to the bus whenever a schedule mutation succeeds.
# Subscribed clients (frontend SchedulePanel) use it to refetch.
SCHEDULE_EVENTS_CHANGED = "schedule_events_changed"


class ScheduleService:
    """Service for managing calendar events stored in SQLite.

    All times use millisecond epoch (UTC) on the wire. Range queries are
    half-open: ``[start_ms, end_ms)`` and overlap with an event when
    ``event.start_at_ms < end_ms AND event.end_at_ms > start_ms``.

    If a :class:`~backend.core.events.bus.MessageBus` is provided, every
    successful create / update / delete publishes a broadcast event so any
    open client can refresh without polling.
    """

    def __init__(self, db: Any | None = None, bus: Any | None = None):
        if db is None:
            from backend.data import Database

            db = Database()
        self._db = db
        # Optional - the service works without a bus (e.g. unit tests, the
        # cron-style direct tool path) and just skips broadcasting.
        self._bus = bus

    async def publish_change(self, action: str, event_id: int | None) -> None:
        """Broadcast a schedule change over the message bus.

        Called by both the WS handlers (after CRUD) and the LLM-callable
        tools (so a chat-driven create_event also refreshes the calendar UI
        in every open client).

        The bus is optional: if the service was constructed without one
        (e.g. in a unit test) this is a no-op. Failures are swallowed so a
        transient bus hiccup doesn't undo the user's already-persisted
        mutation.
        """
        if self._bus is None:
            return
        try:
            await self._bus.publish_event(
                AgentEvent(
                    event_type=SCHEDULE_EVENTS_CHANGED,
                    data={"action": action, "event_id": event_id},
                    channel="desktop",
                )
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Schedule: failed to broadcast {action} event: {e}")

    # ---- helpers ----------------------------------------------------------

    def _execute(self, sql: str, params: tuple = ()) -> list[Any]:
        with self._db._get_connection() as conn:
            return conn.execute(sql, params).fetchall()

    def _execute_one(self, sql: str, params: tuple = ()) -> Any | None:
        with self._db._get_connection() as conn:
            return conn.execute(sql, params).fetchone()

    def _execute_write(self, sql: str, params: tuple = ()) -> int:
        with self._db._get_connection() as conn:
            cur = conn.execute(sql, params)
            return cur.lastrowid or 0

    # ---- CRUD -------------------------------------------------------------

    def list_events(self, start_ms: int, end_ms: int) -> list[ScheduleEvent]:
        """Return events that overlap with ``[start_ms, end_ms)``."""
        rows = self._execute(
            "SELECT * FROM schedule_events "
            "WHERE start_at_ms < ? AND end_at_ms > ? "
            "ORDER BY start_at_ms ASC, id ASC",
            (end_ms, start_ms),
        )
        return [ScheduleEvent.from_row(r) for r in rows]

    def get_event(self, event_id: int) -> ScheduleEvent | None:
        row = self._execute_one(
            "SELECT * FROM schedule_events WHERE id = ?", (event_id,)
        )
        if not row:
            return None
        return ScheduleEvent.from_row(row)

    def create_event(
        self,
        title: str,
        start_at_ms: int,
        end_at_ms: int,
        all_day: bool = False,
        location: str = "",
        description: str = "",
        color: str = "#4F8EF7",
    ) -> ScheduleEvent:
        if not title or not title.strip():
            raise ValueError("title is required")
        if end_at_ms <= start_at_ms:
            raise ValueError("end_at_ms must be greater than start_at_ms")
        event_id = self._execute_write(
            "INSERT INTO schedule_events "
            "(title, description, location, color, start_at_ms, end_at_ms, all_day) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                title.strip(),
                description or "",
                location or "",
                color or "#4F8EF7",
                int(start_at_ms),
                int(end_at_ms),
                1 if all_day else 0,
            ),
        )
        logger.info(f"Schedule: created event {event_id} '{title}'")
        ev = self.get_event(event_id)
        if ev is None:
            raise RuntimeError("Failed to read created event")
        return ev

    def update_event(
        self,
        event_id: int,
        title: str | None = None,
        start_at_ms: int | None = None,
        end_at_ms: int | None = None,
        all_day: bool | None = None,
        location: str | None = None,
        description: str | None = None,
        color: str | None = None,
    ) -> ScheduleEvent | None:
        existing = self.get_event(event_id)
        if existing is None:
            return None

        new_title = title.strip() if title is not None else existing.title
        new_start = int(start_at_ms) if start_at_ms is not None else existing.start_at_ms
        new_end = int(end_at_ms) if end_at_ms is not None else existing.end_at_ms
        new_all_day = bool(all_day) if all_day is not None else existing.all_day
        new_location = location if location is not None else existing.location
        new_description = description if description is not None else existing.description
        new_color = color if color is not None else existing.color

        if not new_title:
            raise ValueError("title cannot be empty")
        if new_end <= new_start:
            raise ValueError("end_at_ms must be greater than start_at_ms")

        self._execute_write(
            "UPDATE schedule_events SET "
            "title = ?, description = ?, location = ?, color = ?, "
            "start_at_ms = ?, end_at_ms = ?, all_day = ?, "
            "updated_at = datetime('now','localtime') "
            "WHERE id = ?",
            (
                new_title,
                new_description,
                new_location,
                new_color,
                new_start,
                new_end,
                1 if new_all_day else 0,
                event_id,
            ),
        )
        logger.info(f"Schedule: updated event {event_id}")
        return self.get_event(event_id)

    def delete_event(self, event_id: int) -> bool:
        with self._db._get_connection() as conn:
            cur = conn.execute("DELETE FROM schedule_events WHERE id = ?", (event_id,))
            deleted = cur.rowcount > 0
        if deleted:
            logger.info(f"Schedule: deleted event {event_id}")
        return deleted

    # ---- search -----------------------------------------------------------

    def search_events(
        self,
        query: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 50,
    ) -> list[ScheduleEvent]:
        """LIKE-search across title/description/location, optionally bound by range."""
        if not query or not query.strip():
            return []
        like = f"%{query.strip()}%"
        sql = (
            "SELECT * FROM schedule_events "
            "WHERE (title LIKE ? OR description LIKE ? OR location LIKE ?) "
        )
        params: list[Any] = [like, like, like]
        if start_ms is not None and end_ms is not None:
            sql += "AND start_at_ms < ? AND end_at_ms > ? "
            params.extend([end_ms, start_ms])
        sql += "ORDER BY start_at_ms ASC LIMIT ?"
        params.append(int(limit))
        rows = self._execute(sql, tuple(params))
        return [ScheduleEvent.from_row(r) for r in rows]
