"""Event types for the message bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class MessageContentItem:
    """Single item in a multi-modal message."""

    type: str  # "text", "image", "image_url", "file"
    text: str | None = None  # For type="text"
    image_path: str | None = None  # For type="image" (local path)
    image_url: str | None = None  # For type="image_url" (URL)
    file_path: str | None = None  # For type="file" (local path)
    file_name: str | None = None  # For type="file"
    mime_type: str | None = None  # For type="file"
    file_size: int | None = None  # For type="file"


@dataclass
class InboundMessage:
    """Message received from a chat channel."""

    channel: str  # feishu, desktop, etc.
    sender_id: str  # User identifier
    chat_id: str  # Chat/channel identifier
    content: str | list[MessageContentItem]  # Message text or multi-modal content
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)  # Media URLs (deprecated, use content instead)
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data
    message_type: str = "normal"  # Message type for routing/filtering

    @property
    def session_key(self) -> str:
        """Unique key for session identification."""
        return f"{self.channel}:{self.chat_id}"

    @property
    def is_multimodal(self) -> bool:
        """Check if message contains multi-modal content."""
        return isinstance(self.content, list)

    @property
    def text_content(self) -> str:
        """Extract plain text content from message."""
        if isinstance(self.content, str):
            return self.content
        # Extract text from multi-modal content
        texts = [item.text for item in self.content if item.type == "text" and item.text]
        return " ".join(texts)

    def get_images(self) -> list[MessageContentItem]:
        """Get all image content items."""
        if isinstance(self.content, str):
            return []
        return [item for item in self.content if item.type in ("image", "image_url")]
    
    def get_files(self) -> list[MessageContentItem]:
        """Get all file content items."""
        if isinstance(self.content, str):
            return []
        return [item for item in self.content if item.type == "file"]


@dataclass
class OutboundMessage:
    """Message to send to a chat channel."""
    
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentEvent:
    """Event emitted by the agent (start, finish, chunk, etc)."""
    
    event_type: str  # "agent_start", "agent_finish", "agent_chunk"
    data: Dict[str, Any] = field(default_factory=dict)
    channel: str = ""  # Source channel (desktop, feishu, etc.)

