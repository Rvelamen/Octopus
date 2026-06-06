"""WebSocket message handlers for Desktop channel."""

from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import WSMessage
from backend.core.events.bus import MessageBus

# Import handlers from extensions (unified extension system)


class MessageHandler:
    """Base class for message handlers."""

    def __init__(self, bus: MessageBus):
        self.bus = bus

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Handle a message. Must be implemented by subclasses."""
        raise NotImplementedError

    async def handle_validated(
        self, websocket: WebSocket, message: WSMessage, validated: Any
    ) -> None:
        """Handle a validated Pydantic model.

        Subclasses should override this to consume typed payloads.
        Default implementation raises so that the registry falls back to `handle`.
        """
        raise NotImplementedError

    async def send_response(self, websocket: WebSocket, message: WSMessage) -> None:
        """Send a response back to the client."""
        try:
            await websocket.send_json(message.to_dict())
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
