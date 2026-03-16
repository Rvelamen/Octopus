"""Context builder for assembling agent prompts."""

import base64
import mimetypes
from pathlib import Path
from typing import Any

from loguru import logger

from backend.agent.memory import MemoryStore
from backend.extensions.loader import SkillsLoader
from backend.agent.loader import SubAgentLoader
from backend.core.providers.message_adapter import MessageAdapter


# Global agent loop reference
_agent_loop: "Any" = None


def set_agent_loop(loop: "Any") -> None:
    """Set global agent loop reference."""
    global _agent_loop
    _agent_loop = loop


def get_agent_loop() -> "Any":
    """Get global agent loop reference."""
    return _agent_loop


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.

    Assembles bootstrap files, memory, skills, subagents, and conversation history
    into a coherent prompt for the LLM.
    """

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "IDENTITY.md", "BOOTSTRAP.md"]
    SYSTEM_DIR = "system"  # Directory for system prompt files

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
        self.subagent_loader = SubAgentLoader(workspace)

    def _get_agents_dir(self) -> Path:
        """Get the agents directory path (workspace sibling).

        Returns:
            Path to agents directory.
        """
        # Agents directory is at the same level as workspace
        return self.workspace.parent / "agents"
    
    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        """
        Build the system prompt from bootstrap files, memory, skills, and subagents.
        
        Args:
            skill_names: Optional list of skills to include.
        
        Returns:
            Complete system prompt.
        """
        from datetime import datetime
        
        parts = []
        
        # Core identity
        parts.append(self._get_identity())

        # Real-time context - refreshed on every request
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S (%A)")

        parts.append(f"""# Current Context

**Current Time**: {current_time}""")
        
        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        
        # Memory context
        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        print(skills_summary)
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

```

{skills_summary}""")
        
        # 3. Available SubAgents: show summary for spawn tool
        subagents_summary = self.subagent_loader.build_agents_summary()
        if subagents_summary:
            parts.append(f"""# SubAgents

The following subagents are available for background task execution. Use the `spawn` tool with `agent_role` parameter to invoke a specific subagent.

{subagents_summary}

## Usage

To spawn a subagent with a specific role, use:
- `spawn` tool with `agent_role` parameter set to the subagent name
- If no `agent_role` is specified, the default subagent configuration will be used

Example: Spawn a code-reviewer subagent to review a file.
""")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self) -> str:
        """Get the core identity section."""
        workspace_path = str(self.workspace.expanduser().resolve())

        return f"""
## Workspace
Your workspace is at: {workspace_path}

"""
    
    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from agents/system directory."""
        parts = []
        agents_dir = self._get_agents_dir()
        system_dir = agents_dir / self.SYSTEM_DIR

        # Try loading from agents/system directory first, then fall back to workspace/system for backward compatibility
        for filename in self.BOOTSTRAP_FILES:
            # First try agents/system directory (new location)
            file_path = system_dir / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")
            else:
                # Fall back to workspace/system directory for backward compatibility
                file_path = self.workspace / self.SYSTEM_DIR / filename
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
                    parts.append(f"## {filename} Source Path: {file_path}\n\n{content}")

        return "\n\n".join(parts) if parts else ""
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str | list[dict[str, Any]],
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message (string or multi-modal content list).
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.
            channel: Current channel (feishu, desktop, etc.).
            chat_id: Current chat/user ID.

        Returns:
            List of messages including system prompt.
        """
        from datetime import datetime
        messages = []

        # System prompt
        system_prompt = self.build_system_prompt(skill_names)
        # logger.info(f"System prompt: {system_prompt}")
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"
        messages.append({"role": "system", "content": system_prompt})

        # History
        messages.extend(history)

        # Current time context - always include fresh timestamp with each message
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S (%A)")
        time_prefix = f"[Current Time: {now}]\n\n"

        # Current message (with optional image attachments)
        if isinstance(current_message, list):
            # Multi-modal content: prepend time prefix to first text item
            user_content = self._prepend_time_to_multimodal(current_message, time_prefix)
        else:
            # Text-only message
            user_content = self._build_user_content(time_prefix + current_message, media)
        messages.append({"role": "user", "content": user_content})
        # logger.info(f"User message: {messages}")
        return messages

    def _prepend_time_to_multimodal(
        self,
        content: list[dict[str, Any]],
        time_prefix: str
    ) -> list[dict[str, Any]]:
        """Prepend time prefix to the first text item in multi-modal content."""
        result = []
        time_added = False
        for item in content:
            if item["type"] == "text" and not time_added:
                result.append({"type": "text", "text": time_prefix + item["text"]})
                time_added = True
            else:
                result.append(item)
        if not time_added:
            # No text item found, add time as first item
            result.insert(0, {"type": "text", "text": time_prefix.strip()})
        return result

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text
        
        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        
        if not images:
            return text
        return images + [{"type": "text", "text": text}]
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str,
        provider_type: str = "openai"
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.

        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
            provider_type: Provider type for message format adaptation.

        Returns:
            Updated message list.
        """
        # Use MessageAdapter to create properly formatted tool result
        tool_msg = MessageAdapter.create_tool_result_message(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            result=result,
            provider_type=provider_type
        )
        messages.append(tool_msg)
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        provider_type: str = "openai"
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.

        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
            provider_type: Provider type ("openai", "anthropic", etc.).

        Returns:
            Updated message list.
        """
        # Use MessageAdapter to create properly formatted assistant message
        msg = MessageAdapter.create_assistant_message(
            content=content,
            tool_calls=tool_calls,
            provider_type=provider_type
        )
        messages.append(msg)
        return messages
