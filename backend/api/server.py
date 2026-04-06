"""FastAPI service for Octopus Desktop."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from backend.core.events.bus import MessageBus
from backend.core.events.types import InboundMessage, OutboundMessage, AgentEvent
from backend.utils import init_workspace_path, get_workspace_path


# Global instances
agent_loop = None  # Main agent loop for user messages
agent_task = None
channel_manager = None


def get_channel_manager():
    """Get the global channel manager instance."""
    return channel_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle: start/stop agent loop and channels.
    """
    global agent_loop, agent_task, channel_manager
    
    logger.info("=== STARTING LIFESPAN ===")
    
    logger.info("Starting Octopus Desktop Service...")

    # 1. Initialize Database first
    from backend.data import Database, init_system_providers
    db = Database()
    init_system_providers(db)

    # 2. Initialize Message Bus
    bus = MessageBus()

    # 3. Initialize workspace path from database
    from backend.data.provider_store import AgentDefaultsRepository
    from backend.services.workspace_service import setup_workspace_from_template
    from backend.utils.helpers import get_data_path

    agent_defaults_repo = AgentDefaultsRepository(db)
    agent_defaults = agent_defaults_repo.get_or_create_defaults()
    workspace_path = agent_defaults.workspace_path

    # Determine actual workspace path
    if not workspace_path:
        workspace_path = get_data_path() / "workspace"

    workspace = Path(workspace_path)

    # Copy template files to workspace if workspace is empty or doesn't exist
    if not workspace.exists() or not any(workspace.iterdir()):
        logger.info(f"Workspace {workspace} is empty or doesn't exist, copying template files...")
        setup_workspace_from_template(workspace)

    # Update database with the actual workspace path if it was empty
    if not agent_defaults.workspace_path:
        agent_defaults_repo.update_agent_defaults(workspace_path=str(workspace))

    workspace = init_workspace_path(str(workspace))
    print(f"Workspace: {workspace}")
    print(f"Workspace Path: {get_workspace_path()}")

    # 4. Initialize Agent Loop (Lazy import to avoid circular deps)
    from backend.agent.loop import AgentLoop
    from backend.channels.manager import ChannelManager
    
    from backend.mcp.manager import MCPManager
    from backend.mcp.llm_bridge import MCPBridgeIntegration
    mcp_manager = MCPManager(db=db)
    if mcp_manager.config.enabled:
        await mcp_manager.initialize()
    mcp_bridge = MCPBridgeIntegration(mcp_manager)
    
    from backend.agent.subagent import SubagentManager
    from backend.services.cron import CronService
    from backend.core.events.types import OutboundMessage
    from backend.core.config.schema import ExecToolConfig
    from backend.data import SessionManager

    exec_config = ExecToolConfig()
    subagent_manager = SubagentManager(
        workspace=workspace,
        bus=bus,
        exec_config=exec_config
    )

    async def publish_message(channel: str, chat_id: str, content: str) -> None:
        """Publish message to user via message bus."""
        await bus.publish_outbound(OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content
        ))

    cron_service = CronService(
        db=db,
        publish_message=publish_message,
        subagent_manager=subagent_manager,
    )
    await cron_service.start()

    agent_loop = AgentLoop(
        bus=bus,
        workspace=workspace,
        max_iterations=20,
        db=db,
        exec_config=exec_config,
        cron_service=cron_service,
        subagent_manager=subagent_manager,
        mcp_bridge=mcp_bridge,
    )
    
    # 4. Initialize Desktop Channel
    from backend.channels.desktop.channel import DesktopChannel
    from backend.channels.desktop.config import DesktopConfig

    desktop_config = DesktopConfig()
    desktop_channel = DesktopChannel(
        config=desktop_config,
        bus=bus,
        app=app,
        mcp_manager=mcp_manager,
        cron_service=cron_service,
        agent_loop=agent_loop,
        subagent_manager=subagent_manager
    )
    
    # 5. Initialize Channel Manager with Desktop Channel
    logger.info(f"Creating ChannelManager with desktop channel: {desktop_channel}")
    channel_manager = ChannelManager(bus=bus, workspace=workspace, custom_channels={"desktop": desktop_channel})
    
    # 6. Subscribe Desktop Channel to Events
    logger.info(f"Event subscribers before: {bus._event_subscribers}")
    bus.subscribe_event(desktop_channel._handle_event)
    logger.info(f"Event subscribers after: {bus._event_subscribers}")

    # 7. Start Agent Loop in background
    agent_task = asyncio.create_task(agent_loop.run())
    logger.info("Agent loop started")

    # 8. Start Channel Manager (includes desktop channel and outbound dispatcher)
    channel_manager_task = asyncio.create_task(channel_manager.start_all())
    logger.info("Channel manager started")

    # 9. Start Event Dispatcher in background
    event_dispatch_task = asyncio.create_task(bus.dispatch_events())
    logger.info("Event dispatcher started")

    # 10. Mount workspace directory for static file serving (images)
    # This must be done after init_workspace_path() is called
    from fastapi.staticfiles import StaticFiles
    from backend.utils.helpers import get_data_path
    workspace_path = get_workspace_path()
    app.mount("/workspace", StaticFiles(directory=str(workspace_path)), name="workspace")
    logger.info(f"Mounted /workspace to {workspace_path}")

    yield

    # Shutdown
    logger.info("Shutting down Octopus Desktop Service...")

    # Stop cron service
    if cron_service:
        cron_service.stop()
    
    # Stop channels via ChannelManager
    if channel_manager:
        await channel_manager.stop_all()
    if channel_manager_task:
        channel_manager_task.cancel()
    
    # Stop agent loop
    if agent_loop:
        agent_loop.stop()
    if agent_task:
        agent_task.cancel()
        
    if event_dispatch_task:
        bus.stop()
        event_dispatch_task.cancel()
        
    logger.info("Service stopped.")


app = FastAPI(lifespan=lifespan)

# CORS configuration - restricted to known origins for security
# Desktop app uses file:// protocol, development uses localhost
ALLOWED_ORIGINS = [
    "http://localhost:3000",    # Vite dev server
    "http://127.0.0.1:3000",    # Vite dev server (alternative)
    "http://localhost:5173",    # Vite default port (if changed)
    "http://127.0.0.1:5173",    # Vite default port (alternative)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount wechat qrcodes directory upfront
from fastapi.staticfiles import StaticFiles
from backend.utils.helpers import get_data_path
wechat_qrcodes_dir = get_data_path() / "wechat_qrcodes"
wechat_qrcodes_dir.mkdir(parents=True, exist_ok=True)
app.mount("/wechat_qrcodes", StaticFiles(directory=str(wechat_qrcodes_dir)), name="wechat_qrcodes")


@app.post("/hooks/longtask/{plugin_name}")
async def longtask_hook(plugin_name: str, request: dict):
    """Handle hooks from long-running task plugins.

    This endpoint receives callbacks from CLI tools when:
    - Task needs user authorization (type: auth)
    - Task is completed (type: complete)
    - Other events

    Instead of directly notifying the user, this creates an InboundMessage
    to trigger the main Agent to handle the event. This allows for natural
    conversation flow.

    Args:
        plugin_name: Name of the plugin that sent the hook
        request: Hook data containing type, task_id, etc.

    Returns:
        Response dict
    """
    from backend.core.longtask.manager import get_longtask_manager, TaskStatus
    from backend.core.events.types import InboundMessage

    manager = get_longtask_manager()

    # Update hook endpoint with actual port
    manager.set_hook_endpoint("127.0.0.1", PORT, "/hooks/longtask")

    hook_type = request.get("type")
    task_id = request.get("task_id")

    if not task_id:
        return {"success": False, "error": "Missing task_id"}

    task = manager.get_task(task_id)
    if not task:
        return {"success": False, "error": f"Task {task_id} not found"}

    # Update task status based on hook type
    if hook_type == "auth":
        # Task needs authorization
        await manager._update_task_status(task_id, TaskStatus.WAITING_AUTH)

        # Mark as notified
        task._auth_notified = True

        # Get auth details from request
        prompt = request.get("prompt", "未知操作")
        session = task.params.get("session", task_id)

        # Get plugin name from hook request, fallback to URL parameter
        plugin_display_name = request.get("plugin_name", plugin_name)

        # Save auth request to session and notify user
        if agent_loop:
            try:
                session_key = f"{task.channel}:{task.chat_id}"
                session_mgr = agent_loop.sessions
                session_obj = session_mgr.get_or_create(session_key)

                # Build auth content
                auth_content = f"任务 `{task_id}` (session: {session}) 需要授权确认。\n\n**授权内容**：{prompt}\n\n**工具**：{plugin_display_name}\n\n请回复批准或拒绝。"

                # Add to session for context
                session_obj.add_message("assistant", auth_content, message_type="longtask_auth")

                # Use the session_instance_id from task params if available
                # This ensures the message is saved to the instance where the task was created
                session_instance_id = task.params.get("session_instance_id")
                if session_instance_id:
                    session_mgr.save_to_instance(session_obj, session_instance_id)
                    logger.info(f"[LongTaskHook] Saved auth request to session {session_key}, instance {session_instance_id}")
                else:
                    session_mgr.save(session_obj)
                    logger.info(f"[LongTaskHook] Saved auth request to session {session_key} (using active instance)")

                # Create InboundMessage to trigger main Agent
                if agent_loop.bus:
                    msg = InboundMessage(
                        channel=task.channel,
                        chat_id=task.chat_id,
                        sender_id="system",
                        content=auth_content,
                        message_type="longtask_auth",
                    )
                    await agent_loop.bus.publish_inbound(msg)
            except Exception as e:
                logger.warning(f"[LongTaskHook] Failed to save auth to session: {e}")
                import traceback
                logger.warning(traceback.format_exc())

    elif hook_type == "complete":
        # Task completed
        task._completion_event.set()

        # Create InboundMessage to notify completion
        if agent_loop and agent_loop.bus:
            msg = InboundMessage(
                channel=task.channel,
                chat_id=task.chat_id,
                sender_id="system",
                content=f"任务 `{task_id}` 已完成。",
                message_type="longtask_complete",
            )
            await agent_loop.bus.publish_inbound(msg)

    return {"success": True, "hook_type": hook_type}


# Keep backward compatibility with old endpoint
@app.post("/hooks/claude-code")
async def claude_code_hook_legacy(request: dict):
    """Legacy endpoint for Claude Code hooks (backward compatibility)."""
    return await longtask_hook("claude-code", request)


logger.info("Octopus Desktop Service initialized.")

import uvicorn

PORT = int(os.environ.get("OCTOPUS_PORT", 18791))

if __name__ == "__main__":
    logger.info(f"Starting Octopus Desktop Service on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
