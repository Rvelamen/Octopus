"""WebSocket message handlers for Desktop channel - Chat handler."""

import asyncio
import uuid

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.core.events.types import InboundMessage, MessageContentItem
from backend.core.events.bus import MessageBus


class ChatHandler(MessageHandler):
    """Handle chat messages from clients."""

    def __init__(self, bus: MessageBus, pending_responses: dict[str, asyncio.Queue], image_service=None):
        super().__init__(bus)
        self.pending_responses = pending_responses
        self.image_service = image_service

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Process a chat message and forward to agent."""
        content = message.data.get("content", "")
        images = message.data.get("images", [])
        files = message.data.get("files", [])

        instance_id = message.data.get("instance_id")

        request_id = message.request_id or str(uuid.uuid4())

        response_queue = asyncio.Queue()
        self.pending_responses[request_id] = response_queue

        await self.send_response(websocket, WSMessage(
            type=MessageType.ACK,
            request_id=request_id,
            data={"status": "received"}
        ))

        metadata = {
            "request_id": request_id,
            "websocket_client": id(websocket)
        }
        if instance_id:
            metadata["instance_id"] = instance_id
            logger.info(f"Chat message with instance_id: {instance_id}")

        if images or files:
            content_items = []
            if content.strip():
                content_items.append(MessageContentItem(type="text", text=content))
            for img in images:
                img_path = img.get("path", "")
                if img_path:
                    content_items.append(MessageContentItem(type="image", image_path=img_path))
            for file in files:
                file_path = file.get("path", "")
                file_name = file.get("name", "unknown")
                mime_type = file.get("mime_type", "application/octet-stream")
                file_size = file.get("size", 0)
                if file_path:
                    content_items.append(MessageContentItem(
                        type="file",
                        file_path=file_path,
                        file_name=file_name,
                        mime_type=mime_type,
                        file_size=file_size
                    ))
            processed_content = content_items
        else:
            processed_content = content

        msg = InboundMessage(
            channel="desktop",
            sender_id="user",
            chat_id="desktop_session",
            content=processed_content,
            metadata=metadata
        )

        try:
            await self.bus.publish_inbound(msg)
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            await self._send_error(websocket, request_id, f"Failed to process message: {e}")
            del self.pending_responses[request_id]

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        """Send error response."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
