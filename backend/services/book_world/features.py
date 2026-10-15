"""Process-start release gates; disabling preserves all persisted book records."""

import asyncio
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from functools import lru_cache

from .source import BookWorldError


@dataclass(frozen=True)
class BookWorldFeatures:
    characters: bool
    single_chat: bool
    group_chat: bool
    automatic_import: bool

    def public(self) -> dict[str, bool]:
        return asdict(self)

    def require(self, capability: str) -> None:
        if not getattr(self, capability):
            raise BookWorldError("feature_disabled", "This book feature is disabled; existing data is retained")


def load_features(environ: Mapping[str, str] | None = None) -> BookWorldFeatures:
    environ = os.environ if environ is None else environ

    def enabled(name: str) -> bool:
        return environ.get(name, "1") == "1"

    characters = enabled("OCTOPUS_BOOK_WORLD_ENABLED")
    single_chat = characters and enabled("OCTOPUS_BOOK_SINGLE_CHAT_ENABLED")
    return BookWorldFeatures(
        characters=characters,
        single_chat=single_chat,
        group_chat=single_chat and enabled("OCTOPUS_BOOK_GROUP_CHAT_ENABLED"),
        automatic_import=characters and enabled("OCTOPUS_BOOK_AUTO_IMPORT_ENABLED"),
    )


@lru_cache(maxsize=1)
def get_features() -> BookWorldFeatures:
    return load_features()


async def recover_disabled_workspace(root) -> None:
    features = get_features()
    if not features.automatic_import:
        from .automatic import AutoImportService

        service = await asyncio.to_thread(AutoImportService, root)
        await asyncio.to_thread(service.recover)
    if not features.characters:
        from .lifecycle import BookLifecycleService

        lifecycle = await asyncio.to_thread(BookLifecycleService, root)
        await asyncio.to_thread(lifecycle.interrupt_builds)


def require_world_action(action: str) -> None:
    features = get_features()
    if action in ("retry_auto_import", "restart_auto_import", "continue_auto_import"):
        features.require("automatic_import")
    elif action in (
        "start_discovery", "retry_build", "resume_build", "start_persona", "create_revision",
        "save_extension", "start_expression_set", "resume_expression_set", "retry_expression_set",
    ):
        features.require("characters")


def require_room_action(action: str, *, group_room: bool = False, revocation: bool = False) -> None:
    if revocation or action not in (
        "create_single_room", "create_group_room", "add_members", "set_member",
        "submit_turn", "resume_round", "set_discussion", "summarize_room", "reset_memory",
    ):
        return
    features = get_features()
    features.require("single_chat")
    if group_room or action in ("create_group_room", "add_members"):
        features.require("group_chat")
