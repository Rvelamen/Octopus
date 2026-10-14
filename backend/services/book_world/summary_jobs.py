"""Durable public-summary status; candidates remain private to the bounded worker."""

import json
from uuid import uuid4

from .discovery import _json
from .rooms import BookRoomService
from .source import BookWorldError
from .storage import connect


class RoomSummaryJobs:
    def __init__(self, root):
        self.rooms = BookRoomService(root)

    @staticmethod
    def _public(row):
        if row is None:
            return None
        return {
            key: row[key]
            for key in ("id", "room_id", "epoch", "status", "time_limit_seconds", "error_code")
        } | {
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
        }

    def latest(self, scope):
        with connect(self.rooms.db_path) as db:
            self.rooms._room(db, scope)
            return self._public(
                db.execute(
                    "SELECT * FROM book_room_summary_jobs WHERE room_id=? AND epoch=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
                    (scope.room_id, scope.epoch),
                ).fetchone()
            )

    def create(self, scope, client_id, seconds):
        if (
            not isinstance(client_id, str)
            or not 1 <= len(client_id.strip()) <= 100
            or type(seconds) is not int
            or seconds <= 0
        ):
            raise BookWorldError("invalid_request", "Invalid summary identity or time window")
        with connect(self.rooms.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            room = self.rooms._room(db, scope)
            if room["status"] != "active":
                raise BookWorldError("room_readonly", "Room cannot start a public summary")
            prior = db.execute(
                "SELECT * FROM book_room_summary_jobs WHERE room_id=? AND epoch=? AND client_summary_id=?",
                (scope.room_id, scope.epoch, client_id),
            ).fetchone()
            if prior is not None:
                return self._public(prior)
            if db.execute(
                "SELECT 1 FROM book_room_summary_jobs WHERE room_id=? AND status IN ('queued','running')",
                (scope.room_id,),
            ).fetchone():
                raise BookWorldError("summary_busy", "This room already has a summary in progress")
            identifier = str(uuid4())
            db.execute(
                "INSERT INTO book_room_summary_jobs(id,room_id,epoch,client_summary_id,status,time_limit_seconds) VALUES (?,?,?,?,'queued',?)",
                (identifier, scope.room_id, scope.epoch, client_id, seconds),
            )
            return self._public(
                db.execute(
                    "SELECT * FROM book_room_summary_jobs WHERE id=?", (identifier,)
                ).fetchone()
            )

    def start(self, scope, identifier):
        with connect(self.rooms.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.rooms._room(db, scope)
            row = db.execute(
                "SELECT * FROM book_room_summary_jobs WHERE room_id=? AND epoch=? AND id=?",
                (scope.room_id, scope.epoch, identifier),
            ).fetchone()
            if row is None or row["status"] != "queued":
                return None
            db.execute(
                "UPDATE book_room_summary_jobs SET status='running' WHERE id=?", (identifier,)
            )
            return row["generation"]

    def authorized(self, scope, identifier, generation, db=None):
        if db is None:
            with connect(self.rooms.db_path) as connection:
                return self.authorized(scope, identifier, generation, connection)
        self.rooms._room(db, scope)
        return (
            db.execute(
                "SELECT 1 FROM book_room_summary_jobs j JOIN book_rooms r ON r.id=j.room_id AND r.current_epoch=j.epoch WHERE j.room_id=? AND j.epoch=? AND j.id=? AND j.generation=? AND j.status='running' AND r.status='active'",
                (scope.room_id, scope.epoch, identifier, generation),
            ).fetchone()
            is not None
        )

    def finish(self, scope, identifier, generation, *, result=None, error=None, db=None):
        if scope.workspace_id != self.rooms.workspace_id:
            raise BookWorldError("invalid_scope", "Summary belongs to another workspace")
        if db is None:
            with connect(self.rooms.db_path) as connection:
                return self.finish(
                    scope, identifier, generation, result=result, error=error, db=connection
                )
        db.execute(
            "UPDATE book_room_summary_jobs SET status=?,result_json=?,error_code=? WHERE room_id=? AND epoch=? AND id=? AND generation=? AND status IN ('queued','running')",
            (
                "failed" if error else "completed",
                _json(result) if result else None,
                error,
                scope.room_id,
                scope.epoch,
                identifier,
                generation,
            ),
        )

    def cancel(self, scope, identifier):
        with connect(self.rooms.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.rooms._room(db, scope)
            row = db.execute(
                "SELECT * FROM book_room_summary_jobs WHERE room_id=? AND epoch=? AND id=?",
                (scope.room_id, scope.epoch, identifier),
            ).fetchone()
            if row is None:
                raise BookWorldError("invalid_scope", "Summary does not belong to this room")
            db.execute(
                "UPDATE book_room_summary_jobs SET status='cancelled',generation=generation+1 WHERE id=? AND status IN ('queued','running')",
                (identifier,),
            )
        return self.latest(scope)

    def recover(self):
        with connect(self.rooms.db_path) as db:
            db.execute(
                "UPDATE book_room_summary_jobs SET status='interrupted',generation=generation+1,error_code='service_interrupted' WHERE status IN ('queued','running')"
            )
