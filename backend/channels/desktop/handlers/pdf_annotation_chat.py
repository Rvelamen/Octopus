"""WebSocket message handlers for Desktop channel — PDF Annotation Chat handler."""

import asyncio

from fastapi import WebSocket
from loguru import logger

from backend.agent.pdf_annotation_chat_agent import PdfAnnotationChatAgent
from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.data.database import Database
from backend.services.pdf_annotation_chat_service import PdfAnnotationChatService
from backend.utils.helpers import get_workspace_path


class PdfAnnotationChatHandler(MessageHandler):
    """Handle annotation-bound PDF chat messages.

    Each session is permanently bound to a single library_annotations row;
    annotation text + its thread comments are injected into the LLM system
    prompt at chat time (see PdfAnnotationChatAgent._build_system_prompt).
    """

    def __init__(self, bus, pending_responses: dict[str, asyncio.Queue]):
        super().__init__(bus)
        self.pending_responses = pending_responses
        workspace = get_workspace_path()
        db = Database()
        self.chat_service = PdfAnnotationChatService(db)
        self.chat_agent = PdfAnnotationChatAgent(workspace, db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        action = message.data.get("action", "")

        if action == "list_sessions":
            await self._handle_list_sessions(websocket, message)
        elif action == "create_session":
            await self._handle_create_session(websocket, message)
        elif action == "delete_session":
            await self._handle_delete_session(websocket, message)
        elif action == "list_messages":
            await self._handle_list_messages(websocket, message)
        elif action == "chat":
            await self._handle_chat(websocket, message)
        else:
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": f"Unknown action: {action}"},
                ),
            )

    async def _handle_list_sessions(
        self, websocket: WebSocket, message: WSMessage
    ) -> None:
        annotation_id = message.data.get("annotation_id")
        item_id = message.data.get("item_id")
        pdf_path = message.data.get("pdf_path")
        sessions = self.chat_service.list_sessions(
            annotation_id=annotation_id, item_id=item_id, pdf_path=pdf_path
        )
        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.CHAT_RESPONSE,
                request_id=message.request_id,
                data={
                    "sessions": [
                        {
                            "id": s.id,
                            "item_id": s.item_id,
                            "pdf_path": s.pdf_path,
                            "annotation_id": s.annotation_id,
                            "title": s.title,
                            "agent_config_id": s.agent_config_id,
                            "created_at": s.created_at.isoformat() if s.created_at else None,
                            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                        }
                        for s in sessions
                    ]
                },
            ),
        )

    async def _handle_create_session(
        self, websocket: WebSocket, message: WSMessage
    ) -> None:
        annotation_id = message.data.get("annotation_id")
        if not annotation_id:
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": "annotation_id is required"},
                ),
            )
            return
        title = message.data.get("title", "Annotation Chat")
        item_id = message.data.get("item_id")
        pdf_path = message.data.get("pdf_path")
        agent_config_id = message.data.get("agent_config_id")
        try:
            session = self.chat_service.create_session(
                annotation_id=int(annotation_id),
                title=title,
                item_id=item_id,
                pdf_path=pdf_path,
                agent_config_id=agent_config_id,
            )
        except Exception as e:
            logger.error(f"Failed to create annotation chat session: {e}")
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": str(e)},
                ),
            )
            return
        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.CHAT_RESPONSE,
                request_id=message.request_id,
                data={
                    "session": {
                        "id": session.id,
                        "item_id": session.item_id,
                        "pdf_path": session.pdf_path,
                        "annotation_id": session.annotation_id,
                        "title": session.title,
                        "agent_config_id": session.agent_config_id,
                        "created_at": (
                            session.created_at.isoformat() if session.created_at else None
                        ),
                        "updated_at": (
                            session.updated_at.isoformat() if session.updated_at else None
                        ),
                    }
                },
            ),
        )

    async def _handle_delete_session(
        self, websocket: WebSocket, message: WSMessage
    ) -> None:
        session_id = message.data.get("session_id")
        if session_id:
            self.chat_service.delete_session(session_id)
        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.CHAT_RESPONSE,
                request_id=message.request_id,
                data={"success": True},
            ),
        )

    async def _handle_list_messages(
        self, websocket: WebSocket, message: WSMessage
    ) -> None:
        session_id = message.data.get("session_id")
        messages = self.chat_service.list_messages(session_id) if session_id else []
        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.CHAT_RESPONSE,
                request_id=message.request_id,
                data={
                    "messages": [
                        {
                            "id": m.id,
                            "session_id": m.session_id,
                            "role": m.role,
                            "content": m.content,
                            "page_number": m.page_number,
                            "selected_text": m.selected_text,
                            "metadata": m.metadata,
                            "created_at": m.created_at.isoformat() if m.created_at else None,
                        }
                        for m in messages
                    ]
                },
            ),
        )

    async def _handle_chat(self, websocket: WebSocket, message: WSMessage) -> None:
        session_id = message.data.get("session_id")
        user_content = message.data.get("content", "")
        page_number = message.data.get("page_number")
        selected_text = message.data.get("selected_text")

        if not session_id or not user_content:
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": "session_id and content are required"},
                ),
            )
            return

        request_id = message.request_id

        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.CHAT_RESPONSE,
                request_id=request_id,
                data={"status": "started", "session_id": session_id},
            ),
        )

        def on_token(token: str):
            asyncio.create_task(
                self.send_response(
                    websocket,
                    WSMessage(
                        type=MessageType.CHAT_RESPONSE,
                        request_id=request_id,
                        data={
                            "status": "streaming",
                            "content": token,
                            "session_id": session_id,
                        },
                    ),
                )
            )

        def on_tool_start(data: dict):
            asyncio.create_task(
                self.send_response(
                    websocket,
                    WSMessage(
                        type=MessageType.CHAT_RESPONSE,
                        request_id=request_id,
                        data={"status": "tool_start", **data, "session_id": session_id},
                    ),
                )
            )

        def on_tool_result(data: dict):
            asyncio.create_task(
                self.send_response(
                    websocket,
                    WSMessage(
                        type=MessageType.CHAT_RESPONSE,
                        request_id=request_id,
                        data={"status": "tool_result", **data, "session_id": session_id},
                    ),
                )
            )

        try:
            result = await self.chat_agent.chat(
                session_id=session_id,
                user_content=user_content,
                page_number=page_number,
                selected_text=selected_text,
                on_token=on_token,
                on_tool_start=on_tool_start,
                on_tool_result=on_tool_result,
            )
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.CHAT_RESPONSE,
                    request_id=request_id,
                    data={
                        "status": "completed",
                        "content": result,
                        "session_id": session_id,
                    },
                ),
            )
        except Exception as e:
            logger.error(f"[PdfAnnotationChatHandler] Chat failed: {e}")
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=request_id,
                    data={"error": str(e), "session_id": session_id},
                ),
            )
