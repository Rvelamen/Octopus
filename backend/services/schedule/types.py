"""Schedule types - calendar event dataclasses."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScheduleEvent:
    """A single calendar event."""

    id: int
    title: str
    description: str = ""
    location: str = ""
    color: str = "#4F8EF7"
    start_at_ms: int = 0
    end_at_ms: int = 0
    all_day: bool = False
    cancelled: bool = False
    # Soft-delete stamp: NULL = active, non-NULL = in recycle bin. Combined
    # with a 30-day retention enforced by ``ScheduleService.purge_old_deleted``.
    deleted_at_ms: int = 0
    created_at_ms: int = 0
    updated_at_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "color": self.color,
            "start_at_ms": self.start_at_ms,
            "end_at_ms": self.end_at_ms,
            "all_day": bool(self.all_day),
            "cancelled": bool(self.cancelled),
            "deleted_at_ms": self.deleted_at_ms,
            "created_at_ms": self.created_at_ms,
            "updated_at_ms": self.updated_at_ms,
        }

    @classmethod
    def from_row(cls, row: Any) -> "ScheduleEvent":
        """Construct from a sqlite3.Row."""
        d = dict(row)
        return cls(
            id=d["id"],
            title=d["title"],
            description=d.get("description") or "",
            location=d.get("location") or "",
            color=d.get("color") or "#4F8EF7",
            start_at_ms=d["start_at_ms"],
            end_at_ms=d["end_at_ms"],
            all_day=bool(d.get("all_day", 0)),
            cancelled=bool(d.get("cancelled", 0)),
            deleted_at_ms=_parse_iso_ms(d.get("deleted_at")),
            created_at_ms=_parse_iso_ms(d.get("created_at")),
            updated_at_ms=_parse_iso_ms(d.get("updated_at")),
        )


def _parse_iso_ms(value: Any) -> int:
    """Parse an ISO-like 'YYYY-MM-DD HH:MM:SS' timestamp to milliseconds.

    Falls back to 0 on any error; the database stores localtime timestamps
    and we only need a coarse epoch here.
    """
    if value is None or value == "":
        return 0
    if not isinstance(value, str):
        try:
            return int(value)
        except Exception:
            return 0
    try:
        from datetime import datetime

        # SQLite's datetime('now','localtime') produces 'YYYY-MM-DD HH:MM:SS'
        return int(datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
    except Exception:
        return 0
