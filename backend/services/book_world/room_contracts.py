"""Desktop clients request user actions; character publication remains internal."""

from typing import Literal

from pydantic import Field, model_validator

from .discovery_models import StrictModel


class BookRoomRequest(StrictModel):
    action: Literal[
        "create_single_room",
        "list_rooms",
        "list_chat_models",
        "get_room",
        "read_messages",
        "get_round",
        "submit_turn",
        "cancel_round",
        "resume_round",
        "get_message_evidence",
    ]
    workspace_id: str | None = Field(default=None, min_length=1, max_length=100)
    item_id: int | None = Field(default=None, ge=1)
    build_id: str | None = Field(default=None, min_length=1, max_length=100)
    character_id: str | None = Field(default=None, min_length=1, max_length=100)
    client_room_id: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    reuse_existing: bool = False
    provider_id: int | None = Field(default=None, ge=1)
    model_record_id: int | None = Field(default=None, ge=1)
    room_id: str | None = Field(default=None, min_length=1, max_length=100)
    expected_epoch: int | None = Field(default=None, gt=0)
    round_id: str | None = Field(default=None, min_length=1, max_length=100)
    client_turn_id: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    message_id: str | None = Field(default=None, min_length=1, max_length=100)
    after_seq: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def required(self) -> "BookRoomRequest":
        if self.action not in ("list_rooms", "list_chat_models") and self.workspace_id is None:
            raise ValueError("Workspace identity is required")
        if self.action == "create_single_room":
            if None in (self.item_id, self.build_id, self.character_id, self.client_room_id):
                raise ValueError("Room creation requires a published character and client identity")
        elif self.action not in ("list_rooms", "list_chat_models") and None in (
            self.room_id,
            self.expected_epoch,
        ):
            raise ValueError("Room identity and expected epoch are required")
        if (self.provider_id is None) != (self.model_record_id is None):
            raise ValueError("Provider and model selection must be supplied together")
        if self.action in ("get_round", "cancel_round", "resume_round") and self.round_id is None:
            raise ValueError("Round identity is required")
        if self.action == "submit_turn" and None in (self.client_turn_id, self.content):
            raise ValueError("Turn identity and message are required")
        if self.action == "get_message_evidence" and self.message_id is None:
            raise ValueError("Message identity is required")
        return self
