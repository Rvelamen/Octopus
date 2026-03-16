"""Long-running task plugin system.

This module provides a generic framework for long-running task plugins
that can execute CLI tools with callback support.

Example usage:
    # In your plugin's handler.py
    from backend.core.longtask import LongTaskPlugin, LongTaskWorker

    class MyToolWorker(LongTaskWorker):
        task_type = "my_tool"
        tool_name = "my-cli"

        async def _handle_start(self, task_id, params):
            # Implement start logic
            pass

    class MyToolPlugin(LongTaskPlugin):
        def __init__(self, extension):
            super().__init__(extension)
            self.worker_class = MyToolWorker

    # In manifest.yaml
    # type: longtask
    # longtask:
    #   worker_class: "my_plugin.worker.MyToolWorker"
"""

from backend.core.longtask.base import LongTaskWorker, LongTaskPlugin
from backend.core.longtask.manager import LongTaskManager, TaskStatus, Task
from backend.core.longtask.registry import LongTaskRegistry

__all__ = [
    "LongTaskWorker",
    "LongTaskPlugin",
    "LongTaskManager",
    "LongTaskRegistry",
    "TaskStatus",
    "Task",
]
