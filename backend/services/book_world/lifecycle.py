"""Fence one book before retryable payload/file removal, retaining B and room history."""

import shutil
import sqlite3
import threading
from pathlib import Path

from .room_models import RoomScope
from .round_queue import advance_cursor
from .source import BookSourceService, BookWorldError
from .storage import connect, workspace_identity

_purge_locks: dict[tuple[str, str], threading.Lock] = {}
_locks_guard = threading.Lock()


def fence_book_rooms(db, book_id: str, workspace_id: str) -> None:
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='book_rooms'").fetchone():
        return
    rooms = [
        row["room_id"]
        for row in db.execute("SELECT room_id FROM book_room_sources WHERE book_id=?", (book_id,))
    ]
    db.execute("UPDATE book_room_sources SET status='source_removed' WHERE book_id=?", (book_id,))
    db.execute(
        "UPDATE book_room_members SET active=0,removed_reason='source_removed',membership_generation=membership_generation+1,ephemeral_state_json='{}' WHERE book_id=? AND removed_reason IS NOT 'source_removed'",
        (book_id,),
    )
    for identifier in rooms:
        room = db.execute("SELECT * FROM book_rooms WHERE id=?", (identifier,)).fetchone()
        scope = RoomScope(
            workspace_id=workspace_id, room_id=identifier, epoch=room["current_epoch"]
        )
        active = db.execute(
            "SELECT 1 FROM book_room_sources rs JOIN book_books k ON k.id=rs.book_id JOIN book_source_versions s ON s.book_id=rs.book_id AND s.id=rs.source_version_id JOIN book_builds b ON b.book_id=rs.book_id AND b.source_version_id=rs.source_version_id AND b.id=rs.build_id WHERE rs.room_id=? AND rs.status='active' AND k.lifecycle_state='active' AND s.lifecycle_state='available' AND b.lifecycle_state='active' LIMIT 1",
            (identifier,),
        ).fetchone()
        rounds = db.execute(
            "SELECT r.id,r.status,r.cursor,sl.position,sl.status AS slot_status FROM book_room_rounds r JOIN book_round_slots sl ON sl.room_id=r.room_id AND sl.epoch=r.epoch AND sl.round_id=r.id JOIN book_room_members m ON m.room_id=sl.room_id AND m.id=sl.member_id WHERE r.room_id=? AND r.epoch=? AND r.status IN ('queued','running','paused','interrupted','failed') AND sl.status IN ('pending','running','failed') AND m.book_id=?",
            (identifier, scope.epoch, book_id),
        ).fetchall()
        db.execute(
            "UPDATE book_round_slots SET status='no_comment',skip_reason='source_unavailable' WHERE room_id=? AND epoch=? AND status IN ('pending','running','failed') AND member_id IN (SELECT id FROM book_room_members WHERE room_id=? AND book_id=?)",
            (identifier, scope.epoch, identifier, book_id),
        )
        if active is None:
            db.execute(
                "UPDATE book_rooms SET status='readonly' WHERE id=? AND status='active'",
                (identifier,),
            )
            db.execute(
                "UPDATE book_room_rounds SET status='cancelled',cancel_requested=1,error_code='source_unavailable',lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL,progress_phase=NULL WHERE room_id=? AND status IN ('queued','running','paused','interrupted','failed')",
                (identifier,),
            )
            db.execute(
                "UPDATE book_round_slots SET status='cancelled' WHERE room_id=? AND epoch=? AND status IN ('pending','running','failed')",
                (identifier, scope.epoch),
            )
        else:
            for row in {row["id"]: row for row in rounds}.values():
                current_lost = any(
                    entry["id"] == row["id"]
                    and entry["status"] == "running"
                    and entry["cursor"] == entry["position"]
                    for entry in rounds
                )
                advance_cursor(db, scope, row["id"], revoke_current=current_lost)


class BookLifecycleService:
    def __init__(self, workspace_root: str | Path):
        source = BookSourceService(workspace_root)
        self.root = source.root
        self.db_path = source.db_path
        self.workspace_id = workspace_identity(self.root)

    def interrupt_builds(self) -> None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE book_builds SET status='queued',lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL WHERE status='running' AND lifecycle_state='active'"
            )
            db.execute(
                "UPDATE book_expression_sets SET status='paused',lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL,error_code='service_interrupted' WHERE status='running' AND lifecycle_state='active'"
            )

    def status(self, book_id: str) -> dict:
        with connect(self.db_path) as db:
            row = db.execute(
                "SELECT p.*,b.title_snapshot FROM book_source_purges p JOIN book_books b ON b.id=p.book_id WHERE p.book_id=?",
                (book_id,),
            ).fetchone()
        if row is None:
            raise BookWorldError("purge_unavailable", "No deletion exists for this book")
        return {
            "workspace_id": self.workspace_id,
            "book_id": book_id,
            "title": row["title_snapshot"],
            "status": row["status"],
            "error_code": row["error_code"],
        }

    def _redact(self, book_id: str) -> str | None:
        with connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute(
                "SELECT p.*,b.lifecycle_state FROM book_source_purges p JOIN book_books b ON b.id=p.book_id WHERE p.book_id=?",
                (book_id,),
            ).fetchone()
            if job is None or job["lifecycle_state"] == "active":
                raise BookWorldError(
                    "purge_unavailable", "Source authorization must be disabled before cleanup"
                )
            if job["status"] == "completed":
                return None
            db.execute(
                "UPDATE book_source_purges SET status='running',error_code=NULL WHERE book_id=?",
                (book_id,),
            )
            db.execute(
                "UPDATE book_segments SET text=replace(hex(zeroblob(length(text))),'00',' '),chapter=NULL WHERE book_id=?",
                (book_id,),
            )
            db.execute(
                "UPDATE book_claims SET proposition='',search_terms='' WHERE book_id=?", (book_id,)
            )
            db.execute(
                "UPDATE book_access_evidence SET approved_excerpt='',visibility_state='rejected' WHERE book_id=?",
                (book_id,),
            )
            db.execute(
                "UPDATE book_claim_access SET access_state='revoked' WHERE book_id=?", (book_id,)
            )
            db.execute("UPDATE book_evidence SET quote_text='' WHERE book_id=?", (book_id,))
            db.execute("DELETE FROM book_character_baselines WHERE book_id=?", (book_id,))
            db.execute("DELETE FROM book_character_aliases WHERE book_id=?", (book_id,))
            db.execute(
                "UPDATE book_characters SET agent_status='source_removed',public_profile_json=json_object('name',name),runtime_policy_json='{}' WHERE book_id=?",
                (book_id,),
            )
            db.execute(
                "UPDATE book_scenes SET location_label=NULL,story_time_json='{}' WHERE book_id=?",
                (book_id,),
            )
            db.execute("UPDATE book_build_steps SET result_json='{}' WHERE book_id=?", (book_id,))
            db.execute("UPDATE book_builds SET error_detail=NULL WHERE book_id=?", (book_id,))
            db.execute(
                "UPDATE book_revisions SET changes_json='[]',review_json='{}' WHERE book_id=?",
                (book_id,),
            )
            db.execute("DELETE FROM book_user_extensions WHERE book_id=?", (book_id,))
            db.execute("DELETE FROM book_expression_materials WHERE book_id=?", (book_id,))
            db.execute(
                "UPDATE book_expression_sets SET progress_json='[]',error_detail=NULL WHERE book_id=?",
                (book_id,),
            )
            db.execute(
                "DELETE FROM book_claims_fts WHERE rowid IN (SELECT rowid FROM book_access_evidence WHERE book_id=?)",
                (book_id,),
            )
            db.execute(
                "UPDATE book_source_versions SET quality_json='{}' WHERE book_id=?", (book_id,)
            )
            # Remove every ordinary-library retrieval payload before touching
            # files. A file lock must not leave the original text searchable.
            db.execute("DELETE FROM library_chunks WHERE item_id=?", (job["library_item_id"],))
            db.execute("DELETE FROM library_annotations WHERE item_id=?", (job["library_item_id"],))
            prefix = job["library_rel_path"].replace("\\", "/") + "/"
            db.execute("DELETE FROM library_note_links WHERE instr(replace(from_path,char(92),'/'),?)=1 OR instr(replace(to_path,char(92),'/'),?)=1", (prefix, prefix))
            db.execute("DELETE FROM library_notes WHERE instr(replace(path,char(92),'/'),?)=1", (prefix,))
            db.execute("DELETE FROM knowledge_links WHERE instr(replace(from_path,char(92),'/'),?)=1 OR instr(replace(to_path,char(92),'/'),?)=1", (prefix, prefix))
            db.execute("DELETE FROM knowledge_nodes WHERE instr(replace(path,char(92),'/'),?)=1", (prefix,))
            db.execute("UPDATE library_items SET abstract=NULL,metadata_json='{}',chunk_status='failed' WHERE id=?", (job["library_item_id"],))
            return str(job["library_rel_path"])

    def purge(self, book_id: str) -> dict:
        with _locks_guard:
            lock = _purge_locks.setdefault((self.workspace_id, book_id), threading.Lock())
        with lock:
            return self._purge(book_id)

    def _purge(self, book_id: str) -> dict:
        try:
            relative = self._redact(book_id)
            if relative is None:
                return self.status(book_id)
            target = (self.root / relative).resolve()
            parent = (self.root / "knowledge/library").resolve()
            if target == parent or not target.is_relative_to(parent):
                raise BookWorldError(
                    "invalid_purge_path", "Deletion target is outside this workspace library item"
                )
            if target.exists():
                try:
                    shutil.rmtree(target)
                except FileNotFoundError:
                    # Another process may have already completed the same
                    # irreversible removal. Accept only an absent item folder.
                    if target.exists():
                        raise
            with connect(self.db_path) as db:
                db.execute("BEGIN IMMEDIATE")
                job = db.execute(
                    "SELECT library_item_id,library_rel_path FROM book_source_purges WHERE book_id=?",
                    (book_id,),
                ).fetchone()
                db.execute(
                    "DELETE FROM library_items WHERE id=? AND EXISTS(SELECT 1 FROM book_books b WHERE b.id=? AND b.library_item_id=library_items.id AND b.lifecycle_state<>'active')",
                    (job["library_item_id"], book_id),
                )
                db.execute(
                    "UPDATE book_source_versions SET lifecycle_state='purged',asset_rel_path=NULL,text_rel_path=NULL WHERE book_id=?",
                    (book_id,),
                )
                db.execute(
                    "UPDATE book_builds SET lifecycle_state='purged' WHERE book_id=?", (book_id,)
                )
                db.execute("UPDATE book_books SET lifecycle_state='removed' WHERE id=?", (book_id,))
                db.execute(
                    "UPDATE book_source_purges SET status='completed',error_code=NULL,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE book_id=?",
                    (book_id,),
                )
        except (OSError, BookWorldError, sqlite3.Error):
            with connect(self.db_path) as db:
                db.execute(
                    "UPDATE book_source_purges SET status='failed',error_code='source_cleanup_failed' WHERE book_id=? AND status<>'completed'",
                    (book_id,),
                )
            if self.status(book_id)["status"] == "completed":
                return self.status(book_id)
            raise BookWorldError(
                "source_cleanup_failed",
                "Source disabled; file cleanup failed. Retry cleanup from the room source status.",
            ) from None
        return self.status(book_id)
