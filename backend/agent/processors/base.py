"""Base message processor."""
from abc import ABC, abstractmethod

from backend.core.events.types import InboundMessage, OutboundMessage


class MessageProcessor(ABC):
    """Abstract base class for message processors."""

    def __init__(self, agent_loop):
        self.agent_loop = agent_loop

    @abstractmethod
    def can_process(self, msg: InboundMessage) -> bool:
        """Check if this processor can handle the given message."""
        ...

    @abstractmethod
    async def process(self, msg: InboundMessage, session_key: str | None = None) -> OutboundMessage | None:
        """Process the message and return a response, or None."""
        ...
