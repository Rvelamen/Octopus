"""Desktop channel implementation using WebSocket."""

import asyncio
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

    def __init__(self, config: Any, bus: MessageBus, app: FastAPI, mcp_manager: MCPManager | None = None, cron_service=None):
        super().__init__(config, bus)
        self.app = app
        self.connected_clients: list[WebSocket] = []
        self.pending_responses: dict[str, asyncio.Queue] = {}
        self.mcp_manager = mcp_manager
        self.cron_service = cron_service
        self.handler_registry = HandlerRegistry(bus, self.pending_responses, mcp_manager, cron_service)
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

            try:
                while True:
                    try:
                        # Wait for client message with timeout
                        data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                        await self._handle_client_message(websocket, data)
                    except asyncio.TimeoutError:
                        pass
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error(f"WebSocket error: {e}")
                        break

            except WebSocketDisconnect:
                logger.info("Desktop client disconnected")
            finally:
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
        
        # Check if this response has a request_id for correlation
        request_id = msg.metadata.get("request_id") if msg.metadata else None
        
        ws_message = WSMessage(
            type=MessageType.CHAT_RESPONSE,
            request_id=request_id,
            data={"content": msg.content}
        )
        
        await self._broadcast(ws_message.to_dict())
                
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
            "agent_chunk": MessageType.AGENT_CHUNK,
            "agent_finish": MessageType.AGENT_FINISH,
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

    def _on_mcp_state_change(self, event_type: str, old_value: Any, new_value: Any) -> None:
        """Handle MCP state changes and broadcast to all connected clients."""
        asyncio.create_task(self._broadcast({
            "type": MessageType.MCP_STATE_CHANGE.value,
            "event": event_type,
            "old_value": old_value,
            "new_value": new_value,
            "timestamp": datetime.now().isoformat(),
        }))
