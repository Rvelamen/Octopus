"""Fixed public room identity and bounded generation policy."""

from typing import Literal

from pydantic import Field

from .discovery_models import DiscoveryConfig, StrictModel

ROOM_POLICY_VERSION = "bounded-room-v1"


class RoomScope(StrictModel):
    workspace_id: str = Field(min_length=1, max_length=100)
    room_id: str = Field(min_length=1, max_length=100)
    epoch: int = Field(gt=0)
    policy_version: str = ROOM_POLICY_VERSION


class CharacterChatConfig(DiscoveryConfig):
    model_record_id: int | None = Field(default=None, ge=1)
    prompt_version: str = "character-chat-v3"
    policy_version: str = ROOM_POLICY_VERSION
    review_prompt_version: str = "character-chat-review-v2"
    context_window: int = Field(default=32768, ge=16000)
    max_input_tokens: int = Field(default=24000, ge=1000, le=200000)
    expression_enabled: bool = False
    memory_policy_version: Literal["legacy-history-v1", "typed-room-memory-v1"] = (
        "legacy-history-v1"
    )
    memory_prompt_version: Literal["room-memory-v1", "room-memory-v2"] = "room-memory-v1"
    expression_selection_version: Literal["expression-selection-v1", "expression-selection-v2"] = (
        "expression-selection-v1"
    )
    expression_sets: dict[str, str | None] = Field(default_factory=dict)

    @classmethod
    def from_model(
        cls, config: DiscoveryConfig, context_window: int = 32768
    ) -> "CharacterChatConfig":
        return cls(
            **config.model_dump(exclude={"prompt_version", "policy_version"}),
            context_window=context_window,
        )
