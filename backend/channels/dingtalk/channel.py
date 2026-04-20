"""DingTalk channel implementation using dingtalk-stream SDK."""

import asyncio
import uuid
from typing import Any

import httpx
from loguru import logger

from backend.core.events.types import OutboundMessage
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel

try:
    import dingtalk_stream
    from dingtalk_stream import ChatbotHandler, ChatbotMessage
    DINGTALK_AVAILABLE = True
except ImportError:
    DINGTALK_AVAILABLE = False
    dingtalk_stream = None
    ChatbotHandler = object
    ChatbotMessage = Any


class _DingTalkHandler(ChatbotHandler if DINGTALK_AVAILABLE else object):
    """Handler that bridges dingtalk-stream callbacks to the async channel."""

    def __init__(self, channel: "DingTalkChannel", loop: asyncio.AbstractEventLoop):
        if DINGTALK_AVAILABLE:
            super().__init__()
        self._channel = channel
        self._loop = loop

    def process(self, message: ChatbotMessage):
        if self._loop is None or self._loop.is_closed():
            logger.error("[DingTalk] Event loop unavailable")
            if DINGTALK_AVAILABLE:
                return dingtalk_stream.AckMessage.STATUS_OK, "OK"
            return "OK", "OK"

        future = asyncio.run_coroutine_threadsafe(
            self._channel._on_message(message), self._loop
        )
        try:
            future.result(timeout=60)
        except Exception:
            logger.exception("[DingTalk] Error processing message")

        if DINGTALK_AVAILABLE:
            return dingtalk_stream.AckMessage.STATUS_OK, "OK"
        return "OK", "OK"


class DingTalkChannel(BaseChannel):
    """DingTalk channel using Stream Mode (WebSocket)."""

    name = "dingtalk"

    def __init__(self, config, bus: MessageBus):
        super().__init__(config, bus)
        self._client_id = getattr(self.config.config, "client_id", "") or ""
        self._client_secret = getattr(self.config.config, "client_secret", "") or ""
        self._stream_client: Any = None
        self._stream_task: asyncio.Task | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._session_webhooks: dict[str, str] = {}

    async def start(self) -> None:
        """Start DingTalk Stream client."""
        if not DINGTALK_AVAILABLE:
            logger.error("dingtalk-stream not installed. Run: pip install dingtalk-stream")
            return
        if not self._client_id or not self._client_secret:
            logger.error("DingTalk client_id and client_secret not configured")
            return

        self._running = True
        self._http_client = httpx.AsyncClient(timeout=30.0)

        credential = dingtalk_stream.Credential(self._client_id, self._client_secret)
        self._stream_client = dingtalk_stream.DingTalkStreamClient(credential)

        loop = asyncio.get_running_loop()
        handler = _DingTalkHandler(self, loop)
        self._stream_client.register_callback_handler(
            dingtalk_stream.ChatbotMessage.TOPIC, handler
        )

        self._stream_task = asyncio.create_task(self._run_stream())
        logger.info("DingTalk channel started")

    async def _run_stream(self) -> None:
        """Run blocking stream client with auto-reconnection."""
        backoff = [2, 5, 10, 30, 60]
        idx = 0
        while self._running:
            try:
                await asyncio.to_thread(self._stream_client.start)
            except asyncio.CancelledError:
                return
            except Exception as e:
                if not self._running:
                    return
                logger.warning(f"DingTalk stream error: {e}")
            if not self._running:
                return
            delay = backoff[min(idx, len(backoff) - 1)]
            logger.info(f"DingTalk reconnecting in {delay}s...")
            await asyncio.sleep(delay)
            idx += 1

    async def stop(self) -> None:
        """Stop DingTalk channel."""
        self._running = False
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        if self._http_client:
            await self._http_client.aclose()
        logger.info("DingTalk channel stopped")

    async def _on_message(self, message: ChatbotMessage) -> None:
        """Process incoming DingTalk message."""
        msg_id = getattr(message, "message_id", None) or uuid.uuid4().hex
        text = self._extract_text(message)
        if not text:
            return

        sender_id = getattr(message, "sender_id", "") or ""
        chat_id = getattr(message, "conversation_id", "") or sender_id

        session_webhook = getattr(message, "session_webhook", None) or ""
        if session_webhook and chat_id:
            self._session_webhooks[chat_id] = session_webhook

        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=text,
            metadata={"session_webhook": session_webhook, "message_id": msg_id},
        )

    @staticmethod
    def _extract_text(message: ChatbotMessage) -> str:
        """Extract plain text from DingTalk message."""
        text = getattr(message, "text", None) or ""
        if isinstance(text, dict):
            content = text.get("content", "").strip()
        else:
            content = str(text).strip()

        if not content:
            rich_text = getattr(message, "rich_text", None)
            if rich_text and isinstance(rich_text, list):
                parts = [
                    item["text"]
                    for item in rich_text
                    if isinstance(item, dict) and item.get("text")
                ]
                content = " ".join(parts).strip()
        return content

    async def send(self, msg: OutboundMessage) -> None:
        """Send markdown reply via DingTalk session webhook."""
        if not self._http_client:
            logger.warning("DingTalk HTTP client not initialized")
            return

        session_webhook = (
            msg.metadata.get("session_webhook") if msg.metadata else None
        )
        if not session_webhook:
            session_webhook = self._session_webhooks.get(msg.chat_id)
        if not session_webhook:
            logger.warning(f"No session_webhook for chat {msg.chat_id}")
            return

        payload = {
            "msgtype": "markdown",
            "markdown": {"title": "Octopus", "text": msg.content[:20000]},
        }

        try:
            resp = await self._http_client.post(
                session_webhook, json=payload, timeout=15.0
            )
            if resp.status_code >= 300:
                logger.warning(
                    f"DingTalk send failed: HTTP {resp.status_code} {resp.text[:200]}"
                )
        except Exception as e:
            logger.error(f"Error sending DingTalk message: {e}")
