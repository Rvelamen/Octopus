"""MCP connection management module.

Provides connection lifecycle management including:
- Connection establishment
- Connection maintenance (heartbeat)
- Connection recovery (auto-reconnect)
- Connection pooling
"""

import asyncio
import json
import os
import uuid
from enum import Enum, auto
from typing import Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from backend.mcp.config import MCPServerConfig


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    ERROR = auto()
    CLOSED = auto()


@dataclass
class ConnectionStats:
    """Connection statistics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    last_activity: datetime | None = None
    connect_time: datetime | None = None
    disconnect_time: datetime | None = None
    reconnect_attempts: int = 0
    
    @property
    def average_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


class MCPConnection:
    """MCP connection handler.
    
    Manages the lifecycle of a connection to an MCP server including:
    - Establishing connection
    - Maintaining connection (heartbeat)
    - Auto-reconnection on failure
    - Graceful disconnection
    """
    
    def __init__(
        self,
        config: MCPServerConfig,
        on_state_change: Callable[["MCPConnection", ConnectionState, ConnectionState], None] | None = None,
        on_message: Callable[["MCPConnection", dict], None] | None = None,
    ):
        self.id = str(uuid.uuid4())
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.stats = ConnectionStats()
        
        self._on_state_change = on_state_change
        self._on_message = on_message
        
        self._transport: Any = None
        self._heartbeat_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._reconnect_count = 0
        self._lock = asyncio.Lock()
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._closed = False
        
    @property
    def name(self) -> str:
        """Get connection name."""
        return self.config.name
    
    @property
    def is_connected(self) -> bool:
        """Check if connection is established."""
        return self.state == ConnectionState.CONNECTED
    
    @property
    def is_available(self) -> bool:
        """Check if connection is available for requests."""
        return self.is_connected and not self._closed
    
    def _set_state(self, new_state: ConnectionState) -> None:
        """Set connection state and trigger callback."""
        old_state = self.state
        if old_state != new_state:
            self.state = new_state
            logger.info(f"MCP connection '{self.name}' state: {old_state.name} -> {new_state.name}")
            
            if self._on_state_change:
                try:
                    self._on_state_change(self, old_state, new_state)
                except Exception as e:
                    logger.error(f"State change callback error: {e}")
    
    async def connect(self) -> bool:
        """Establish connection to MCP server."""
        if self._closed:
            logger.warning(f"Cannot connect closed connection: {self.name}")
            return False
        
        async with self._lock:
            if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
                logger.debug(f"Connection already {self.state.name}: {self.name}")
                return True
            
            self._set_state(ConnectionState.CONNECTING)
            
            try:
                if self.config.protocol == "stdio":
                    success = await self._connect_stdio()
                elif self.config.protocol == "sse":
                    success = await self._connect_sse()
                elif self.config.protocol == "websocket":
                    success = await self._connect_websocket()
                else:
                    raise ValueError(f"Unsupported protocol: {self.config.protocol}")
                
                if success:
                    self._set_state(ConnectionState.CONNECTED)
                    self.stats.connect_time = datetime.now()
                    self.stats.reconnect_attempts = self._reconnect_count
                    self._reconnect_count = 0

                    await self._send_initialize()

                    # Start heartbeat
                    self._start_heartbeat()

                    logger.info(f"MCP connection established: {self.name}")
                    return True
                else:
                    self._set_state(ConnectionState.ERROR)
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {self.name}: {e}")
                self._set_state(ConnectionState.ERROR)
                return False
    
    async def _connect_stdio(self) -> bool:
        """Connect using stdio protocol."""
        import subprocess

        try:
            cmd = self.config.command or self.config.url
            if not cmd:
                raise ValueError("No command specified for stdio connection")

            env = {**dict(os.environ), **self.config.env_vars}

            # 在后台线程中启动进程，避免阻塞
            loop = asyncio.get_event_loop()
            self._transport = await loop.run_in_executor(
                None,
                lambda: subprocess.Popen(
                    [cmd] + self.config.args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.config.working_dir,
                    env=env,
                )
            )

            # Wait a moment to ensure process started
            await asyncio.sleep(0.5)

            if self._transport.poll() is not None:
                # 在后台线程中读取 stderr
                stderr = await loop.run_in_executor(
                    None,
                    lambda: self._transport.stderr.read() if self._transport.stderr else b""
                )
                raise RuntimeError(f"Process exited immediately with code {self._transport.returncode}, stderr: {stderr}")

            # Start reading loop
            asyncio.create_task(self._read_stdio())

            return True

        except Exception as e:
            logger.error(f"stdio connection error: {e}")
            return False
    
    async def _connect_sse(self) -> bool:
        """Connect using Server-Sent Events protocol."""
        import aiohttp

        try:
            # 使用更短的连接超时
            timeout = aiohttp.ClientTimeout(
                total=self.config.connection_timeout,
                connect=5.0  # 连接超时 5 秒
            )
            self._session = aiohttp.ClientSession(
                headers=self.config.headers,
                timeout=timeout,
            )

            # Establish SSE connection with timeout
            self._response = await asyncio.wait_for(
                self._session.get(
                    self.config.url,
                    headers={"Accept": "text/event-stream"},
                ),
                timeout=10.0
            )

            if self._response.status != 200:
                raise RuntimeError(f"HTTP {self._response.status}")

            # Start reading loop
            asyncio.create_task(self._read_sse())

            return True
        except asyncio.TimeoutError:
            logger.error(f"SSE connection timed out: {self.config.url}")
            if hasattr(self, '_session') and self._session:
                await self._session.close()
            return False
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
            if hasattr(self, '_session') and self._session:
                await self._session.close()
            return False
    
    async def _connect_websocket(self) -> bool:
        """Connect using WebSocket protocol."""
        try:
            import websockets

            headers = self.config.headers.copy()
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"

            # 使用超时连接
            self._transport = await asyncio.wait_for(
                websockets.connect(
                    self.config.url,
                    extra_headers=headers,
                    ping_interval=self.config.heartbeat_interval,
                    ping_timeout=self.config.connection_timeout,
                ),
                timeout=10.0
            )

            # Start reading loop
            asyncio.create_task(self._read_websocket())

            return True

        except asyncio.TimeoutError:
            logger.error(f"WebSocket connection timed out: {self.config.url}")
            return False
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            return False

    async def _send_initialize(self) -> None:
        """Send MCP protocol initialization request."""
        try:
            response = await self.request(
                method="initialize",
                params={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "octopus-mcp-client",
                        "version": "1.0.0"
                    }
                },
                timeout=10,
            )
            if response and "result" in response:
                logger.info(f"MCP server '{self.name}' initialized successfully")
            else:
                logger.warning(f"MCP initialize response unexpected: {response}")
        except Exception as e:
            logger.warning(f"MCP initialize request failed for '{self.name}': {e}")

    async def _read_stdio(self) -> None:
        """Read from stdio process using asyncio to avoid blocking."""
        import sys
        
        try:
            # Use asyncio to run blocking I/O in executor
            loop = asyncio.get_event_loop()
            
            while self.is_connected and self._transport:
                # Run blocking readline in executor to avoid blocking event loop
                line = await loop.run_in_executor(
                    None, 
                    self._transport.stdout.readline
                )
                if not line:
                    break
                
                line = line.decode('utf-8').strip() if isinstance(line, bytes) else line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from stdio: {line[:100]}")
                    
        except Exception as e:
            logger.error(f"stdio read error: {e}")
        finally:
            await self._handle_disconnect()
    
    async def _read_sse(self) -> None:
        """Read from SSE stream."""
        try:
            async for line in self._response.content:
                line = line.decode("utf-8").strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                        await self._handle_message(data)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from SSE: {data_str[:100]}")
                        
        except Exception as e:
            logger.error(f"SSE read error: {e}")
        finally:
            await self._handle_disconnect()
    
    async def _read_websocket(self) -> None:
        """Read from WebSocket connection."""
        try:
            import websockets
            
            async for message in self._transport:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from WebSocket: {message[:100]}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket connection closed: {self.name}")
        except Exception as e:
            logger.error(f"WebSocket read error: {e}")
        finally:
            await self._handle_disconnect()
    
    async def _handle_message(self, data: dict) -> None:
        """Handle incoming message."""
        self.stats.last_activity = datetime.now()
        
        # Check if this is a response to a pending request
        request_id = data.get("id")
        if request_id and request_id in self._pending_requests:
            future = self._pending_requests.pop(request_id)
            if not future.done():
                future.set_result(data)
        
        # Call message callback
        if self._on_message:
            try:
                self._on_message(self, data)
            except Exception as e:
                logger.error(f"Message callback error: {e}")
    
    async def _handle_disconnect(self) -> None:
        """Handle unexpected disconnection."""
        if self.state == ConnectionState.CLOSED:
            return
        
        self._set_state(ConnectionState.DISCONNECTED)
        self.stats.disconnect_time = datetime.now()
        
        # Cancel heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        
        # Clean up transport
        await self._cleanup_transport()
        
        # Auto-reconnect if enabled
        if self.config.auto_connect and not self._closed:
            self._start_reconnect()
    
    def _start_heartbeat(self) -> None:
        """Start heartbeat task."""
        if self.config.heartbeat_interval > 0:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat pings."""
        try:
            while self.is_connected:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                if not self.is_connected:
                    break
                
                try:
                    await self.send({"type": "ping", "timestamp": datetime.now().isoformat()})
                except Exception as e:
                    logger.warning(f"Heartbeat failed for {self.name}: {e}")
                    break
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}")
    
    def _start_reconnect(self) -> None:
        """Start reconnection task."""
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    async def _reconnect_loop(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        self._set_state(ConnectionState.RECONNECTING)
        
        while not self._closed and self._reconnect_count < self.config.max_reconnect_attempts:
            self._reconnect_count += 1
            
            delay = min(
                self.config.reconnect_interval * (2 ** (self._reconnect_count - 1)),
                60  # Max 60 seconds
            )
            
            logger.info(f"Reconnecting to {self.name} in {delay}s (attempt {self._reconnect_count}/{self.config.max_reconnect_attempts})")
            await asyncio.sleep(delay)
            
            if await self.connect():
                return
        
        logger.error(f"Max reconnection attempts reached for {self.name}")
        self._set_state(ConnectionState.ERROR)
    
    async def send(self, data: dict) -> bool:
        """Send data through the connection."""
        if not self.is_available:
            logger.warning(f"Cannot send, connection not available: {self.name}")
            return False
        
        try:
            message = json.dumps(data, ensure_ascii=False)
            
            if self.config.protocol == "stdio":
                # Run blocking I/O in executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: (self._transport.stdin.write((message + "\n").encode('utf-8')), self._transport.stdin.flush())
                )
                
            elif self.config.protocol == "sse":
                # SSE is server-to-client only for data
                # Use HTTP POST for client-to-server
                try:
                    if not hasattr(self, '_session') or self._session.closed:
                        import aiohttp
                        self._session = aiohttp.ClientSession(
                            headers=self.config.headers,
                            timeout=aiohttp.ClientTimeout(total=self.config.connection_timeout),
                        )
                    
                    # Send POST request for MCP over HTTP
                    async with self._session.post(
                        self.config.url,
                        json=data,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            # Handle the response if it's a request
                            if data.get("id") and result:
                                await self._handle_message(result)
                            return True
                        else:
                            logger.error(f"HTTP POST failed: {response.status}")
                            return False
                except Exception as e:
                    logger.error(f"SSE send error: {e}")
                    return False
                
            elif self.config.protocol == "websocket":
                import websockets
                await self._transport.send(message)
            
            self.stats.total_requests += 1
            return True
            
        except Exception as e:
            logger.error(f"Send error for {self.name}: {e}")
            self.stats.failed_requests += 1
            return False
    
    async def request(self, method: str, params: dict | None = None, timeout: float | None = None) -> dict | None:
        """Send a request and wait for response."""
        if not self.is_available:
            logger.warning(f"Cannot make request, connection not available: {self.name}")
            return None
        
        request_id = str(uuid.uuid4())
        request_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        start_time = datetime.now()
        
        try:
            if not await self.send(request_data):
                self._pending_requests.pop(request_id, None)
                return None
            
            # Wait for response
            timeout = timeout or self.config.connection_timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            
            # Update stats
            latency = (datetime.now() - start_time).total_seconds() * 1000
            self.stats.successful_requests += 1
            self.stats.total_latency_ms += latency
            
            return response
            
        except asyncio.TimeoutError:
            logger.error(f"Request timeout for {self.name}: {method}")
            self._pending_requests.pop(request_id, None)
            self.stats.failed_requests += 1
            return None
            
        except Exception as e:
            logger.error(f"Request error for {self.name}: {e}")
            self._pending_requests.pop(request_id, None)
            self.stats.failed_requests += 1
            return None
    
    async def _cleanup_transport(self) -> None:
        """Clean up transport resources."""
        try:
            if self.config.protocol == "stdio" and self._transport:
                self._transport.terminate()
                try:
                    self._transport.wait(timeout=5)
                except:
                    self._transport.kill()
                    
            elif self.config.protocol == "sse":
                if hasattr(self, "_response"):
                    self._response.close()
                if hasattr(self, "_session"):
                    await self._session.close()
                    
            elif self.config.protocol == "websocket" and self._transport:
                import websockets
                await self._transport.close()
                
        except Exception as e:
            logger.warning(f"Cleanup error for {self.name}: {e}")
        finally:
            self._transport = None
    
    async def disconnect(self) -> None:
        """Gracefully disconnect from server."""
        self._closed = True
        
        # Cancel tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            
        if self._reconnect_task:
            self._reconnect_task.cancel()
        
        # Cancel pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
        
        # Clean up
        await self._cleanup_transport()
        
        self._set_state(ConnectionState.CLOSED)
        logger.info(f"MCP connection closed: {self.name}")
    
    def get_info(self) -> dict[str, Any]:
        """Get connection information."""
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state.name,
            "protocol": self.config.protocol,
            "url": self.config.url,
            "is_connected": self.is_connected,
            "is_available": self.is_available,
            "stats": {
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "success_rate": self.stats.success_rate,
                "average_latency_ms": self.stats.average_latency_ms,
                "last_activity": self.stats.last_activity.isoformat() if self.stats.last_activity else None,
                "connect_time": self.stats.connect_time.isoformat() if self.stats.connect_time else None,
                "reconnect_attempts": self.stats.reconnect_attempts,
            },
        }