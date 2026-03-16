"""Base classes for long-running task plugins."""

import asyncio
import json
from abc import abstractmethod
from pathlib import Path
from typing import Any, Callable

from loguru import logger


class LongTaskWorker:
    """Base class for long-running task workers.

    Subclasses implement specific CLI tool execution logic.
    Each worker handles one type of task (e.g., claude_code, cursor, etc.)

    Example:
        class ClaudeCodeWorker(LongTaskWorker):
            task_type = "claude_code"
            tool_name = "claude"

            async def _handle_start(self, task_id, params):
                # Start Claude Code in tmux
                pass
    """

    # Task type identifier - must be unique across all workers
    task_type: str = ""

    # CLI tool name (for checking availability)
    tool_name: str = ""

    # Default shell timeout
    default_timeout: float = 30.0

    def __init__(self):
        self._hooks: dict[str, Callable] = {}
        self._sessions: dict[str, dict] = {}  # task_id -> session info

    def register_hook(self, event: str, callback: Callable):
        """Register a hook callback.

        Args:
            event: Event name (e.g., "on_auth", "on_complete")
            callback: Async callback function
        """
        self._hooks[event] = callback

    async def trigger_hook(self, event: str, *args, **kwargs):
        """Trigger a hook callback."""
        callback = self._hooks.get(event)
        if callback:
            try:
                await callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"[LongTaskWorker] Hook error for {event}: {e}")

    async def execute(self, task: Any) -> dict:
        """Execute the task.

        Args:
            task: Task object containing id, action, params

        Returns:
            Task result dictionary
        """
        action = task.action
        task_id = task.id
        params = task.params

        logger.info(f"[LongTaskWorker] Executing {action} for task {task_id}")

        if action == "start":
            result = await self._handle_start(task_id, params)
        elif action == "send":
            result = await self._handle_send(task_id, params)
        elif action == "status":
            result = await self._handle_status(task_id, params)
        elif action == "kill":
            result = await self._handle_kill(task_id, params)
        elif action == "auth":
            result = await self._handle_auth(task_id, params)
        else:
            raise ValueError(f"Unknown action: {action}")

        # Trigger completion hook
        await self.trigger_hook("on_complete", task, result)

        return result

    @abstractmethod
    async def _handle_start(self, task_id: str, params: dict) -> dict:
        """Handle task start action.

        Args:
            task_id: Unique task identifier
            params: Task parameters from the plugin

        Returns:
            Result dictionary with at least {"status": "..."}
        """
        pass

    @abstractmethod
    async def _handle_send(self, task_id: str, params: dict) -> dict:
        """Handle sending input to a running task.

        Args:
            task_id: Task identifier
            params: Must contain "input" or "prompt" key

        Returns:
            Result dictionary
        """
        pass

    @abstractmethod
    async def _handle_status(self, task_id: str, params: dict) -> dict:
        """Handle status check.

        Args:
            task_id: Task identifier
            params: Optional filter parameters

        Returns:
            Result dictionary with status info
        """
        pass

    @abstractmethod
    async def _handle_kill(self, task_id: str, params: dict) -> dict:
        """Handle task termination.

        Args:
            task_id: Task identifier
            params: Optional parameters

        Returns:
            Result dictionary
        """
        pass

    async def _handle_auth(self, task_id: str, params: dict) -> dict:
        """Handle authorization response.

        Override this if your tool needs custom auth handling.

        Args:
            task_id: Task identifier
            params: Must contain "action" key (e.g., "approve", "deny")

        Returns:
            Result dictionary
        """
        # Default implementation - subclasses can override
        return {"status": "auth_received", "task_id": task_id, "action": params.get("action")}

    async def run_shell(
        self,
        command: list[str],
        timeout: float | None = None,
        cwd: str | None = None,
        env: dict | None = None,
    ) -> dict:
        """Run a shell command asynchronously.

        Args:
            command: Command and arguments as a list
            timeout: Timeout in seconds (default: default_timeout)
            cwd: Working directory
            env: Environment variables

        Returns:
            Dict with stdout, stderr, returncode, and success flag
        """
        timeout = timeout or self.default_timeout

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
            }

        except asyncio.TimeoutError:
            try:
                proc.kill()
            except:
                pass
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }

    def get_hook_config(self, callback_url: str, task_id: str) -> dict:
        """Generate hook configuration for the CLI tool.

        Override this to provide tool-specific hook configuration.
        The default implementation returns an empty config.

        Args:
            callback_url: URL for callbacks
            task_id: Task identifier

        Returns:
            Hook configuration dictionary
        """
        # Default: no hooks
        return {}

    async def setup_hooks(self, workdir: str, callback_url: str, task_id: str) -> bool:
        """Setup hooks in the working directory.

        Args:
            workdir: Working directory
            callback_url: Callback URL
            task_id: Task identifier

        Returns:
            True if setup successful
        """
        # Default: no setup needed
        return True


class LongTaskPlugin:
    """Base class for long-running task plugins.

    This class bridges the PluginHandler interface with the LongTaskWorker.

    Example:
        class ClaudeCodePlugin(LongTaskPlugin):
            def __init__(self, extension):
                super().__init__(extension)
                self.worker_class = ClaudeCodeWorker
    """

    # Standard actions supported by all longtask plugins
    actions = ["start", "send", "status", "kill", "auth", "list"]

    def __init__(self, extension):
        self.extension = extension
        self.worker_class: type[LongTaskWorker] | None = None
        self._worker_instance: LongTaskWorker | None = None

    def get_worker(self) -> LongTaskWorker:
        """Get or create worker instance."""
        if self._worker_instance is None and self.worker_class:
            self._worker_instance = self.worker_class()
        return self._worker_instance

    async def execute(self, action: str, **kwargs) -> dict:
        """Execute a plugin action.

        This method is called by the PluginHandler system.
        It delegates to the LongTaskManager.

        Args:
            action: Action name (start, send, status, kill)
            **kwargs: Action parameters

        Returns:
            Plugin result dictionary
        """
        from backend.core.longtask.manager import get_longtask_manager

        manager = get_longtask_manager()

        # Get task type from worker class
        worker = self.get_worker()
        if not worker:
            return {"success": False, "error": "Worker not configured"}

        task_type = worker.task_type

        # Extract common parameters
        # Try to get channel/chat_id from kwargs, or use extension's directory name as fallback
        channel = kwargs.get("channel", "desktop")  # Default to desktop channel
        chat_id = kwargs.get("chat_id", "default")
        session = kwargs.get("session", f"{task_type}_{asyncio.get_event_loop().time()}")
        session_instance_id = kwargs.get("session_instance_id")  # Current session instance when task is created

        # Get callback URL for hooks
        callback_url = manager.get_hook_url(plugin_name=task_type)

        if action == "start":
            # Create new task with callback_url and session_instance_id
            # session_instance_id ensures auth/completion messages are saved to the correct instance
            task_id = await manager.create_task(
                task_type=task_type,
                action="start",
                params={
                    "session": session,
                    "callback_url": callback_url,
                    "session_instance_id": session_instance_id,  # Record the instance where task was created
                    **{k: v for k, v in kwargs.items() if k not in ["channel", "chat_id", "session", "session_instance_id"]},
                },
                channel=channel,
                chat_id=chat_id,
            )

            return {
                "success": True,
                "task_id": task_id,
                "session": session,
                "status": "started",
                "message": f"Claude Code 任务已启动",
                "details": {
                    "task_id": task_id,
                    "session": session,
                    "workdir": kwargs.get("workdir", ""),
                    "prompt_preview": kwargs.get("prompt", "")[:100] + "..." if len(kwargs.get("prompt", "")) > 100 else kwargs.get("prompt", ""),
                },
                "note": "任务正在后台运行。当需要授权或任务完成时，我会通知您。",
            }

        elif action in ("send", "status", "kill"):
            # Find existing task by session
            task = None
            for t in manager.list_tasks():
                if t.params.get("session") == session and t.type == task_type:
                    task = t
                    break

            if not task:
                return {"success": False, "error": f"Session '{session}' not found"}

            if action == "send":
                # Update task action and params
                new_task_id = await manager.create_task(
                    task_type=task_type,
                    action="send",
                    params={
                        "session": session,
                        "prompt": kwargs.get("prompt", ""),
                    },
                    channel=channel,
                    chat_id=chat_id,
                )
                return {
                    "success": True,
                    "task_id": new_task_id,
                    "session": session,
                    "status": "message_sent",
                }

            elif action == "status":
                return {
                    "success": True,
                    "task_id": task.id,
                    "session": session,
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat(),
                }

            elif action == "kill":
                new_task_id = await manager.create_task(
                    task_type=task_type,
                    action="kill",
                    params={"session": session},
                    channel=channel,
                    chat_id=chat_id,
                )
                return {
                    "success": True,
                    "task_id": new_task_id,
                    "session": session,
                    "status": "kill_requested",
                }

        elif action == "auth":
            # Handle authorization response - execute immediately
            # Find existing task by session
            task = None
            for t in manager.list_tasks():
                if t.params.get("session") == session and t.type == task_type:
                    task = t
                    break

            if not task:
                return {"success": False, "error": f"Session '{session}' not found"}

            # Get auth action (approve, deny, always, skip)
            auth_action = kwargs.get("auth_action", "approve")

            # Execute auth immediately using worker
            worker = manager.get_worker(task_type)
            if not worker:
                return {"success": False, "error": f"Worker for {task_type} not found"}

            try:
                # Directly execute auth on the worker
                result = await worker._handle_auth(task.id, {
                    "session": session,
                    "action": auth_action,
                })

                return {
                    "success": True,
                    "task_id": task.id,
                    "session": session,
                    "auth_action": auth_action,
                    "status": "auth_executed",
                    "result": result,
                }
            except Exception as e:
                logger.error(f"[LongTaskPlugin] Auth execution failed: {e}")
                return {"success": False, "error": f"Auth execution failed: {str(e)}"}

        elif action == "list":
            # List all tasks of this task type
            from backend.core.longtask.manager import TaskStatus

            status_filter = kwargs.get("status")
            status_enum = None
            if status_filter:
                try:
                    status_enum = TaskStatus(status_filter)
                except ValueError:
                    pass

            tasks = manager.list_tasks(task_type=task_type, status=status_enum)

            return {
                "success": True,
                "tasks": [t.to_dict() for t in tasks],
                "total": len(tasks),
                "task_type": task_type,
            }

        else:
            return {"success": False, "error": f"Unknown action: {action}"}
