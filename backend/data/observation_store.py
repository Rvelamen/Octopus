"""Observation storage for structured agent memory."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from backend.data.database import Database


@dataclass
class ObservationRecord:
    """Structured observation extracted from conversation."""
    id: int | None = None
    session_instance_id: int | None = None
    type: str = "general"
    title: str = ""
    narrative: str = ""
    files: list[str] = None
    concepts: list[str] = None
    token_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self):
        if self.files is None:
            self.files = []
        if self.concepts is None:
            self.concepts = []


class ObservationRepository:
    """Repository for observation CRUD and FTS5 search."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def add_observation(self, record: ObservationRecord) -> ObservationRecord:
        """Add a new observation to the database."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO observations (
                    session_instance_id, type, title, narrative,
                    files_json, concepts_json, token_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
                """,
                (
                    record.session_instance_id,
                    record.type,
                    record.title,
                    record.narrative,
                    json.dumps(record.files, ensure_ascii=False),
                    json.dumps(record.concepts, ensure_ascii=False),
                    record.token_count,
                ),
            )
            row = conn.execute(
                "SELECT * FROM observations WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            logger.info(f"Created observation #{cursor.lastrowid}: {record.title}")
            return self._row_to_record(row)

    def get_by_id(self, obs_id: int) -> ObservationRecord | None:
        """Get observation by ID."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM observations WHERE id = ?",
                (obs_id,),
            ).fetchone()
            return self._row_to_record(row) if row else None

    def get_by_instance(
        self, instance_id: int, limit: int = 50, offset: int = 0
    ) -> list[ObservationRecord]:
        """Get observations for a session instance."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM observations
                WHERE session_instance_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (instance_id, limit, offset),
            ).fetchall()
            return [self._row_to_record(row) for row in rows]

    def get_recent(self, limit: int = 50) -> list[ObservationRecord]:
        """Get recent observations across all instances."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM observations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._row_to_record(row) for row in rows]

    def search_fts(
        self,
        query: str,
        limit: int = 20,
        type_filter: str | None = None,
        instance_id: int | None = None,
    ) -> list[ObservationRecord]:
        """Full-text search over observations via FTS5."""
        # Escape FTS5 query quotes
        safe_query = query.replace('"', '""')
        with self.db._get_connection() as conn:
            sql = """
                SELECT o.* FROM observations o
                JOIN observations_fts f ON o.id = f.rowid
                WHERE observations_fts MATCH ?
            """
            params: list[Any] = [safe_query]
            if type_filter:
                sql += " AND o.type = ?"
                params.append(type_filter)
            if instance_id is not None:
                sql += " AND o.session_instance_id = ?"
                params.append(instance_id)
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_record(row) for row in rows]

    def get_timeline(
        self,
        anchor_id: int,
        depth_before: int = 2,
        depth_after: int = 2,
    ) -> list[ObservationRecord]:
        """Get observations around a given anchor observation."""
        anchor = self.get_by_id(anchor_id)
        if not anchor or not anchor.session_instance_id or not anchor.created_at:
            return []
        with self.db._get_connection() as conn:
            # Before
            before_rows = conn.execute(
                """
                SELECT * FROM observations
                WHERE session_instance_id = ? AND created_at <= ? AND id != ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (anchor.session_instance_id, anchor.created_at.isoformat(), anchor_id, depth_before),
            ).fetchall()
            # After
            after_rows = conn.execute(
                """
                SELECT * FROM observations
                WHERE session_instance_id = ? AND created_at > ? AND id != ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (anchor.session_instance_id, anchor.created_at.isoformat(), anchor_id, depth_after),
            ).fetchall()
            before = [self._row_to_record(r) for r in before_rows]
            after = [self._row_to_record(r) for r in after_rows]
            merged = list(reversed(before)) + [anchor] + after
            return merged

    def delete_observation(self, obs_id: int) -> bool:
        """Delete an observation by ID."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM observations WHERE id = ?",
                (obs_id,),
            )
            return cursor.rowcount > 0

    def build_index_markdown(
        self,
        instance_id: int | None = None,
        limit: int = 20,
    ) -> str:
        """Build a compact index table of observations for context injection."""
        records = (
            self.get_by_instance(instance_id, limit=limit)
            if instance_id is not None
            else self.get_recent(limit=limit)
        )
        if not records:
            return ""

        type_icon = {
            "gotcha": "🔴",
            "problem-solution": "🟡",
            "how-it-works": "🔵",
            "what-changed": "🟢",
            "discovery": "🟣",
            "why-it-exists": "🟠",
            "decision": "🟤",
            "trade-off": "⚖️",
            "general": "⚪",
        }

        lines = [
            "## Recent Observations",
            "",
            "| ID | Time | Type | Title | ~Tokens |",
            "|----|------|------|-------|---------|",
        ]
        for r in records:
            icon = type_icon.get(r.type, "⚪")
            time_str = r.created_at.strftime("%H:%M") if r.created_at else ""
            lines.append(
                f"| #{r.id} | {time_str} | {icon} {r.type} | {r.title} | ~{r.token_count} |"
            )
        lines.append("")
        lines.append(
            "💡 **Progressive Disclosure:** Use `memory_search` to find observations, "
            "`memory_read` to fetch full details by ID, or `memory_timeline` to see context around one."
        )
        return "\n".join(lines)

    def _row_to_record(self, row) -> ObservationRecord:
        """Convert a DB row to ObservationRecord."""
        files = []
        concepts = []
        if row["files_json"]:
            try:
                files = json.loads(row["files_json"])
            except json.JSONDecodeError:
                files = []
        if row["concepts_json"]:
            try:
                concepts = json.loads(row["concepts_json"])
            except json.JSONDecodeError:
                concepts = []
        return ObservationRecord(
            id=row["id"],
            session_instance_id=row["session_instance_id"],
            type=row["type"],
            title=row["title"],
            narrative=row["narrative"],
            files=files,
            concepts=concepts,
            token_count=row["token_count"] or 0,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
