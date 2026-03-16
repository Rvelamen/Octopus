"""Feishu/Lark channel implementation using lark-oapi SDK with WebSocket long connection."""

import asyncio
import json
import os
import threading
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from backend.core.events.types import OutboundMessage
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
        CreateMessageReactionRequest,
        CreateMessageReactionRequestBody,
        Emoji,
        P2ImMessageReceiveV1,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False
    lark = None
    Emoji = None

# Message type display mapping
MSG_TYPE_MAP = {
    "image": "[image]",
    "audio": "[audio]",
    "file": "[file]",
    "sticker": "[sticker]",
}

# Resource types that can be downloaded
DOWNLOADABLE_TYPES = {"image", "file", "audio", "video", "media"}


class FeishuChannel(BaseChannel):
    """
    Feishu/Lark channel using WebSocket long connection.
    
    Uses WebSocket to receive events - no public IP or webhook required.
    
    Requires:
    - App ID and App Secret from Feishu Open Platform
    - Bot capability enabled
    - Event subscription enabled (im.message.receive_v1)
    """
    
    name = "feishu"
    
    def __init__(self, config, bus: MessageBus, workspace: Path | None = None):
        super().__init__(config, bus)
        self.config = config
        self._client: Any = None
        self._ws_client: Any = None
        self._ws_thread: threading.Thread | None = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()  # Ordered dedup cache
        self._loop: asyncio.AbstractEventLoop | None = None
        # Use provided workspace or fall back to default relative path
        workspace_path = workspace or Path("workspace")
        self._workspace_dir: Path = workspace_path / "feishu_files"
    
    async def start(self) -> None:
        """Start the Feishu bot with WebSocket long connection."""
        if not FEISHU_AVAILABLE:
            logger.error("Feishu SDK not installed. Run: pip install lark-oapi")
            return
        
        if not self.config.config.app_id or not self.config.config.app_secret:
            logger.error("Feishu app_id and app_secret not configured")
            return

        self._running = True
        self._loop = asyncio.get_running_loop()

        # Create workspace directory for downloaded files
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Feishu files will be saved to: {self._workspace_dir.absolute()}")

        # Create Lark client for sending messages
        self._client = lark.Client.builder() \
            .app_id(self.config.config.app_id) \
            .app_secret(self.config.config.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        # Create event handler (only register message receive, ignore other events)
        event_handler = lark.EventDispatcherHandler.builder(
            self.config.config.encrypt_key or "",
            self.config.config.verification_token or "",
        ).register_p2_im_message_receive_v1(
            self._on_message_sync
        ).build()

        # Create WebSocket client for long connection
        self._ws_client = lark.ws.Client(
            self.config.config.app_id,
            self.config.config.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO
        )
        
        # Start WebSocket client in a separate thread
        def run_ws():
            try:
                self._ws_client.start()
            except Exception as e:
                logger.error(f"Feishu WebSocket error: {e}")
        
        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()
        
        logger.info("Feishu bot started with WebSocket long connection")
        logger.info("No public IP required - using WebSocket to receive events")
        
        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Stop the Feishu bot."""
        self._running = False
        if self._ws_client:
            try:
                self._ws_client.stop()
            except Exception as e:
                logger.warning(f"Error stopping WebSocket client: {e}")
        logger.info("Feishu bot stopped")
    
    def _add_reaction_sync(self, message_id: str, emoji_type: str) -> None:
        """Sync helper for adding reaction (runs in thread pool)."""
        try:
            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                    .build()
                ).build()
            
            response = self._client.im.v1.message_reaction.create(request)
            
            if not response.success():
                logger.warning(f"Failed to add reaction: code={response.code}, msg={response.msg}")
            else:
                logger.debug(f"Added {emoji_type} reaction to message {message_id}")
        except Exception as e:
            logger.warning(f"Error adding reaction: {e}")

    async def _add_reaction(self, message_id: str, emoji_type: str = "THUMBSUP") -> None:
        """
        Add a reaction emoji to a message (non-blocking).
        
        Common emoji types: THUMBSUP, OK, EYES, DONE, OnIt, HEART
        """
        if not self._client or not Emoji:
            return
        
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._add_reaction_sync, message_id, emoji_type)
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Feishu."""
        if not self._client:
            logger.warning("Feishu client not initialized")
            return
        
        try:
            # Determine receive_id_type based on chat_id format
            # open_id starts with "ou_", chat_id starts with "oc_"
            if msg.chat_id.startswith("oc_"):
                receive_id_type = "chat_id"
            else:
                receive_id_type = "open_id"
            
            # Build text message content
            content = json.dumps({"text": msg.content}, ensure_ascii=False)
            
            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(msg.chat_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                ).build()
            
            response = self._client.im.v1.message.create(request)
            
            if not response.success():
                logger.error(
                    f"Failed to send Feishu message: code={response.code}, "
                    f"msg={response.msg}, log_id={response.get_log_id()}"
                )
            else:
                logger.debug(f"Feishu message sent to {msg.chat_id}")
                
        except Exception as e:
            logger.error(f"Error sending Feishu message: {e}")
    
    def _download_resource_sync(
        self, 
        message_id: str, 
        file_key: str, 
        resource_type: str,
        save_path: Path
    ) -> tuple[bool, str]:
        """
        Sync helper for downloading resource from Feishu message.
        
        Args:
            message_id: The message ID containing the resource
            file_key: The file key of the resource
            resource_type: "image" or "file"
            save_path: Path to save the downloaded file
            
        Returns:
            Tuple of (success, file_path or error_message)
        """
        try:
            import requests
            
            # Get tenant access token
            token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            token_resp = requests.post(
                token_url,
                json={
                    "app_id": self.config.config.app_id,
                    "app_secret": self.config.config.app_secret
                },
                timeout=30
            )
            token_data = token_resp.json()
            
            if token_data.get("code") != 0:
                return False, f"Failed to get access token: {token_data.get('msg')}"
            
            access_token = token_data.get("tenant_access_token")
            
            # Download the resource
            download_url = (
                f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
                f"?type={resource_type}"
            )
            
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = requests.get(download_url, headers=headers, timeout=120, stream=True)
            
            if response.status_code != 200:
                return False, f"Download failed: HTTP {response.status_code}"
            
            # Save the file
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True, str(save_path)
            
        except Exception as e:
            logger.error(f"Error downloading resource: {e}")
            return False, str(e)
    
    async def _download_resource(
        self, 
        message_id: str, 
        file_key: str, 
        resource_type: str,
        save_path: Path
    ) -> tuple[bool, str]:
        """
        Download resource from Feishu message (async wrapper).
        
        Args:
            message_id: The message ID containing the resource
            file_key: The file key of the resource
            resource_type: "image" or "file"
            save_path: Path to save the downloaded file
            
        Returns:
            Tuple of (success, file_path or error_message)
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, 
            self._download_resource_sync, 
            message_id, 
            file_key, 
            resource_type,
            save_path
        )
    
    async def _save_file_message_to_session(
        self,
        sender_id: str,
        chat_id: str,
        downloaded_files: list[dict],
        message_id: str,
        chat_type: str,
        msg_type: str,
    ) -> None:
        """
        Save file-only message to session history without triggering agent.
        
        This allows subsequent text messages to reference the files.
        """
        try:
            # Import directly from data module
            from backend.data import Database, SessionRepository
            
            # Build session key
            session_key = f"{self.name}:{chat_id}"
            
            # Create database and repository
            db = Database()
            repo = SessionRepository(db)
            
            # Get or create session
            session_record = repo.get_or_create_session(self.name, chat_id)
            
            # Get or create active instance
            instance = repo.get_or_create_active_instance(session_record.id, "default")
            
            # Build file info message for session history
            file_info_lines = ["User uploaded files:"]
            for i, f in enumerate(downloaded_files, 1):
                file_info_lines.append(f"{i}. {f['original_name']} ({f['type']}) - Path: {f['path']}")
            
            file_info_content = "\n".join(file_info_lines)
            
            # Add message directly to database
            metadata = {
                "message_id": message_id,
                "chat_type": chat_type,
                "msg_type": msg_type,
                "downloaded_files": downloaded_files,
            }
            
            repo.add_message(instance.id, "user", file_info_content, metadata)
            logger.info(f"File message saved to session {session_key}: {file_info_content[:100]}...")
            
        except Exception as e:
            logger.warning(f"Failed to save file message to session: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    async def _save_assistant_message_to_session(
        self,
        chat_id: str,
        content: str,
        message_id: str,
    ) -> None:
        """
        Save assistant message to session history.
        
        This records the bot's response in the conversation history.
        """
        try:
            from backend.data import Database, SessionRepository
            
            session_key = f"{self.name}:{chat_id}"
            
            db = Database()
            repo = SessionRepository(db)
            
            session_record = repo.get_or_create_session(self.name, chat_id)
            instance = repo.get_or_create_active_instance(session_record.id, "default")
            
            metadata = {
                "message_id": message_id,
                "is_bot_message": True,
            }
            
            repo.add_message(instance.id, "assistant", content, metadata)
            logger.debug(f"Assistant message saved to session {session_key}: {content[:50]}...")
            
        except Exception as e:
            logger.warning(f"Failed to save assistant message to session: {e}")
    
    def _parse_message_content(self, message) -> tuple[str, list[dict]]:
        """
        Parse message content and extract file/image information.
        
        Args:
            message: The Feishu message object
            
        Returns:
            Tuple of (content_text, list of resource_info dicts)
            Each resource_info contains: type, file_key, file_name, etc.
        """
        msg_type = message.message_type
        content_str = message.content or "{}"
        resources = []
        
        try:
            content = json.loads(content_str)
        except json.JSONDecodeError:
            return MSG_TYPE_MAP.get(msg_type, f"[{msg_type}]"), resources
        
        if msg_type == "text":
            return content.get("text", ""), resources
        
        elif msg_type == "image":
            image_key = content.get("image_key", "")
            if image_key:
                resources.append({
                    "type": "image",
                    "file_key": image_key,
                    "file_name": f"image_{image_key}.png",
                })
            return "[image]", resources
        
        elif msg_type == "file":
            file_key = content.get("file_key", "")
            file_name = content.get("file_name", f"file_{file_key}")
            if file_key:
                resources.append({
                    "type": "file",
                    "file_key": file_key,
                    "file_name": file_name,
                })
            return f"[file: {file_name}]", resources
        
        elif msg_type == "audio":
            file_key = content.get("file_key", "")
            duration = content.get("duration", 0)
            if file_key:
                resources.append({
                    "type": "file",
                    "file_key": file_key,
                    "file_name": f"audio_{file_key}.mp3",
                    "duration": duration,
                })
            return "[audio]", resources
        
        elif msg_type == "video":
            file_key = content.get("file_key", "")
            file_name = content.get("file_name", f"video_{file_key}.mp4")
            if file_key:
                resources.append({
                    "type": "file",
                    "file_key": file_key,
                    "file_name": file_name,
                })
            return f"[video: {file_name}]", resources
        
        elif msg_type == "media":
            # Rich media message (can contain multiple files/images)
            file_key = content.get("file_key", "")
            image_key = content.get("image_key", "")
            file_name = content.get("file_name", "")
            
            if image_key:
                resources.append({
                    "type": "image",
                    "file_key": image_key,
                    "file_name": file_name or f"image_{image_key}.png",
                })
                return f"[media image: {file_name or image_key}]", resources
            elif file_key:
                resources.append({
                    "type": "file",
                    "file_key": file_key,
                    "file_name": file_name or f"file_{file_key}",
                })
                return f"[media file: {file_name or file_key}]", resources
        
        return MSG_TYPE_MAP.get(msg_type, f"[{msg_type}]"), resources
    
    def _on_message_sync(self, data: "P2ImMessageReceiveV1") -> None:
        """
        Sync handler for incoming messages (called from WebSocket thread).
        Schedules async handling in the main event loop.
        """
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._on_message(data), self._loop)
    
    async def _on_message(self, data: "P2ImMessageReceiveV1") -> None:
        """Handle incoming message from Feishu."""
        try:
            event = data.event
            message = event.message
            sender = event.sender
            
            # Deduplication check
            message_id = message.message_id
            if message_id in self._processed_message_ids:
                return
            self._processed_message_ids[message_id] = None
            
            # Trim cache: keep most recent 500 when exceeds 1000
            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)
            
            # Skip bot messages
            sender_type = sender.sender_type
            if sender_type == "bot":
                return
            
            sender_id = sender.sender_id.open_id if sender.sender_id else "unknown"
            chat_id = message.chat_id
            chat_type = message.chat_type  # "p2p" or "group"
            msg_type = message.message_type
            
            # Add reaction to indicate "seen"
            await self._add_reaction(message_id, "THUMBSUP")
            
            # Parse message content and extract resources
            content, resources = self._parse_message_content(message)
            
            if not content and not resources:
                return
            
            # Download resources if any
            downloaded_files = []
            if resources:
                # Create date-based subdirectory
                today = datetime.now().strftime("%Y%m%d")
                save_dir = self._workspace_dir / today
                save_dir.mkdir(parents=True, exist_ok=True)
                
                for i, resource in enumerate(resources):
                    file_key = resource["file_key"]
                    resource_type = resource["type"]
                    file_name = resource["file_name"]
                    
                    # Generate unique filename
                    unique_name = f"{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:8]}_{file_name}"
                    save_path = save_dir / unique_name
                    
                    logger.info(f"Downloading {resource_type} from message {message_id}: {file_name}")
                    
                    success, result = await self._download_resource(
                        message_id=message_id,
                        file_key=file_key,
                        resource_type=resource_type,
                        save_path=save_path
                    )
                    
                    if success:
                        downloaded_files.append({
                            "path": result,
                            "type": resource_type,
                            "original_name": file_name,
                        })
                        logger.info(f"Downloaded {resource_type} to: {result}")
                    else:
                        logger.error(f"Failed to download {resource_type}: {result}")
                        # Add error info to content
                        content += f"\n[Failed to download {resource_type}: {result}]"
            
            # Build media list from downloaded files
            media_paths = [f["path"] for f in downloaded_files]
            
            # Determine reply target
            reply_to = chat_id if chat_type == "group" else sender_id
            
            # Check if this is a file-only message (no actual text content)
            is_file_only = not content or content.startswith("[")
            
            if is_file_only and downloaded_files:
                # For file-only messages: save to session history but don't trigger agent
                await self._save_file_message_to_session(
                    sender_id=sender_id,
                    chat_id=reply_to,
                    downloaded_files=downloaded_files,
                    message_id=message_id,
                    chat_type=chat_type,
                    msg_type=msg_type,
                )
                
                # Send confirmation message
                file_names = [f["original_name"] for f in downloaded_files]
                confirm_msg = f"✅ 已接收文件: {', '.join(file_names)}"
                
                # Also save confirmation to session history as assistant message
                await self._save_assistant_message_to_session(
                    chat_id=reply_to,
                    content=confirm_msg,
                    message_id=f"{message_id}_confirm",
                )
                
                from backend.core.events.types import OutboundMessage
                await self.send(OutboundMessage(
                    channel=self.name,
                    chat_id=reply_to,
                    content=confirm_msg
                ))
                
                logger.info(f"Files received from {sender_id}, saved to session history. No agent task triggered.")
                return
            
            # For text messages (possibly with files): forward to message bus for agent processing
            await self._handle_message(
                sender_id=sender_id,
                chat_id=reply_to,
                content=content,
                media=media_paths,
                metadata={
                    "message_id": message_id,
                    "chat_type": chat_type,
                    "msg_type": msg_type,
                    "downloaded_files": downloaded_files,
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing Feishu message: {e}")
