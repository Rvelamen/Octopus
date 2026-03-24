"""WeChat ClawBot channel implementation using ilink API.

This channel integrates with WeChat's official ClawBot plugin,
allowing any Agent to receive and respond to WeChat messages.

Protocol: HTTP long polling + Token authentication
API Base: https://ilinkai.weixin.qq.com

Flow:
1. Call get_bot_qrcode?bot_type=3 to get QR code (no appid needed)
2. User scans QR code with WeChat
3. Poll get_qrcode_status?qrcode=<token> until confirmed
4. Receive bot_token on successful scan
5. Use bot_token for all subsequent API calls
"""

import asyncio
import json
import re
import os
from collections import OrderedDict
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from backend.core.events.types import OutboundMessage
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel


def markdown_to_plain_text(text: str) -> str:
    """Convert markdown-formatted text to plain text for WeChat delivery.
    
    Preserves newlines; strips markdown syntax.
    """
    if not text:
        return text
    
    result = text
    
    result = re.sub(r'```[^\n]*\n?([\s\S]*?)```', lambda m: m.group(1).strip(), result)
    
    result = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', result)
    
    result = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', result)
    
    result = re.sub(r'^\|[\s:|-]+\|$', '', result, flags=re.MULTILINE)
    result = re.sub(r'^\|(.+)\|$', lambda m: '  '.join(cell.strip() for cell in m.group(1).split('|')), result, flags=re.MULTILINE)
    
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    result = re.sub(r'\*([^*]+)\*', r'\1', result)
    result = re.sub(r'__([^_]+)__', r'\1', result)
    result = re.sub(r'_([^_]+)_', r'\1', result)
    result = re.sub(r'~~([^~]+)~~', r'\1', result)
    result = re.sub(r'`([^`]+)`', r'\1', result)
    result = re.sub(r'^#{1,6}\s+', '', result, flags=re.MULTILINE)
    result = re.sub(r'^[-*+]\s+', '• ', result, flags=re.MULTILINE)
    result = re.sub(r'^\d+\.\s+', '', result, flags=re.MULTILINE)
    result = re.sub(r'^---+\s*$', '──────────', result, flags=re.MULTILINE)
    result = re.sub(r'^\*\*\*+\s*$', '──────────', result, flags=re.MULTILINE)
    
    return result

WECHAT_API_BASE = "https://ilinkai.weixin.qq.com"
DEFAULT_BOT_TYPE = "3"
CHANNEL_VERSION = "3.2.0.109"
QR_STATUS_TIMEOUT = 5000

SESSION_EXPIRED_ERRCODE = -14
MAX_CONSECUTIVE_FAILURES = 3
BACKOFF_DELAY_MS = 30000
RETRY_DELAY_MS = 2000
SESSION_PAUSE_MINUTES = 60


def get_wechat_data_dir() -> Path:
    """Get the directory for persisting WeChat channel data."""
    from backend.utils.helpers import get_data_path
    wechat_dir = get_data_path() / "wechat"
    wechat_dir.mkdir(parents=True, exist_ok=True)
    return wechat_dir


def get_sync_buf_path() -> Path:
    """Get path to the sync buffer file."""
    return get_wechat_data_dir() / "sync_buf.json"


def load_sync_buf() -> str:
    """Load persisted get_updates_buf from disk."""
    sync_path = get_sync_buf_path()
    try:
        if sync_path.exists():
            data = json.loads(sync_path.read_text())
            buf = data.get("get_updates_buf", "")
            if buf:
                logger.info(f"Loaded sync buf ({len(buf)} bytes) from disk")
                return buf
    except Exception as e:
        logger.warning(f"Failed to load sync buf: {e}")
    return ""


def save_sync_buf(buf: str) -> None:
    """Persist get_updates_buf to disk."""
    if not buf:
        return
    sync_path = get_sync_buf_path()
    try:
        sync_path.write_text(json.dumps({"get_updates_buf": buf}))
        logger.debug(f"Saved sync buf ({len(buf)} bytes) to disk")
    except Exception as e:
        logger.warning(f"Failed to save sync buf: {e}")


class WechatChannel(BaseChannel):
    """
    WeChat ClawBot channel using HTTP long polling.

    Uses WeChat's official ilink API to:
    1. Get bot QR code for connection (no appid required)
    2. Poll for QR code scan status
    3. Long-poll for incoming messages
    4. Send reply messages

    Requires:
    - bot_token obtained after scanning QR code
    """

    name = "wechat"

    def __init__(self, config, bus: MessageBus):
        super().__init__(config, bus)
        self._client: httpx.AsyncClient | None = None
        self._poll_task: asyncio.Task | None = None
        self._dispatch_task: asyncio.Task | None = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()
        self._context_tokens: dict[str, str] = {}
        self._typing_tickets: dict[str, str] = {}
        self._get_updates_buf: str = ""
        self._consecutive_failures: int = 0
        self._session_paused_until: float = 0

        self.bus.subscribe_outbound("wechat", self._on_outbound_message)
        self.bus.subscribe_event(self._on_agent_event)

    async def start(self) -> None:
        """Start the WeChat bot with HTTP long polling."""
        logger.info("WechatChannel.start() called")
        bot_token = getattr(self.config.config, 'bot_token', None)
        if not bot_token:
            logger.warning("WeChat bot_token not configured. Please scan QR code first.")
            return

        self._running = True
        self._client = httpx.AsyncClient(timeout=60.0)
        self._get_updates_buf = load_sync_buf()
        self._consecutive_failures = 0
        self._session_paused_until = 0

        saved_tokens = getattr(self.config.config, 'context_tokens', None) or {}
        if saved_tokens:
            self._context_tokens = saved_tokens
            logger.info(f"Loaded {len(self._context_tokens)} context tokens from config")

        logger.info(f"WeChat ClawBot channel started with token: {bot_token[:20]}...")
        logger.info("Starting message polling...")

        while self._running:
            try:
                await self._poll_messages()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message polling: {e}")
            await asyncio.sleep(3)

    async def stop(self) -> None:
        """Stop the WeChat bot."""
        self._running = False
        self._session_paused_until = 0

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.aclose()

        logger.info("WeChat channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through WeChat."""
        bot_token = getattr(self.config.config, 'bot_token', None)
        if not self._client or not bot_token:
            logger.warning("WeChat client not initialized")
            return

        context_token = self._context_tokens.get(msg.chat_id)
        if not context_token:
            logger.warning(f"No context token for chat {msg.chat_id}")
            return

        plain_content = markdown_to_plain_text(msg.content)
        
        import uuid
        client_id = f"openclaw-weixin-{uuid.uuid4().hex[:8]}"

        payload = {
            "msg": {
                "from_user_id": "",
                "to_user_id": msg.chat_id,
                "client_id": client_id,
                "message_type": 2,
                "message_state": 2,
                "context_token": context_token,
                "item_list": [
                    {
                        "type": 1,
                        "text_item": {
                            "text": plain_content
                        }
                    }
                ]
            },
            "base_info": self._build_base_info()
        }
        
        body_str = json.dumps(payload, ensure_ascii=False)

        try:
            response = await self._client.post(
                f"{WECHAT_API_BASE}/ilink/bot/sendmessage",
                content=body_str,
                headers={
                    "Content-Type": "application/json",
                    "AuthorizationType": "ilink_bot_token",
                    "Authorization": f"Bearer {bot_token.strip()}",
                    "X-WECHAT-UIN": self._random_wechat_uin(),
                }
            )

            data = response.json()
            ret = data.get("ret")
            errcode = data.get("errcode")
            if (ret is not None and ret != 0) or (errcode is not None and errcode != 0):
                logger.error(f"Failed to send WeChat message: {data}")
            else:
                logger.debug(f"WeChat message sent to {msg.chat_id}")

        except Exception as e:
            logger.error(f"Error sending WeChat message: {e}")

    async def send_typing(self, chat_id: str, typing: bool = True) -> None:
        """Send typing indicator to a user."""
        bot_token = getattr(self.config.config, 'bot_token', None)
        if not self._client or not bot_token:
            return

        typing_ticket = self._typing_tickets.get(chat_id)
        if not typing_ticket:
            typing_ticket = await self._get_typing_ticket(chat_id)
            if not typing_ticket:
                return

        status = 1 if typing else 2

        payload = {
            "ilink_user_id": chat_id,
            "typing_ticket": typing_ticket,
            "status": status,
            "base_info": self._build_base_info()
        }

        try:
            response = await self._client.post(
                f"{WECHAT_API_BASE}/ilink/bot/sendtyping",
                content=json.dumps(payload),
                headers={
                    "Content-Type": "application/json",
                    "AuthorizationType": "ilink_bot_token",
                    "Authorization": f"Bearer {bot_token.strip()}",
                    "X-WECHAT-UIN": self._random_wechat_uin(),
                }
            )

            data = response.json()
            ret = data.get("ret")
            if ret is not None and ret != 0:
                logger.warning(f"Failed to send typing indicator: {data}")

        except Exception as e:
            logger.warning(f"Error sending typing indicator: {e}")

    async def _get_typing_ticket(self, chat_id: str) -> str | None:
        """Get typing ticket for a user via getconfig API."""
        bot_token = getattr(self.config.config, 'bot_token', None)
        if not self._client or not bot_token:
            return None

        context_token = self._context_tokens.get(chat_id, "")

        payload = {
            "ilink_user_id": chat_id,
            "context_token": context_token,
            "base_info": self._build_base_info()
        }

        try:
            response = await self._client.post(
                f"{WECHAT_API_BASE}/ilink/bot/getconfig",
                content=json.dumps(payload),
                headers={
                    "Content-Type": "application/json",
                    "AuthorizationType": "ilink_bot_token",
                    "Authorization": f"Bearer {bot_token.strip()}",
                    "X-WECHAT-UIN": self._random_wechat_uin(),
                }
            )

            data = response.json()
            typing_ticket = data.get("typing_ticket", "")
            if typing_ticket:
                self._typing_tickets[chat_id] = typing_ticket
                return typing_ticket

        except Exception as e:
            logger.warning(f"Error getting typing ticket: {e}")

        return None

    async def _on_outbound_message(self, msg: OutboundMessage) -> None:
        """Handle outbound message from agent."""
        if msg.channel != "wechat":
            return
        logger.info(f"[WechatChannel] Received outbound message for {msg.chat_id}: {msg.content[:50]}...")
        await self.send(msg)

    async def _on_agent_event(self, event) -> None:
        """Handle agent events for typing indicator."""
        if event.channel != "wechat":
            return

        if event.event_type == "agent_start":
            chat_id = event.data.get("session", "").split(":")[-1] if event.data.get("session") else ""
            if chat_id:
                await self.send_typing(chat_id, typing=True)
        elif event.event_type == "agent_finish":
            chat_id = event.data.get("session", "").split(":")[-1] if event.data.get("session") else ""
            if chat_id:
                await self.send_typing(chat_id, typing=False)

    def _build_base_info(self) -> dict:
        """Build base_info for API requests."""
        return {"channel_version": CHANNEL_VERSION}

    def _random_wechat_uin(self) -> str:
        """Generate a random WeChat UIN (base64 encoded uint32)."""
        import random
        import base64
        uint32 = random.randint(0, 4294967295)
        return base64.b64encode(str(uint32).encode('utf-8')).decode('utf-8')

    def _save_context_tokens(self) -> None:
        """Save context tokens to database."""
        try:
            from backend.data import Database
            from backend.data.provider_store import ChannelConfigRepository

            db = Database()
            repo = ChannelConfigRepository(db)
            config = repo.get_channel_config("wechat")
            if config:
                config_json = config.config_json if isinstance(config.config_json, dict) else json.loads(config.config_json or "{}")
                config_json["contextTokens"] = self._context_tokens
                repo.create_or_update_channel_config(
                    channel_name="wechat",
                    channel_type="wechat",
                    enabled=config.enabled,
                    app_id=config.app_id,
                    app_secret=config.app_secret,
                    encrypt_key=config.encrypt_key,
                    verification_token=config.verification_token,
                    allow_from=config.allow_from,
                    config_json=config_json,
                )
                logger.debug(f"Saved {len(self._context_tokens)} context tokens to database")
        except Exception as e:
            logger.warning(f"Failed to save context tokens: {e}")

    async def _poll_messages(self) -> None:
        """Long-poll for incoming messages from WeChat."""
        bot_token = getattr(self.config.config, 'bot_token', None)
        if not self._client or not bot_token:
            logger.warning("WeChat poll: missing client or token")
            return

        if self._session_paused_until > 0:
            remaining = self._session_paused_until - asyncio.get_event_loop().time()
            if remaining > 0:
                logger.debug(f"WeChat session paused, waiting {remaining:.0f}s before retry")
                await asyncio.sleep(min(remaining, 5))
                return
            self._session_paused_until = 0

        logger.debug("WeChat polling for messages...")
        try:
            body = json.dumps({
                "get_updates_buf": self._get_updates_buf,
                "base_info": self._build_base_info(),
            })

            response = await self._client.post(
                f"{WECHAT_API_BASE}/ilink/bot/getupdates",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "AuthorizationType": "ilink_bot_token",
                    "Authorization": f"Bearer {bot_token.strip()}",
                    "X-WECHAT-UIN": self._random_wechat_uin(),
                },
                timeout=40.0
            )

            data = response.json()

            ret = data.get("ret")
            errcode = data.get("errcode")
            errmsg = data.get("errmsg", data.get("msg", ""))

            is_api_error = (ret is not None and ret != 0) or (errcode is not None and errcode != 0)

            if is_api_error:
                if errcode == SESSION_EXPIRED_ERRCODE:
                    pause_ms = SESSION_PAUSE_MINUTES * 60 * 1000
                    self._session_paused_until = asyncio.get_event_loop().time() + (pause_ms / 1000)
                    logger.warning(
                        f"WeChat session expired (errcode={errcode}), pausing for {SESSION_PAUSE_MINUTES} min"
                    )
                    self._consecutive_failures = 0
                    return
                else:
                    logger.warning(f"WeChat poll error: {errmsg} (errcode={errcode})")

                self._consecutive_failures += 1
                if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.warning(f"WeChat: {MAX_CONSECUTIVE_FAILURES} consecutive failures, backing off 30s")
                    await asyncio.sleep(BACKOFF_DELAY_MS / 1000)
                    self._consecutive_failures = 0
                return

            self._consecutive_failures = 0

            new_buf = data.get("get_updates_buf", "")
            if new_buf and new_buf != self._get_updates_buf:
                self._get_updates_buf = new_buf
                save_sync_buf(new_buf)

            messages = data.get("msgs", [])

            if messages:
                logger.info(f"Received {len(messages)} WeChat messages")

            for msg in messages:
                await self._handle_wechat_message(msg)

        except httpx.TimeoutException:
            pass
        except Exception as e:
            logger.error(f"Error polling messages: {e}")
            self._consecutive_failures += 1

    async def _handle_wechat_message(self, msg: dict[str, Any]) -> None:
        """Handle an incoming WeChat message."""
        try:
            message_id = str(msg.get("message_id", msg.get("seq", "")))

            if message_id in self._processed_message_ids:
                return
            self._processed_message_ids[message_id] = None

            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)

            sender_id = msg.get("from_user_id", "unknown")
            to_user_id = msg.get("to_user_id", "")
            context_token = msg.get("context_token", "")
            item_list = msg.get("item_list", [])

            if context_token:
                self._context_tokens[sender_id] = context_token
                self._save_context_tokens()

            content = ""
            for item in item_list:
                if item.get("type") == 1:
                    text_item = item.get("text_item", {})
                    content = text_item.get("text", "")
                    break

            if not content:
                return

            logger.info(f"WeChat message from {sender_id}: {content[:50]}...")

            await self._handle_message(
                sender_id=sender_id,
                chat_id=sender_id,
                content=content,
                metadata={
                    "message_id": message_id,
                    "context_token": context_token,
                    "to_user_id": to_user_id,
                }
            )

        except Exception as e:
            logger.error(f"Error handling WeChat message: {e}")

    async def get_qrcode(self) -> dict[str, Any]:
        """Get bot QR code for WeChat connection (no appid needed)."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=30.0)

        try:
            url = f"{WECHAT_API_BASE}/ilink/bot/get_bot_qrcode?bot_type={DEFAULT_BOT_TYPE}"
            response = await self._client.get(url)

            data = response.json()

            qrcode = data.get("qrcode")
            qrcode_url = data.get("qrcode_img_content")

            if not qrcode:
                return {"success": False, "error": "Failed to get QR code"}

            return {
                "success": True,
                "qrcode_url": qrcode_url,
                "qrcode_token": qrcode
            }

        except Exception as e:
            logger.error(f"Error getting WeChat QR code: {e}")
            return {"success": False, "error": str(e)}

    async def check_qrcode_status(self, qrcode_token: str) -> dict[str, Any]:
        """Check if QR code has been scanned."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=30.0)

        try:
            url = f"{WECHAT_API_BASE}/ilink/bot/get_qrcode_status?qrcode={qrcode_token}"
            response = await self._client.get(url)

            data = response.json()

            status = data.get("status", "wait")
            bot_token = data.get("bot_token")

            return {
                "success": True,
                "status": status,
                "bot_token": bot_token,
                "ilink_bot_id": data.get("ilink_bot_id"),
                "ilink_user_id": data.get("ilink_user_id"),
            }

        except Exception as e:
            logger.error(f"Error checking WeChat QR code status: {e}")
            return {"success": False, "error": str(e)}
