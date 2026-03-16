"""Long-running task manager with callback support."""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from loguru import logger


class TaskStatus(Enum):
    """Task status states."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_AUTH = "waiting_auth"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task:
    """Represents a long-running task."""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        action: str,
        params: dict,
        channel: str,
        chat_id: str,
    ):
        self.id = task_id
        self.type = task_type
        self.action = action
        self.params = params
        self.channel = channel
        self.chat_id = chat_id

        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.completed_at = None

        self.result = None
        self.error = None

        # For blocking/waiting mechanism
        self._auth_event = asyncio.Event()
        self._auth_response = None
        self._completion_event = asyncio.Event()

        # Callbacks
        self._on_auth_request: Callable | None = None
        self._on_complete: Callable | None = None

    def to_dict(self) -> dict:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "action": self.action,
            "params": self.params,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "channel": self.channel,
            "chat_id": self.chat_id,
        }


class LongTaskManager:
    """Manages long-running tasks with support for blocking and callbacks.

    This is a generic manager that works with any LongTaskWorker implementation.
    Workers are registered dynamically based on task type.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.tasks: dict[str, Task] = {}
        self.workers: dict[str, Any] = {}  # task_type -> worker instance
        self._lock = asyncio.Lock()
        self._initialized = True

        # Hook URL configuration
        self.hook_host = "127.0.0.1"
        self.hook_port = 18791
        self.hook_path = "/hooks/longtask"

        logger.info("[LongTaskManager] Initialized")

    def set_hook_endpoint(self, host: str, port: int, path: str = "/hooks/longtask"):
        """Set the hook endpoint for callbacks."""
        self.hook_host = host
        self.hook_port = port
        self.hook_path = path
        logger.info(f"[LongTaskManager] Hook endpoint set to {host}:{port}{path}")

    def get_hook_url(self, plugin_name: str | None = None) -> str:
        """Get the hook URL for callbacks.

        Args:
            plugin_name: Optional plugin name for plugin-specific hooks
        """
        base = f"http://{self.hook_host}:{self.hook_port}{self.hook_path}"
        if plugin_name:
            return f"{base}/{plugin_name}"
        return base

    def register_worker(self, task_type: str, worker: Any):
        """Register a worker for a task type.

        Args:
            task_type: Task type identifier
            worker: LongTaskWorker instance
        """
        self.workers[task_type] = worker
        logger.info(f"[LongTaskManager] Registered worker for task type: {task_type}")

    def get_worker(self, task_type: str) -> Any | None:
        """Get worker for task type."""
        return self.workers.get(task_type)

    async def create_task(
        self,
        task_type: str,
        action: str,
        params: dict,
        channel: str,
        chat_id: str,
    ) -> str:
        """Create a new task.

        Args:
            task_type: Type of task (e.g., "claude_code")
            action: Action to perform (e.g., "start")
            params: Task parameters
            channel: Channel name
            chat_id: Chat ID

        Returns:
            Task ID
        """
        task_id = f"{task_type}_{uuid.uuid4().hex[:8]}"

        task = Task(
            task_id=task_id,
            task_type=task_type,
            action=action,
            params=params,
            channel=channel,
            chat_id=chat_id,
        )

        async with self._lock:
            self.tasks[task_id] = task

        logger.info(f"[LongTaskManager] Created task {task_id} of type {task_type}")

        # Save task to database
        await self._save_task_to_db(task)

        # Start the task in background
        asyncio.create_task(self._run_task(task))

        return task_id

    async def _save_task_to_db(self, task: Task) -> None:
        """Save task to database for persistence."""
        try:
            from backend.data import Database
            import json

            db = Database()

            # Check if tasks table exists (it should from database.py)
            db.execute_one("""
                SELECT 1 FROM sqlite_master
                WHERE type='table' AND name='tasks'
            """)

            # Get or create session and instance
            session_key = f"{task.channel}:{task.chat_id}"
            session_row = db.execute_one(
                "SELECT id FROM sessions WHERE session_key = ?",
                (session_key,)
            )

            if session_row:
                session_id = session_row['id']
            else:
                # Create new session
                db.execute("""
                    INSERT INTO sessions (channel, chat_id, session_key, metadata)
                    VALUES (?, ?, ?, '{}')
                """, (task.channel, task.chat_id, session_key))
                session_row = db.execute_one(
                    "SELECT id FROM sessions WHERE session_key = ?",
                    (session_key,)
                )
                session_id = session_row['id']

            # Get or create default instance
            instance_row = db.execute_one(
                "SELECT id FROM session_instances WHERE session_id = ? AND instance_name = 'default'",
                (session_id,)
            )

            if instance_row:
                instance_id = instance_row['id']
            else:
                # Create default instance
                db.execute("""
                    INSERT INTO session_instances (session_id, instance_name, is_active)
                    VALUES (?, 'default', 1)
                """, (session_id,))
                instance_row = db.execute_one(
                    "SELECT id FROM session_instances WHERE session_id = ? AND instance_name = 'default'",
                    (session_id,)
                )
                instance_id = instance_row['id']

            # Insert or update task
            db.execute("""
                INSERT OR REPLACE INTO tasks (
                    id, type, action, status, parent_session, parent_instance_id,
                    channel, chat_id, input_params, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id,
                task.type,
                task.action,
                task.status.value,
                session_key,
                instance_id,
                task.channel,
                task.chat_id,
                json.dumps(task.params, ensure_ascii=False),
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            ))

            logger.info(f"[LongTaskManager] Task {task.id} saved to database")
        except Exception as e:
            logger.warning(f"[LongTaskManager] Failed to save task to database: {e}")

    async def _update_task_in_db(self, task: Task) -> None:
        """Update task status in database."""
        try:
            from backend.data import Database
            import json

            db = Database()

            db.execute("""
                UPDATE tasks SET
                    status = ?,
                    updated_at = ?,
                    completed_at = ?,
                    result_summary = ?,
                    error_message = ?
                WHERE id = ?
            """, (
                task.status.value,
                task.updated_at.isoformat(),
                task.completed_at.isoformat() if task.completed_at else None,
                json.dumps(task.result, ensure_ascii=False) if task.result else None,
                task.error,
                task.id,
            ))
        except Exception as e:
            logger.warning(f"[LongTaskManager] Failed to update task in database: {e}")

    async def _run_task(self, task: Task):
        """Run a task with the appropriate worker."""
        async with self._lock:
            task.status = TaskStatus.RUNNING
            task.updated_at = datetime.now()

        # Update task status in database
        await self._update_task_in_db(task)

        try:
            # Get worker for this task type
            worker = self.get_worker(task.type)

            if not worker:
                # Try to load worker dynamically
                worker = await self._load_worker(task.type)

            if worker:
                # Register hooks
                worker.register_hook("on_auth", lambda t, data: self._on_worker_auth(t, data))
                worker.register_hook("on_complete", lambda t, r: self._on_worker_complete(t, r))

                # Execute the task
                result = await worker.execute(task)

                async with self._lock:
                    task.result = result
                    if task.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                        task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()
                    task.updated_at = datetime.now()

                # Update task in database
                await self._update_task_in_db(task)

                # Signal completion
                task._completion_event.set()

                # Trigger callback if set
                if task._on_complete:
                    await task._on_complete(task)

                logger.info(f"[LongTaskManager] Task {task.id} completed")
            else:
                raise ValueError(f"No worker found for task type: {task.type}")

        except Exception as e:
            logger.error(f"[LongTaskManager] Task {task.id} failed: {e}")

            async with self._lock:
                task.error = str(e)
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                task.updated_at = datetime.now()

            # Update task in database
            await self._update_task_in_db(task)

            task._completion_event.set()

    async def _load_worker(self, task_type: str) -> Any | None:
        """Dynamically load a worker for the task type.

        This method tries to find and instantiate a worker from registered plugins.
        """
        from backend.extensions.registry import get_registry

        registry = get_registry()

        # Find plugin that handles this task type
        for ext in registry.list_all():
            if ext.type == "longtask":
                longtask_config = ext.manifest.get("longtask", {})
                if longtask_config.get("task_type") == task_type:
                    # Found matching plugin, load its worker
                    worker_class_path = longtask_config.get("worker_class")
                    if worker_class_path:
                        try:
                            # Import worker class
                            module_path, class_name = worker_class_path.rsplit(".", 1)
                            module = __import__(module_path, fromlist=[class_name])
                            worker_class = getattr(module, class_name)
                            worker = worker_class()

                            # Register worker
                            self.register_worker(task_type, worker)
                            return worker
                        except Exception as e:
                            logger.error(f"[LongTaskManager] Failed to load worker {worker_class_path}: {e}")

        return None

    async def _on_worker_auth(self, task: Task, data: dict):
        """Handle auth request from worker."""
        async with self._lock:
            task.status = TaskStatus.WAITING_AUTH
            task.updated_at = datetime.now()

        if task._on_auth_request:
            await task._on_auth_request(task, data)

    async def _on_worker_complete(self, task: Task, result: dict):
        """Handle completion from worker."""
        pass  # Already handled in _run_task

    async def _update_task_status(self, task_id: str, status: TaskStatus):
        """Update task status.

        Args:
            task_id: Task ID
            status: New status
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.status = status
                task.updated_at = datetime.now()
                logger.info(f"[LongTaskManager] Task {task_id} status updated to {status.value}")

        # Update task in database
        if task:
            await self._update_task_in_db(task)

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        task_type: str | None = None,
    ) -> list[Task]:
        """List all tasks, optionally filtered."""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if task_type:
            tasks = [t for t in tasks if t.type == task_type]
        return tasks

    async def wait_for_auth(self, task_id: str, timeout: float | None = None) -> dict | None:
        """Wait for authorization response for a task.

        Args:
            task_id: Task ID
            timeout: Optional timeout in seconds

        Returns:
            Auth response data or None if timeout
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        try:
            await asyncio.wait_for(task._auth_event.wait(), timeout=timeout)
            return task._auth_response
        except asyncio.TimeoutError:
            return None

    async def respond_to_auth(self, task_id: str, response: dict) -> bool:
        """Respond to an authorization request.

        Args:
            task_id: Task ID
            response: Response data

        Returns:
            True if response was accepted
        """
        task = self.tasks.get(task_id)
        if not task:
            logger.warning(f"[LongTaskManager] Cannot respond to auth: task {task_id} not found")
            return False

        if task.status != TaskStatus.WAITING_AUTH:
            logger.warning(f"[LongTaskManager] Task {task_id} is not waiting for auth")
            return False

        task._auth_response = response
        task._auth_event.set()

        logger.info(f"[LongTaskManager] Auth response received for task {task_id}")

        # Forward to worker if it has auth handling
        worker = self.get_worker(task.type)
        if worker:
            try:
                await worker.execute(Task(
                    task_id=task_id,
                    task_type=task.type,
                    action="auth",
                    params={"action": response.get("action"), "original_task": task},
                    channel=task.channel,
                    chat_id=task.chat_id,
                ))
            except Exception as e:
                logger.error(f"[LongTaskManager] Error forwarding auth to worker: {e}")

        return True

    async def handle_hook(self, plugin_name: str, hook_data: dict) -> dict:
        """Handle a hook callback from a CLI tool.

        Args:
            plugin_name: Name of the plugin that sent the hook
            hook_data: Hook data

        Returns:
            Response dict
        """
        hook_type = hook_data.get("type")
        task_id = hook_data.get("task_id")

        logger.info(f"[LongTaskManager] Received hook from {plugin_name}: type={hook_type}, task_id={task_id}")

        if not task_id:
            return {"success": False, "error": "Missing task_id"}

        task = self.tasks.get(task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}

        if hook_type == "auth":
            # Tool needs authorization
            async with self._lock:
                task.status = TaskStatus.WAITING_AUTH
                task.updated_at = datetime.now()

            # Trigger auth request callback
            if task._on_auth_request:
                await task._on_auth_request(task, hook_data)

            return {"success": True, "message": "Auth request received"}

        elif hook_type == "complete":
            # Task completed
            task._completion_event.set()

            if task._on_complete:
                await task._on_complete(task)

            return {"success": True, "message": "Completion acknowledged"}

        else:
            return {"success": False, "error": f"Unknown hook type: {hook_type}"}

    async def wait_for_completion(self, task_id: str, timeout: float | None = None) -> Task | None:
        """Wait for a task to complete.

        Args:
            task_id: Task ID
            timeout: Optional timeout in seconds

        Returns:
            Task object or None if timeout
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        try:
            await asyncio.wait_for(task._completion_event.wait(), timeout=timeout)
            return task
        except asyncio.TimeoutError:
            return None


# Global instance
_longtask_manager: LongTaskManager | None = None


def get_longtask_manager() -> LongTaskManager:
    """Get the global LongTaskManager instance."""
    global _longtask_manager
    if _longtask_manager is None:
        _longtask_manager = LongTaskManager()
    return _longtask_manager


def set_longtask_manager(manager: LongTaskManager):
    """Set the global LongTaskManager instance."""
    global _longtask_manager
    _longtask_manager = manager
