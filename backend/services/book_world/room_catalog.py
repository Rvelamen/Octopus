"""Published public character identities for room selection, without reader evidence."""

from pathlib import Path

from .rooms import BookRoomService
from .source import BookWorldError
from .storage import connect


class RoomCharacterCatalog:
    def __init__(self, workspace_root: str | Path):
        self.rooms = BookRoomService(workspace_root)

    def list(self, *, limit: int = 25, offset: int = 0, query: str = "") -> dict:
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or type(offset) is not int
            or offset < 0
            or not isinstance(query, str)
            or len(query) > 200
        ):
            raise BookWorldError("invalid_request", "Invalid public character page")
        joins = "FROM book_characters c JOIN book_builds b ON b.book_id=c.book_id AND b.source_version_id=c.source_version_id AND b.id=c.build_id JOIN book_books k ON k.id=b.book_id JOIN book_source_versions s ON s.book_id=b.book_id AND s.id=b.source_version_id WHERE b.stage='persona_published' AND b.status IN ('published','partial_published') AND b.lifecycle_state='active' AND k.lifecycle_state='active' AND s.lifecycle_state='available' AND c.agent_status IN ('ready','sparse') AND (?='' OR instr(c.name,?)>0 OR instr(k.title_snapshot,?)>0)"
        args = (query.strip(),) * 3
        with connect(self.rooms.db_path) as db:
            db.execute("BEGIN")
            total = db.execute("SELECT COUNT(*) " + joins, args).fetchone()[0]
            rows = db.execute(
                "SELECT k.library_item_id AS item_id,k.title_snapshot AS book_title,c.name,c.id AS character_id,c.agent_status,c.book_id,c.source_version_id,c.build_id,b.created_at "
                + joins
                + " ORDER BY k.title_snapshot,k.library_item_id,b.created_at DESC,c.name,c.id LIMIT ? OFFSET ?",
                (*args, limit, offset),
            ).fetchall()
        return {
            "workspace_id": self.rooms.workspace_id,
            "characters": [dict(row) for row in rows],
            "total": total,
            "next_offset": offset + len(rows) if offset + len(rows) < total else None,
        }
