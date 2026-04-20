"""Slack channel implementation using slack-bolt Socket Mode."""

import asyncio
from typing import Any

from loguru import logger

from backend.core.events.types import OutboundMessage
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel

try:
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False
    AsyncApp = Any
    AsyncSocketModeHandler = Any


class SlackChannel(BaseChannel):
    """Slack channel using Socket Mode."""

    name = "slack"

    def __init__(self, config, bus: MessageBus):
        super().__init__(config, bus)
        self._bot_token = getattr(self.config.config, "bot_token", "") or ""
        self._app_token = getattr(self.config.config, "app_token", "") or ""
        self._app: Any = None
        self._handler: Any = None
        self._handler_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start Slack Socket Mode client."""
        if not SLACK_AVAILABLE:
            logger.error("slack-bolt not installed. Run: pip install slack-bolt")
            return
        if not self._bot_token or not self._app_token:
            logger.error("Slack bot_token and app_token not configured")
            return

        self._running = True
        self._app = AsyncApp(token=self._bot_token)

        @self._app.event("message")
        async def handle_message(event, say, client):
            await self._on_event(event)

        self._handler = AsyncSocketModeHandler(self._app, self._app_token)
        self._handler_task = asyncio.create_task(self._handler.start_async())
        logger.info("Slack channel started")

    async def stop(self) -> None:
        """Stop Slack channel."""
        self._running = False
        if self._handler:
            try:
                await self._handler.close_async()
            except Exception as e:
                logger.warning(f"Error closing Slack handler: {e}")
        if self._handler_task:
            self._handler_task.cancel()
            try:
                await self._handler_task
            except asyncio.CancelledError:
                pass
        logger.info("Slack channel stopped")

    async def _on_event(self, event: dict) -> None:
        """Process incoming Slack message event."""
        if event.get("bot_id"):
            return
        if event.get("subtype"):
            return

        sender_id = event.get("user", "")
        chat_id = event.get("channel", "")
        content = event.get("text", "")

        if not content:
            return

        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata={"thread_ts": event.get("thread_ts")},
        )

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Slack."""
        if not self._app or not self._app.client:
            logger.warning("Slack app not initialized")
            return

        try:
            kwargs = {"channel": msg.chat_id, "text": msg.content}
            if msg.metadata and msg.metadata.get("thread_ts"):
                kwargs["thread_ts"] = msg.metadata["thread_ts"]
            await self._app.client.chat_postMessage(**kwargs)
            logger.debug(f"Slack message sent to {msg.chat_id}")
        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")
