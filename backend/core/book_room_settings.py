"""Validated, user-configurable time limits for book-character rooms."""

from typing import Annotated

from pydantic import BaseModel, Field

DEFAULT_BOOK_ROOM_TIMEOUT_SECONDS = 60
DEFAULT_BOOK_ROOM_ALL_TIMEOUT_SECONDS = 300
MAX_BOOK_ROOM_TIMEOUT_SECONDS = 2_147_483_647
TimeoutSeconds = Annotated[
    int, Field(strict=True, gt=0, le=MAX_BOOK_ROOM_TIMEOUT_SECONDS)
]


class BookRoomTimeoutSettings(BaseModel):
    """Keep preferences in seconds; select a snapshot for the requested mode."""

    model_config = {"populate_by_name": True}

    book_room_round_timeout_seconds: TimeoutSeconds = Field(
        default=DEFAULT_BOOK_ROOM_TIMEOUT_SECONDS, alias="bookRoomRoundTimeoutSeconds"
    )
    book_room_all_round_timeout_seconds: TimeoutSeconds = Field(
        default=DEFAULT_BOOK_ROOM_ALL_TIMEOUT_SECONDS, alias="bookRoomAllRoundTimeoutSeconds"
    )

    def seconds_for_mode(self, mode: str) -> int:
        """Return the configured limit without converting seconds to milliseconds."""
        if mode == "all":
            return self.book_room_all_round_timeout_seconds
        if mode in {"directed", "natural"}:
            return self.book_room_round_timeout_seconds
        raise ValueError(f"Unknown book-room mode: {mode}")
