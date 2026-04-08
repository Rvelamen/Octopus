"""Desktop channel implementation using WebSocket."""

import asyncio
import base64
from datetime import datetime
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from loguru import logger

from backend.core.events.types import InboundMessage, OutboundMessage, AgentEvent
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers import HandlerRegistry
from backend.mcp.manager import MCPManager, get_mcp_manager


class DesktopChannel(BaseChannel):
    """
    Desktop channel implementation using WebSocket.

    Manages connections from the desktop frontend and routes messages
    through the central message bus.
    """

    name = "desktop"

    def __init__(self, config: Any, bus: MessageBus, app: FastAPI, mcp_manager: MCPManager | None = None, cron_service=None, agent_loop=None, subagent_manager=None):
        super().__init__(config, bus)
        self.app = app
        self.connected_clients: list[WebSocket] = []
        self.pending_responses: dict[str, asyncio.Queue] = {}
        self.mcp_manager = mcp_manager
        self.cron_service = cron_service
        self.agent_loop = agent_loop
        self.subagent_manager = subagent_manager
        self.handler_registry = HandlerRegistry(bus, self.pending_responses, mcp_manager, cron_service, agent_loop=agent_loop, subagent_manager=subagent_manager)
        self._mcp_state_callback_registered = False
    
    async def start(self) -> None:
        """Start the desktop channel by registering the WebSocket endpoint."""
        self._running = True

        # Register MCP state change callback for broadcasting
        if self.mcp_manager and not self._mcp_state_callback_registered:
            self.mcp_manager.register_state_callback(self._on_mcp_state_change)
            self._mcp_state_callback_registered = True

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            logger.info("Desktop client connected")

            self.connected_clients.append(websocket)

            heartbeat_task = asyncio.create_task(self._heartbeat_loop(websocket))

            try:
                while True:
                    try:
                        data = await websocket.receive_json()
                        await self._handle_client_message(websocket, data)
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error(f"WebSocket error: {e}")
                        break

            except WebSocketDisconnect:
                logger.info("Desktop client disconnected")
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except (asyncio.CancelledError, Exception):
                    pass
                if websocket in self.connected_clients:
                    self.connected_clients.remove(websocket)

        logger.info("Desktop channel started")

        # Keep running
        while self._running:
            await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Stop the channel."""
        self._running = False
        # Clean up clients
        for ws in self.connected_clients:
            await ws.close()
        self.connected_clients.clear()
        logger.info("Desktop channel stopped")
    
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to the desktop frontend."""
        if not msg.content:
            return
        
        request_id = msg.metadata.get("request_id") if msg.metadata else None
        
        ws_message = WSMessage(
            type=MessageType.CHAT_RESPONSE,
            request_id=request_id,
            data={"content": msg.content}
        )
        
        await self._broadcast(ws_message.to_dict())
        
        # Handle TTS if enabled
        if msg.metadata and msg.metadata.get("tts_enabled"):
            instance_id = msg.metadata.get("session_instance_id")
            tts_config = msg.metadata.get("tts_config", {})
            
            if instance_id and tts_config:
                asyncio.create_task(
                    self._send_tts(msg.content, instance_id, tts_config)
                )
    
    async def _send_tts(self, text: str, instance_id: int, tts_config: dict) -> None:
        """Generate and send TTS audio to desktop frontend."""
        try:
            from backend.services.tts_service import TTSService
            from backend.data import Database
            from backend.data.provider_store import ProviderRepository, SettingsRepository
            from backend.data.session_store import SessionRepository
            
            db = Database()
            session_repo = SessionRepository(db)
            provider_repo = ProviderRepository(db)
            settings_repo = SettingsRepository(db)
            
            tts_service = TTSService(session_repo, provider_repo, settings_repo)
            result = await tts_service.synthesize(text, tts_config)
            
            audio_base64 = base64.b64encode(result.audio_data).decode()
            
            await self._broadcast({
                "type": "tts_auto_reply",
                "data": {
                    "instanceId": instance_id,
                    "audio": audio_base64,
                    "format": result.format,
                    "text": text,
                    "duration_ms": result.duration_ms
                }
            })
            
            session_repo.update_latest_message_tts(
                instance_id, 
                "assistant",
                {
                    "audio": audio_base64,
                    "format": result.format,
                    "text": text,
                    "duration_ms": result.duration_ms
                }
            )
            
            logger.debug(f"TTS audio sent for instance {instance_id}")
        except Exception as e:
            logger.error(f"Failed to generate TTS audio: {e}")
                
    async def _handle_event(self, event: AgentEvent):
        """Handle an agent event from the bus.
        
        Only process events from the desktop channel to avoid
        displaying messages from other channels (feishu, etc.)
        """
        # logger.info(f"[DesktopChannel] Received event: {event.event_type}, channel: {event.channel}")
        
        # Only handle events from desktop channel
        if event.channel != "desktop":
            # logger.info(f"[DesktopChannel] Ignoring event from channel: {event.channel}")
            return
        
        # Map event types to message types
        event_type_map = {
            "agent_start": MessageType.AGENT_START,
            "agent_token": MessageType.AGENT_TOKEN,  # New: streaming token
            "agent_chunk": MessageType.AGENT_CHUNK,
            "agent_finish": MessageType.AGENT_FINISH,
            # Tool call events
            "agent_tool_call_start": MessageType.AGENT_TOOL_CALL_START,
            "agent_tool_call_streaming": MessageType.AGENT_TOOL_CALL_STREAMING,
            "agent_tool_call_invoking": MessageType.AGENT_TOOL_CALL_INVOKING,
            "agent_tool_call_complete": MessageType.AGENT_TOOL_CALL_COMPLETE,
            "agent_tool_call_error": MessageType.AGENT_TOOL_CALL_ERROR,
            # Iteration event
            "agent_iteration_complete": MessageType.AGENT_ITERATION_COMPLETE,
        }
        
        msg_type = event_type_map.get(event.event_type)
        if msg_type:
            ws_message = WSMessage(
                type=msg_type,
                data=event.data
            )
            # logger.info(f"[DesktopChannel] Broadcasting event: {event.event_type} to {len(self.connected_clients)} clients")
            await self._broadcast(ws_message.to_dict())
        else:
            # For unknown events, broadcast as-is
            # logger.info(f"[DesktopChannel] Broadcasting unknown event: {event.event_type}")
            await self._broadcast({
                "type": event.event_type,
                "data": event.data
            })
        
    async def _broadcast(self, payload: dict):
        """Broadcast a payload to all connected clients."""
        # logger.info(f"[_broadcast] Broadcasting to {len(self.connected_clients)} clients: {payload.get('type')}")
        dead_clients = []
        for client in self.connected_clients:
            try:
                await client.send_json(payload)
                # logger.info(f"[_broadcast] Message sent to client")
            except Exception as e:
                logger.error(f"[_broadcast] Failed to send message: {e}")
                dead_clients.append(client)

        for client in dead_clients:
            if client in self.connected_clients:
                self.connected_clients.remove(client)

    async def _handle_client_message(self, websocket: WebSocket, data: dict):
        """Handle incoming message from client."""
        try:
            # Parse the message
            message = WSMessage.from_dict(data)

            # Route to appropriate handler
            await self.handler_registry.handle(websocket, message)

        except Exception as e:
            logger.error(f"Error handling client message: {e}")
            # Send error response
            try:
                error_msg = WSMessage(
                    type=MessageType.ERROR,
                    request_id=data.get("request_id"),
                    data={"error": f"Failed to process message: {str(e)}"}
                )
                await websocket.send_json(error_msg.to_dict())
            except Exception:
                pass  # Client may have disconnected

    async def _heartbeat_loop(self, websocket: WebSocket, interval: int = 30) -> None:
        """Send periodic ping frames to detect dead connections.

        Args:
            websocket: The client WebSocket connection.
            interval: Heartbeat interval in seconds (default 30s).
        """
        while True:
            await asyncio.sleep(interval)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break

    def _on_mcp_state_change(self, event_type: str, old_value: Any, new_value: Any) -> None:
        """Handle MCP state changes and broadcast to all connected clients."""
        asyncio.create_task(self._broadcast({
            "type": MessageType.MCP_STATE_CHANGE.value,
            "event": event_type,
            "old_value": old_value,
            "new_value": new_value,
            "timestamp": datetime.now().isoformat(),
        }))
