"""Book-world desktop boundary with a fixed server workspace per request."""

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from loguru import logger
from pydantic import ValidationError

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.services.book_world import BookSourceService, BookWorldError
from backend.services.book_world.contracts import BookWorldRequest
from backend.utils.helpers import get_workspace_path


def workspace_identity(root: Path) -> str:
    """Return an opaque identity, without disclosing an absolute filesystem path."""
    return hashlib.sha256(os.path.normcase(str(root.resolve())).encode("utf-8")).hexdigest()


class BookWorldHandler(MessageHandler):
    """Run synchronous PDF/SQLite work off the desktop event loop."""

    @staticmethod
    def _execute(root: Path, request: BookWorldRequest) -> dict[str, Any]:
        service = BookSourceService(root)
        if request.action == "prepare_source":
            result = service.prepare_source(
                request.item_id, expected_attachment_sha256=request.expected_attachment_sha256
            )
        elif request.action == "get_source":
            result = service.get_source(request.item_id, request.source_version_id)
        elif request.action == "list_segments":
            result = service.list_segments(
                request.item_id, request.source_version_id, request.after_ordinal, request.limit
            )
        else:
            result = service.resolve_evidence(
                request.item_id,
                request.source_version_id,
                request.segment_id,
                request.local_start,
                request.local_end,
            )
        return {
            "action": request.action,
            "workspace_id": workspace_identity(root),
            "item_id": request.item_id,
            **result,
        }

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            request = BookWorldRequest.model_validate(message.data)
        except ValidationError as error:
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={
                        "error": "Invalid book-world request",
                        "code": "invalid_request",
                        "details": error.errors(include_context=False),
                    },
                ),
            )
            return
        root = Path(get_workspace_path()).resolve()
        try:
            result = await asyncio.to_thread(self._execute, root, request)
            response = WSMessage(
                type=MessageType.BOOK_WORLD_RESULT, request_id=message.request_id, data=result
            )
        except BookWorldError as error:
            response = WSMessage(
                type=MessageType.ERROR,
                request_id=message.request_id,
                data={
                    "error": str(error),
                    "code": error.code,
                    "workspace_id": workspace_identity(root),
                },
            )
        except Exception:
            logger.exception("Book-world source operation failed")
            response = WSMessage(
                type=MessageType.ERROR,
                request_id=message.request_id,
                data={
                    "error": "Could not prepare or read the book source",
                    "code": "source_failed",
                },
            )
        await self.send_response(websocket, response)
