"""Image handlers for Desktop channel."""

import asyncio
import base64
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.core.events.bus import MessageBus
from backend.data import Database


class ImageUploadHandler(MessageHandler):
    """Handle image upload requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Save uploaded image to workspace."""
        try:
            image_data = message.data.get("image_data")  # base64 encoded
            file_name = message.data.get("file_name", "uploaded_image.png")
            mime_type = message.data.get("mime_type", "image/png")
            session_instance_id = message.data.get("session_instance_id")

            if not image_data:
                await self._send_error(websocket, message.request_id, "Image data is required")
                return

            from backend.utils.helpers import get_workspace_path
            workspace = get_workspace_path()

            images_dir = workspace / "images"
            images_dir.mkdir(parents=True, exist_ok=True)

            ext = file_name.split(".")[-1] if "." in file_name else "png"
            unique_name = f"{uuid.uuid4().hex[:8]}_{file_name}"
            file_path = images_dir / unique_name

            image_bytes = base64.b64decode(image_data.split(",")[-1] if "," in image_data else image_data)
            file_path.write_bytes(image_bytes)

            rel_path = file_path.relative_to(workspace)

            if session_instance_id:
                from backend.data.database import Database
                db = Database()
                db.execute(
                    """INSERT INTO images
                        (session_instance_id, image_type, source, file_path, file_name, mime_type, file_size)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session_instance_id, "upload", "user", str(rel_path), unique_name, mime_type, len(image_bytes))
                )

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_UPLOADED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "file_name": unique_name,
                    "file_path": str(rel_path),
                    "full_path": str(file_path),
                    "size": len(image_bytes)
                }
            ))

        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            await self._send_error(websocket, message.request_id, str(e))


class FileUploadHandler(MessageHandler):
    """Handle file upload requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Save uploaded file to workspace."""
        try:
            file_data = message.data.get("file_data")
            file_name = message.data.get("file_name", "uploaded_file")
            mime_type = message.data.get("mime_type", "application/octet-stream")
            session_instance_id = message.data.get("session_instance_id")

            if not file_data:
                await self._send_error(websocket, message.request_id, "File data is required")
                return

            from backend.utils.helpers import get_workspace_path
            workspace = get_workspace_path()

            files_dir = workspace / "files"
            files_dir.mkdir(parents=True, exist_ok=True)

            ext = file_name.split(".")[-1] if "." in file_name else ""
            unique_name = f"{uuid.uuid4().hex[:8]}_{file_name}"
            file_path = files_dir / unique_name

            file_bytes = base64.b64decode(file_data.split(",")[-1] if "," in file_data else file_data)
            file_path.write_bytes(file_bytes)

            rel_path = file_path.relative_to(workspace)

            await self.send_response(websocket, WSMessage(
                type=MessageType.FILE_UPLOADED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "file_name": unique_name,
                    "original_name": file_name,
                    "file_path": str(rel_path),
                    "full_path": str(file_path),
                    "mime_type": mime_type,
                    "size": len(file_bytes)
                }
            ))

        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ImageAnalyzeHandler(MessageHandler):
    """Handle image analysis requests."""

    def __init__(self, bus: MessageBus):
        super().__init__(bus)
        self.image_service = None

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Analyze image using vision model."""
        try:
            from backend.services.image_service import ImageService

            if self.image_service is None:
                self.image_service = ImageService()

            image_path = message.data.get("image_path")
            question = message.data.get("question", "")
            provider_name = message.data.get("provider_name")  # Use provider name instead of ID

            if not image_path:
                await self._send_error(websocket, message.request_id, "Image path is required")
                return

            # Resolve path
            from backend.utils.helpers import get_workspace_path
            full_path = get_workspace_path() / image_path
            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"Image not found: {image_path}")
                return

            # Analyze
            result = await self.image_service.understand_image(
                image_path=str(full_path),
                question=question,
                provider_name=provider_name
            )

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_ANALYSIS_RESULT,
                request_id=message.request_id,
                data={
                    "success": True,
                    "result": result,
                    "image_path": image_path
                }
            ))

        except Exception as e:
            logger.error(f"Failed to analyze image: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to analyze image: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ImageGenerateHandler(MessageHandler):
    """Handle image generation requests."""

    def __init__(self, bus: MessageBus):
        super().__init__(bus)
        self.image_service = None

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Generate image using AI model."""
        try:
            from backend.services.image_service import ImageService

            if self.image_service is None:
                self.image_service = ImageService()

            prompt = message.data.get("prompt")
            size = message.data.get("size")
            quality = message.data.get("quality")
            provider_name = message.data.get("provider_name")  # Use provider name instead of ID

            if not prompt:
                await self._send_error(websocket, message.request_id, "Prompt is required")
                return

            # Send progress
            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_GENERATION_PROGRESS,
                request_id=message.request_id,
                data={"status": "generating", "message": "正在生成图片..."}
            ))

            # Generate
            result = await self.image_service.generate_image(
                prompt=prompt,
                size=size,
                quality=quality,
                provider_name=provider_name
            )

            # Save image
            from backend.utils.helpers import get_workspace_path
            output_dir = get_workspace_path() / "generated"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"generated_{uuid.uuid4().hex[:8]}.png"

            if "image_data" in result:
                output_path.write_bytes(result["image_data"])
            elif "url" in result:
                async with httpx.AsyncClient() as client:
                    response = await client.get(result["url"], timeout=60.0)
                    response.raise_for_status()
                    output_path.write_bytes(response.content)

            rel_path = output_path.relative_to(get_workspace_path())

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_GENERATED,
                request_id=message.request_id,
                data={
                    "success": True,
                    "file_path": str(rel_path),
                    "full_path": str(output_path),
                    "prompt": result.get("revised_prompt", prompt)
                }
            ))

        except Exception as e:
            logger.error(f"Failed to generate image: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to generate image: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ImageGetUnderstandingProvidersHandler(MessageHandler):
    """Handle get understanding providers requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all image understanding providers from AI providers."""
        try:
            from backend.services.image_service import ImageService

            image_service = ImageService()
            providers = image_service.get_understanding_providers()

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_UNDERSTANDING_PROVIDERS,
                request_id=message.request_id,
                data={
                    "providers": [
                        {
                            "name": p.name,
                            "provider_type": p.provider_type,
                            "model": p.model,
                            "api_base": p.api_base,
                            "is_default": p.is_default,
                            "enabled": p.enabled,
                        }
                        for p in providers
                    ]
                }
            ))

        except Exception as e:
            logger.error(f"Failed to get understanding providers: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get providers: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class ImageGetGenerationProvidersHandler(MessageHandler):
    """Handle get generation providers requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return all image generation providers from AI providers."""
        try:
            from backend.services.image_service import ImageService

            image_service = ImageService()
            providers = image_service.get_generation_providers()

            await self.send_response(websocket, WSMessage(
                type=MessageType.IMAGE_GENERATION_PROVIDERS,
                request_id=message.request_id,
                data={
                    "providers": [
                        {
                            "name": p.name,
                            "provider_type": p.provider_type,
                            "model": p.model,
                            "api_base": p.api_base,
                            "is_default": p.is_default,
                            "enabled": p.enabled,
                        }
                        for p in providers
                    ]
                }
            ))

        except Exception as e:
            logger.error(f"Failed to get generation providers: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get providers: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
