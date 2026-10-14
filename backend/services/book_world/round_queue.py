"""Advance a fixed round past terminal slots without creating another turn."""

from .room_models import RoomScope


def advance_cursor(db, scope: RoomScope, round_id: str, *, revoke_current: bool = False) -> None:
    row = db.execute(
        "SELECT * FROM book_room_rounds WHERE room_id=? AND epoch=? AND id=?",
        (scope.room_id, scope.epoch, round_id),
    ).fetchone()
    slots = db.execute(
        "SELECT position,status FROM book_round_slots WHERE room_id=? AND epoch=? AND round_id=? ORDER BY position",
        (scope.room_id, scope.epoch, round_id),
    ).fetchall()
    cursor = row["cursor"]
    while cursor < len(slots) and slots[cursor]["status"] in (
        "published",
        "no_comment",
        "cancelled",
    ):
        cursor += 1
    status = (
        "completed"
        if cursor == len(slots)
        else "queued"
        if revoke_current and row["status"] == "running"
        else row["status"]
    )
    if status == "completed" or revoke_current:
        db.execute(
            "UPDATE book_room_rounds SET cursor=?,status=?,lease_generation=lease_generation+1,lease_owner=NULL,lease_expires_at=NULL WHERE id=?",
            (cursor, status, round_id),
        )
    else:
        db.execute("UPDATE book_room_rounds SET cursor=? WHERE id=?", (cursor, round_id))
