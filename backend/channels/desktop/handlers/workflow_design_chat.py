"""WebSocket message handlers for Desktop channel — Workflow Design Chat handler."""

import asyncio

from fastapi import WebSocket
from loguru import logger

from backend.agent.workflow_designer_agent import WorkflowDesignerAgent
from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.data.database import Database
from backend.services.workflow_design_chat_service import WorkflowDesignChatService
from backend.utils.helpers import get_workspace_path


class WorkflowDesignChatHandler(MessageHandler):
    """Handle workflow design chat messages from clients."""

    def __init__(self, bus, pending_responses: dict[str, asyncio.Queue]):
        super().__init__(bus)
        self.pending_responses = pending_responses
        workspace = get_workspace_path()
        db = Database()
        self.design_service = WorkflowDesignChatService(db)
        self.design_agent = WorkflowDesignerAgent(workspace, db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Process a workflow design chat message."""
        action = message.data.get("action", "")

        if action == "init_session":
            await self._handle_init_session(websocket, message)
        elif action == "list_sessions":
            await self._handle_list_sessions(websocket, message)
        elif action == "list_messages":
            await self._handle_list_messages(websocket, message)
        elif action == "chat":
            await self._handle_chat(websocket, message)
        elif action == "clear_session":
            await self._handle_clear_session(websocket, message)
        else:
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": f"Unknown action: {action}"},
                ),
            )

    async def _handle_init_session(self, websocket: WebSocket, message: WSMessage) -> None:
        workflow_id = message.data.get("workflow_id")
        if not workflow_id:
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": "workflow_id is required"},
                ),
            )
            return

        agent_config_id = message.data.get("agent_config_id")

        # Check for existing session for this workflow
        sessions = self.design_service.list_sessions(workflow_id=workflow_id)
        if sessions:
            session = sessions[0]
        else:
            session = self.design_service.create_session(
                workflow_id=workflow_id, agent_config_id=agent_config_id
            )

        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.CHAT_RESPONSE,
                request_id=message.request_id,
                data={
                    "session": {
                        "id": session.id,
                        "workflow_id": session.workflow_id,
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

    async def _handle_list_sessions(self, websocket: WebSocket, message: WSMessage) -> None:
        workflow_id = message.data.get("workflow_id")
        sessions = self.design_service.list_sessions(workflow_id=workflow_id)
        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.CHAT_RESPONSE,
                request_id=message.request_id,
                data={
                    "sessions": [
                        {
                            "id": s.id,
                            "workflow_id": s.workflow_id,
                            "agent_config_id": s.agent_config_id,
                            "created_at": s.created_at.isoformat() if s.created_at else None,
                            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                        }
                        for s in sessions
                    ]
                },
            ),
        )

    async def _handle_list_messages(self, websocket: WebSocket, message: WSMessage) -> None:
        session_id = message.data.get("session_id")
        messages = self.design_service.list_messages(session_id) if session_id else []
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
                            "tool_calls": m.tool_calls,
                            "tool_call_id": m.tool_call_id,
                            "metadata": m.metadata,
                            "created_at": m.created_at.isoformat() if m.created_at else None,
                        }
                        for m in messages
                    ]
                },
            ),
        )

    async def _handle_clear_session(self, websocket: WebSocket, message: WSMessage) -> None:
        session_id = message.data.get("session_id")
        if session_id:
            self.design_service.delete_session(session_id)
        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.CHAT_RESPONSE,
                request_id=message.request_id,
                data={"success": True},
            ),
        )

    async def _handle_chat(self, websocket: WebSocket, message: WSMessage) -> None:
        session_id = message.data.get("session_id")
        workflow_id = message.data.get("workflow_id")
        user_content = message.data.get("content", "")
        selected_nodes = message.data.get("selected_nodes", [])

        if not session_id or not workflow_id or not user_content:
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": "session_id, workflow_id, and content are required"},
                ),
            )
            return

        # Load session to get agent_config_id
        session = self.design_service.get_session(session_id)
        agent_config_id = session.agent_config_id if session else None

        request_id = message.request_id

        # Emit start event
        await self.send_response(
            websocket,
            WSMessage(
                type=MessageType.CHAT_RESPONSE,
                request_id=request_id,
                data={"status": "started", "session_id": session_id},
            ),
        )

        full_content = ""

        def on_token(token: str):
            nonlocal full_content
            full_content += token
            asyncio.create_task(
                self.send_response(
                    websocket,
                    WSMessage(
                        type=MessageType.CHAT_RESPONSE,
                        request_id=request_id,
                        data={"status": "streaming", "content": token, "session_id": session_id},
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
            result = await self.design_agent.chat(
                session_id=session_id,
                workflow_id=workflow_id,
                user_content=user_content,
                selected_nodes=selected_nodes or None,
                agent_config_id=agent_config_id,
                on_token=on_token,
                on_tool_start=on_tool_start,
                on_tool_result=on_tool_result,
            )
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.CHAT_RESPONSE,
                    request_id=request_id,
                    data={"status": "completed", "content": result, "session_id": session_id},
                ),
            )
        except Exception as e:
            logger.error(f"[WorkflowDesignChatHandler] Chat failed: {e}")
            await self.send_response(
                websocket,
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=request_id,
                    data={"error": str(e), "session_id": session_id},
                ),
            )
