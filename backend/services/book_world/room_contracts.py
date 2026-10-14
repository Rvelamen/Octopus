"""Desktop clients request user actions; character publication remains internal."""

from typing import Literal

from pydantic import Field, model_validator

from .discovery_models import StrictModel


class RoomCharacterSelection(StrictModel):
    item_id: int = Field(ge=1)
    build_id: str = Field(min_length=1, max_length=100)
    character_id: str = Field(min_length=1, max_length=100)


class BookRoomRequest(StrictModel):
    action: Literal[
        "create_single_room",
        "list_rooms",
        "list_chat_models",
        "get_room",
        "open_room",
        "read_messages",
        "get_round",
        "submit_turn",
        "cancel_round",
        "pause_round",
        "resume_round",
        "get_message_evidence",
        "get_member_profile",
        "get_memory",
        "reset_memory",
        "list_room_characters",
        "get_room_character",
        "create_group_room",
        "add_members",
        "set_member",
        "retry_source_cleanup",
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
    characters: list[RoomCharacterSelection] | None = Field(
        default=None, min_length=1, max_length=100
    )
    member_id: str | None = Field(default=None, min_length=1, max_length=100)
    source_book_id: str | None = Field(default=None, min_length=1, max_length=100)
    active: bool | None = None
    speaking_mode: Literal["auto", "mention_only", "muted"] | None = None
    mode: Literal["directed", "natural", "all"] = "directed"
    target_member_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)
    query: str = Field(default="", max_length=200)
    after_seq: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def required(self) -> "BookRoomRequest":
        if self.action == "retry_source_cleanup" and self.source_book_id is None:
            raise ValueError("Choose the source book whose cleanup failed")
        listings = ("list_rooms", "list_chat_models", "list_room_characters")
        if self.action not in listings and self.workspace_id is None:
            raise ValueError("Workspace identity is required")
        if self.action == "get_room_character":
            if None in (self.item_id, self.build_id, self.character_id):
                raise ValueError("Public character lookup requires a complete published identity")
        elif self.action == "create_single_room":
            if None in (self.item_id, self.build_id, self.character_id, self.client_room_id):
                raise ValueError("Room creation requires a published character and client identity")
        elif self.action == "create_group_room":
            if self.characters is None or self.client_room_id is None:
                raise ValueError("Group creation requires characters and creation identity")
        elif self.action == "open_room":
            if self.room_id is None:
                raise ValueError("Opening a room requires its identity")
        elif self.action not in listings and None in (
            self.room_id,
            self.expected_epoch,
        ):
            raise ValueError("Room identity and expected epoch are required")
        if (self.provider_id is None) != (self.model_record_id is None):
            raise ValueError("Provider and model selection must be supplied together")
        if (
            self.action in ("get_round", "cancel_round", "pause_round", "resume_round")
            and self.round_id is None
        ):
            raise ValueError("Round identity is required")
        if self.action == "submit_turn" and None in (self.client_turn_id, self.content):
            raise ValueError("Turn identity and message are required")
        if self.target_member_ids is not None and (
            self.mode != "directed"
            or len(set(self.target_member_ids)) != len(self.target_member_ids)
            or any(not 1 <= len(member) <= 100 for member in self.target_member_ids)
        ):
            raise ValueError("Directed targets must be distinct member identities")
        if self.action == "get_message_evidence" and self.message_id is None:
            raise ValueError("Message identity is required")
        if self.action == "get_member_profile" and self.member_id is None:
            raise ValueError("Member identity is required")
        if self.action == "add_members" and self.characters is None:
            raise ValueError("Joining requires published character selections")
        if self.action == "set_member" and (
            self.member_id is None or (self.active is None and self.speaking_mode is None)
        ):
            raise ValueError("Member control requires an identity and a control value")
        return self
