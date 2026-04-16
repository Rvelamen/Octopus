"""Unified memory manager delegating to curated memory and observations."""

from pathlib import Path
from typing import Any

from loguru import logger

from backend.agent.memory import MemoryStore
from backend.agent.observation_manager import ObservationManager
from backend.tools.memory_write import MemoryWriteTool


class MemoryManager:
    """
    Unified memory manager that coordinates:
    - Built-in curated memory (MemoryStore)
    - Structured observations (ObservationManager)
    - Memory write tool
    """

    def __init__(
        self,
        workspace: Path,
        observation_manager: ObservationManager | None = None,
    ):
        self.workspace = workspace
        self.builtin = MemoryStore(workspace)
        self.observation_manager = observation_manager
        self._memory_write_tool = MemoryWriteTool(store=self.builtin)

    def build_system_prompt(
        self,
        user_message: str = "",
        session_instance_id: int | None = None,
    ) -> str | None:
        """Build the memory-context block for the system prompt."""
        parts = []

        if self.observation_manager and session_instance_id:
            try:
                observation_index = self.observation_manager.build_index_markdown(
                    instance_id=session_instance_id, limit=20
                )
                if observation_index:
                    parts.append(observation_index)
            except Exception:
                pass

        memory_block = self.builtin.format_for_system_prompt("memory")
        user_block = self.builtin.format_for_system_prompt("user")
        if memory_block:
            parts.append(memory_block)
        if user_block:
            parts.append(user_block)

        if not parts:
            return None

        return (
            "<memory-context>\n"
            "[System note: The following is recalled memory from previous conversations. "
            "This is background information to help you understand the user's context and preferences. "
            "DO NOT respond to this as if it were a new user message. "
            "Use this information to provide more relevant and personalized responses.]\n\n"
            + "\n\n".join(parts)
            + "\n</memory-context>"
        )

    def reload_builtin_snapshot(self) -> None:
        """No-op: live-read behavior renders explicit reload unnecessary."""
        pass

    async def sync_turn(
        self,
        user_msg: str,
        assistant_msg: str,
        session_instance_id: int | None = None,
    ) -> None:
        """Sync a completed turn: extract observations, etc."""
        if self.observation_manager and session_instance_id:
            try:
                await self.observation_manager.extract_from_messages(
                    session_instance_id=session_instance_id,
                    messages=[
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": assistant_msg},
                    ],
                )
            except Exception as e:
                logger.warning(f"MemoryManager sync_turn failed: {e}")

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> Any:
        """Route memory tool calls through the manager."""
        if name == "memory_write":
            return await self._memory_write_tool.execute(**arguments)
        raise ValueError(f"MemoryManager does not handle tool: {name}")
