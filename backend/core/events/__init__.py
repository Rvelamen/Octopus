"""Message bus module for decoupled channel-agent communication."""

from backend.core.events.bus import MessageBus
from backend.core.events.types import AgentEvent, InboundMessage, OutboundMessage

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage", "AgentEvent"]
