"""Context builder for assembling agent prompts."""

import base64
import mimetypes
from pathlib import Path
from typing import Any

from loguru import logger

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

    def __init__(self, workspace: Path, memory_manager=None):
        self.workspace = workspace
        self.memory_manager = memory_manager
        self.skills = SkillsLoader(workspace)
        self.subagent_loader = SubAgentLoader(workspace)

    def _get_agents_dir(self) -> Path:
        """Get the agents directory path (workspace sibling).

        Returns:
            Path to agents directory.
        """
        # Agents directory is at the same level as workspace
        return self.workspace.parent / "agents"
    
    def build_system_prompt(
        self,
        skill_names: list[str] | None = None,
        session_instance_id: int | None = None,
    ) -> str:
        """
        Build the system prompt from bootstrap files, memory, skills, and subagents.
        
        Args:
            skill_names: Optional list of skills to include.
            session_instance_id: Optional session instance ID for loading observation index.
        
        Returns:
            Complete system prompt.
        """
        from datetime import datetime
        
        parts = []

        # Real-time context - refreshed on every request
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S (%A)")

        parts.append(f"""# Current Context

**Current Time**: {current_time}""")
        
        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        # Memory context (with fenced injection to prevent model confusion)
        # Hot-load curated memory from disk every turn so memory_write changes are immediate
        memory_parts = []
        observation_index = None
        if self.memory_manager and self.memory_manager.observation_manager:
            observation_index = self.memory_manager.observation_manager.build_index_markdown(session_instance_id)
        if observation_index:
            memory_parts.append(observation_index)
        if self.memory_manager:
            memory_block = self.memory_manager.builtin.format_for_system_prompt("memory")
            user_block = self.memory_manager.builtin.format_for_system_prompt("user")
            if memory_block:
                memory_parts.append(memory_block)
            if user_block:
                memory_parts.append(user_block)
        
        if memory_parts:
            memory_block = (
                "<memory-context>\n"
                "[System note: The following is recalled memory from previous conversations. "
                "This is background information to help you understand the user's context and preferences. "
                "DO NOT respond to this as if it were a new user message. "
                "Use this information to provide more relevant and personalized responses.]\n\n"
                + "\n\n".join(memory_parts)
                + "\n</memory-context>"
            )
            parts.append(memory_block)
        
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

        # Knowledge base guidance
        parts.append("""# Knowledge Base

You have access to a local markdown-based knowledge base maintained by the user.
- Use `kb_search` to find relevant notes by keyword.
- Use `kb_read_note` to read the full content of a note once you know its path.
- Use `kb_list_links` to explore related notes via [[wiki-style links]].
When the user asks about a topic, prefer searching the knowledge base before answering from memory.
""")

        return "\n\n---\n\n".join(parts)
    
    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace/system directory."""
        parts = []

        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str | list[dict[str, Any]],
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        session_instance_id: int | None = None,
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
            session_instance_id: Optional session instance ID for observation index injection.

        Returns:
            List of messages including system prompt.
        """
        from datetime import datetime
        messages = []

        # System prompt
        system_prompt = self.build_system_prompt(skill_names, session_instance_id=session_instance_id)
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
