"""Message bus module for decoupled channel-agent communication."""

from backend.core.events.types import InboundMessage, OutboundMessage, AgentEvent
from backend.core.events.bus import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage", "AgentEvent"]
