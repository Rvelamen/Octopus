"""One canonical/expression model worker per workspace, shared by manual and auto paths."""

import asyncio
from pathlib import Path

from .storage import workspace_identity

_slots: dict[tuple[asyncio.AbstractEventLoop, str], asyncio.Semaphore] = {}


def build_slot(root: Path) -> asyncio.Semaphore:
    return _slots.setdefault(
        (asyncio.get_running_loop(), workspace_identity(root)), asyncio.Semaphore(1)
    )
