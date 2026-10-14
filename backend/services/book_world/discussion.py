"""Room discussion configuration; it never changes character knowledge or memory epochs."""

from .room_models import RoomScope
from .rooms import BookRoomService
from .source import BookWorldError
from .storage import connect


def check_discussion_revision(room, expected_revision: int | None) -> None:
    # Legacy callers use the server's current configuration; new clients send CAS.
    if expected_revision is None:
        return
    if type(expected_revision) is not int or expected_revision != room["discussion_revision"]:
        raise BookWorldError(
            "stale_discussion_revision", "Refresh the discussion before submitting"
        )


class RoomDiscussionService:
    def __init__(self, workspace_root):
        self.rooms = BookRoomService(workspace_root)

    def set(self, scope: RoomScope, expected_revision: int, mode: str, topic=None, goal=None):
        if (
            type(expected_revision) is not int
            or expected_revision < 0
            or mode not in ("free", "topic")
        ):
            raise BookWorldError("invalid_request", "Invalid discussion mode or revision")
        if (topic is not None and (not isinstance(topic, str) or len(topic) > 200)) or (
            goal is not None and (not isinstance(goal, str) or len(goal) > 1000)
        ):
            raise BookWorldError("invalid_request", "Discussion topic or goal exceeds its limit")
        topic = topic.strip() if topic is not None else None
        goal = goal.strip() if goal is not None else None
        if mode == "topic" and not topic:
            raise BookWorldError("invalid_request", "Topic conversation requires a nonempty topic")
        topic, goal = (topic, goal or None) if mode == "topic" else (None, None)
        with connect(self.rooms.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            room = self.rooms._room(db, scope)
            if room["status"] != "active":
                raise BookWorldError("room_readonly", "Room no longer accepts discussion changes")
            check_discussion_revision(room, expected_revision)
            if db.execute(
                "SELECT 1 FROM book_room_rounds WHERE room_id=? AND status IN ('queued','running','paused','interrupted')",
                (scope.room_id,),
            ).fetchone():
                raise BookWorldError(
                    "room_busy", "Stop the current turn before changing discussion"
                )
            db.execute(
                "UPDATE book_rooms SET discussion_mode=?,discussion_topic=?,discussion_goal=?,discussion_revision=discussion_revision+1 WHERE id=?",
                (mode, topic, goal, scope.room_id),
            )
        return self.rooms.get_room(scope)
