"""WeChat configuration handler for Desktop channel."""

import asyncio
import json
import io
from pathlib import Path
from typing import Any
import uuid

import httpx
import qrcode
from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.data.provider_store import ChannelConfigRepository
from backend.utils.helpers import get_data_path
from pydantic import ValidationError
from backend.channels.desktop.schemas import MESSAGE_TYPE_TO_SCHEMA

WECHAT_API_BASE = "https://ilinkai.weixin.qq.com"
DEFAULT_BOT_TYPE = "3"
QR_STATUS_TIMEOUT = 5000

_processing_confirmed = False
_confirmed_tokens = set()


class WechatConfigHandler:
    """Handler for WeChat QR code and connection status."""

    def __init__(self, bus, db, event_bus=None):
        self.db = db
        self.channel_repo = ChannelConfigRepository(db)
        self.event_bus = event_bus
        self._client: httpx.AsyncClient | None = None

        temp_dir = get_data_path() / "wechat_qrcodes"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir = temp_dir

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        # Validate inbound payload
        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        schema = MESSAGE_TYPE_TO_SCHEMA.get(msg_type_str)
        if schema is not None:
            try:
                validated = schema.model_validate(message.data)
                msg_data = validated.model_dump(mode="json", by_alias=True)
            except ValidationError as ve:
                logger.warning(f"Validation error for {msg_type_str}: {ve}")
                await websocket.send_json({'type': MessageType.ERROR.value, 'request_id': message.request_id, 'data': {'error': 'Invalid request data', 'details': ve.errors()}})
                return
        else:
            msg_data = message.data

        msg_type = message.type
        if hasattr(msg_type, 'value'):
            msg_type = msg_type.value

        request_id = message.request_id

        try:
            if msg_type == "wechat_get_qrcode":
                await self._get_qrcode(websocket, msg_data, request_id)
            elif msg_type == "wechat_check_status":
                await self._check_status(websocket, msg_data, request_id)
            elif msg_type == "wechat_clear_token":
                await self._clear_token(websocket, msg_data, request_id)
            else:
                logger.warning(f"Unknown WeChat message type: {msg_type}")
        except Exception as e:
            import traceback
            logger.error(f"WechatConfigHandler error: {e}\n{traceback.format_exc()}")
            await websocket.send_json({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "data": {"error": str(e)}
            })

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    def _generate_qr_code(self, url: str) -> bytes:
        """Generate QR code image from URL using qrcode library."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    async def _get_qrcode(self, websocket: WebSocket, data: dict, request_id: str = None):
        """Get WeChat QR code for connection (no appid needed)."""
        try:
            client = await self._get_client()
            url = f"{WECHAT_API_BASE}/ilink/bot/get_bot_qrcode?bot_type={DEFAULT_BOT_TYPE}"
            response = await client.get(url)

            result = response.json()
            logger.info(f"WeChat QR code response: {result.keys() if isinstance(result, dict) else result}")

            qrcode_token = result.get("qrcode")
            qrcode_url = result.get("qrcode_img_content")

            if not qrcode_token:
                await websocket.send_json({
                    "type": MessageType.WECHAT_QRCODE_RESULT.value,
                    "request_id": request_id,
                    "data": {
                        "success": False,
                        "error": "Failed to get QR code"
                    }
                })
                return

            if qrcode_url:
                try:
                    img_data = self._generate_qr_code(qrcode_url)

                    filename = f"wechat_qrcode_{uuid.uuid4().hex}.png"
                    local_path = self._temp_dir / filename
                    local_path.write_bytes(img_data)

                    local_qrcode_url = f"/wechat_qrcodes/{filename}"
                    logger.info(f"QR code saved locally: {local_path}")
                except Exception as img_err:
                    logger.warning(f"Failed to generate QR code locally: {img_err}")
                    local_qrcode_url = qrcode_url
            else:
                local_qrcode_url = None

            await websocket.send_json({
                "type": MessageType.WECHAT_QRCODE_RESULT.value,
                "request_id": request_id,
                "data": {
                    "success": True,
                    "qrcode_img_content": local_qrcode_url,
                    "qrcode_token": qrcode_token
                }
            })

        except Exception as e:
            logger.error(f"Error getting WeChat QR code: {e}")
            await websocket.send_json({
                "type": MessageType.WECHAT_QRCODE_RESULT.value,
                "request_id": request_id,
                "data": {
                    "success": False,
                    "error": str(e)
                }
            })

    async def _check_status(self, websocket: WebSocket, data: dict, request_id: str = None):
        """Check QR code scan status with long polling."""
        logger.info(f"WeChat check_status called with data: {data}")
        qrcode_token = data.get("qrcode_token", "")
        channel_name = data.get("channelName", "wechat")

        if not qrcode_token:
            await websocket.send_json({
                "type": MessageType.WECHAT_STATUS_RESULT.value,
                "request_id": request_id,
                "data": {
                    "success": False,
                    "error": "QR code token is required"
                }
            })
            return

        try:
            client = await self._get_client()
            url = f"{WECHAT_API_BASE}/ilink/bot/get_qrcode_status?qrcode={qrcode_token}"

            response = await client.get(url, timeout=QR_STATUS_TIMEOUT)

            result = response.json()
            raw_status = result.get("status", "wait")
            
            logger.info(f"WeChat QR status response: {result}")
            logger.info(f"Raw status from WeChat API: '{raw_status}'")
            
            status_map = {
                "wait": "waiting",
                "scaned": "scaned",
                "scanned": "scaned",
                "confirmed": "confirmed",
                "expired": "expired",
                "cancelled": "cancelled",
                "cancel": "cancelled",
            }
            status = status_map.get(raw_status, raw_status)
            logger.info(f"Mapped status: '{status}' (from '{raw_status}')")
            
            bot_token = result.get("bot_token", "")
            ilink_bot_id = result.get("ilink_bot_id", "")
            ilink_user_id = result.get("ilink_user_id", "")

            if status == "confirmed" and bot_token:
                global _processing_confirmed, _confirmed_tokens
                
                token_already_processed = qrcode_token in _confirmed_tokens
                if token_already_processed:
                    logger.info(f"QR token {qrcode_token[:8]}... already confirmed, skipping duplicate")
                    await websocket.send_json({
                        "type": MessageType.WECHAT_STATUS_RESULT.value,
                        "request_id": request_id,
                        "data": {
                            "success": True,
                            "status": "confirmed",
                            "bot_token": bot_token,
                            "ilink_bot_id": ilink_bot_id,
                            "ilink_user_id": ilink_user_id
                        }
                    })
                    return
                elif _processing_confirmed:
                    logger.info(f"Already processing another confirmed status, skipping")
                    await websocket.send_json({
                        "type": MessageType.WECHAT_STATUS_RESULT.value,
                        "request_id": request_id,
                        "data": {
                            "success": True,
                            "status": "confirmed",
                            "bot_token": bot_token,
                            "ilink_bot_id": ilink_bot_id,
                            "ilink_user_id": ilink_user_id
                        }
                    })
                    return
                
                _processing_confirmed = True
                _confirmed_tokens.add(qrcode_token)
                logger.info(f"Processing confirmed status for QR token {qrcode_token[:8]}...")
                try:
                    self.channel_repo.create_or_update_channel_config(
                        channel_name=channel_name,
                        channel_type="wechat",
                        enabled=True,
                        app_id=ilink_bot_id,
                        app_secret=bot_token,
                    )
                    logger.info(f"WeChat channel {channel_name} connected: bot_id={ilink_bot_id}")

                    from backend.channels.manager import ChannelManager
                    cm = ChannelManager._get_global_instance()
                    if cm:
                        if channel_name in cm.channels:
                            old_channel = cm.channels[channel_name]
                            old_poll_task = getattr(old_channel, '_poll_task', None)
                            if old_poll_task:
                                old_channel._running = False
                                old_poll_task.cancel()
                                try:
                                    await old_poll_task
                                except asyncio.CancelledError:
                                    pass
                            
                            del cm.channels[channel_name]
                            logger.info(f"Old channel {channel_name} stopped and removed")
                        
                        await asyncio.sleep(0.3)
                        
                        if cm.ensure_channel(channel_name):
                            new_channel = cm.channels.get(channel_name)
                            if new_channel:
                                new_channel._session_paused_until = 0
                                new_channel._consecutive_failures = 0
                                logger.info(f"Reset heartbeat state for channel {channel_name}")
                                await cm.start_channel(channel_name)
                        else:
                            logger.info(f"Channel {channel_name} not found in manager")
                finally:
                    _processing_confirmed = False

            await websocket.send_json({
                "type": MessageType.WECHAT_STATUS_RESULT.value,
                "request_id": request_id,
                "data": {
                    "success": True,
                    "status": status,
                    "bot_token": bot_token if status == "confirmed" else None,
                    "ilink_bot_id": ilink_bot_id,
                    "ilink_user_id": ilink_user_id
                }
            })

        except httpx.TimeoutException:
            await websocket.send_json({
                "type": MessageType.WECHAT_STATUS_RESULT.value,
                "request_id": request_id,
                "data": {
                    "success": True,
                    "status": "wait"
                }
            })
        except Exception as e:
            logger.error(f"Error checking WeChat QR code status: {e}")
            await websocket.send_json({
                "type": MessageType.WECHAT_STATUS_RESULT.value,
                "request_id": request_id,
                "data": {
                    "success": False,
                    "error": str(e)
                }
            })

    async def _clear_token(self, websocket: WebSocket, data: dict, request_id: str = None):
        """Clear expired WeChat token and reset channel config."""
        channel_name = data.get("channelName", "wechat")

        try:
            from backend.channels.wechat.channel import get_sync_buf_path

            sync_path = get_sync_buf_path()
            if sync_path.exists():
                try:
                    sync_path.unlink()
                    logger.info(f"WeChat sync_buf file deleted: {sync_path}")
                except Exception as del_err:
                    logger.warning(f"Failed to delete sync_buf file: {del_err}")

            config = self.channel_repo.get_channel_config(channel_name)
            if config:
                self.channel_repo.create_or_update_channel_config(
                    channel_name=channel_name,
                    channel_type="wechat",
                    enabled=False,
                    app_id="",
                    app_secret="",
                    encrypt_key="",
                    verification_token="",
                    allow_from=config.allow_from or [],
                )
                logger.info(f"WeChat token cleared for channel {channel_name}")

                from backend.channels.manager import ChannelManager
                cm = ChannelManager._get_global_instance()
                if cm and channel_name in cm.channels:
                    channel = cm.channels[channel_name]
                    if hasattr(channel, 'stop'):
                        await channel.stop()
                    if hasattr(channel, '_session_paused_until'):
                        channel._session_paused_until = 0
                    if hasattr(channel, '_consecutive_failures'):
                        channel._consecutive_failures = 0
                    del cm.channels[channel_name]
                    logger.info(f"Channel {channel_name} stopped and removed from manager")

            await websocket.send_json({
                "type": MessageType.WECHAT_TOKEN_EXPIRED.value,
                "request_id": request_id,
                "data": {
                    "success": True,
                    "message": "Token cleared, please scan QR code again"
                }
            })

        except Exception as e:
            logger.error(f"Error clearing WeChat token: {e}")
            await websocket.send_json({
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "data": {"error": str(e)}
            })

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
