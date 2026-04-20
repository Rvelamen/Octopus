"""Webhook channel implementation using aiohttp."""

import asyncio
import json
from typing import Any

from aiohttp import web
from loguru import logger

from backend.core.events.types import OutboundMessage
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel


class WebhookChannel(BaseChannel):
    """Generic webhook receiver channel."""

    name = "webhook"

    def __init__(self, config, bus: MessageBus):
        super().__init__(config, bus)
        self._port = getattr(self.config.config, "port", 8644)
        self._secret = getattr(self.config.config, "secret", "") or ""
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        """Start aiohttp webhook server."""
        self._running = True
        app = web.Application()
        app.router.add_post("/webhook", self._handle_webhook)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await self._site.start()

        logger.info(f"Webhook channel listening on 0.0.0.0:{self._port}")

    async def stop(self) -> None:
        """Stop webhook server."""
        self._running = False
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        logger.info("Webhook channel stopped")

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming webhook POST."""
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return web.Response(status=400, text="Invalid JSON")

        if self._secret:
            header_secret = request.headers.get("X-Webhook-Secret", "")
            if header_secret != self._secret:
                return web.Response(status=401, text="Unauthorized")

        chat_id = payload.get("chat_id", "webhook:default")
        sender_id = payload.get("sender_id", "webhook")
        content = payload.get("text", "") or payload.get("message", "")

        if content:
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                metadata={"webhook_payload": payload},
            )

        return web.Response(status=202, text="Accepted")

    async def send(self, msg: OutboundMessage) -> None:
        """Log webhook response (actual delivery depends on external integration)."""
        logger.info(f"[Webhook] Response for {msg.chat_id}: {msg.content[:200]}")
