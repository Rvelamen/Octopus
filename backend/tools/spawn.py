"""Spawn tool for creating background subagents."""

from typing import Any, TYPE_CHECKING

from backend.tools.base import Tool

if TYPE_CHECKING:
    from backend.agent.subagent import SubagentManager
    from backend.agent.aggregator import SubagentAggregator


class SpawnTool(Tool):
    """
    Tool to spawn a subagent for background task execution.
    
    The subagent runs asynchronously and announces its result back
    to the main agent when complete.
    
    Supports both single spawn and batch spawn with aggregation.
    """
    
    def __init__(self, manager: "SubagentManager", aggregator: "SubagentAggregator | None" = None):
        self._manager = manager
        self._aggregator = aggregator
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_instance_id: int | None = None
    
    def set_context(self, channel: str, chat_id: str, session_instance_id: int | None = None) -> None:
        """Set the origin context for subagent announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_instance_id = session_instance_id
    
    @property
    def name(self) -> str:
        return "spawn"
    
    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done. "
            "You can specify an agent_role to use a specific subagent configuration. "
            "For multiple related tasks, use batch_spawn to aggregate results."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
                "agent_role": {
                    "type": "string",
                    "description": (
                        "Optional subagent role name (e.g., 'common-worker', 'code-reviewer'). "
                        "If not specified, uses default subagent configuration. "
                        "Available roles can be found in the system prompt under # SubAgents section."
                    ),
                },
                "tasks": {
                    "type": "array",
                    "description": (
                        "Array of tasks for batch spawn. Each item should have 'task' and optionally "
                        "'label' and 'agent_role'. When provided, all tasks will be executed in parallel "
                        "and results will be aggregated into a single summary."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string"},
                            "label": {"type": "string"},
                            "agent_role": {"type": "string"},
                        },
                        "required": ["task"],
                    },
                },
            },
            "required": ["task"],
        }
    
    async def execute(
        self,
        task: str,
        label: str | None = None,
        agent_role: str | None = None,
        tasks: list[dict[str, Any]] | None = None,
        **kwargs: Any
    ) -> str:
        """
        Spawn a subagent to execute the given task.
        
        If 'tasks' is provided, performs batch spawn with aggregation.
        Otherwise, spawns a single subagent.
        """
        # Batch spawn mode
        if tasks and len(tasks) > 0:
            return await self._batch_spawn(tasks)
        
        # Single spawn mode
        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            agent_role=agent_role,
            session_instance_id=self._session_instance_id,
        )
    
    async def _batch_spawn(self, tasks: list[dict[str, Any]]) -> str:
        """
        Spawn multiple subagents and aggregate their results.
        
        Args:
            tasks: List of task configurations, each with 'task', 'label', 'agent_role'
            
        Returns:
            Status message indicating the batch was started
        """
        if not self._aggregator:
            return "Error: Batch spawn requires aggregator, but none is configured."
        
        # Create a task group for aggregation
        group = await self._aggregator.create_group(
            expected_count=len(tasks),
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            session_instance_id=self._session_instance_id or 0,
        )
        
        # Spawn all subagents with the group ID
        spawned = []
        for task_config in tasks:
            result = await self._manager.spawn(
                task=task_config["task"],
                label=task_config.get("label"),
                origin_channel=self._origin_channel,
                origin_chat_id=self._origin_chat_id,
                agent_role=task_config.get("agent_role"),
                group_id=group.id,
                session_instance_id=self._session_instance_id,
            )
            spawned.append(result)
        
        return f"Batch spawn initiated with {len(tasks)} subagents (group: {group.id}). Results will be aggregated when all complete."
