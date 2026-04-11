"""Spawn tool for creating subagents (sync or async)."""

import json
import asyncio
from typing import Any, TYPE_CHECKING

from loguru import logger

from backend.tools.base import Tool

if TYPE_CHECKING:
    from backend.agent.subagent import SubagentManager
    from backend.agent.aggregator import SubagentAggregator


class SpawnTool(Tool):
    """
    Tool to spawn a subagent to handle a task.
    
    Supports two execution modes:
    - sync: Wait for subagent completion and return result immediately
    - async: Run in background, result announced later via message bus
    
    Note: Sync mode has a fixed timeout of 30 minutes (1800 seconds) for long-running tasks.
    """

    SYNC_TIMEOUT = 1800  # 固定 30 分钟超时

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
            "Spawn a subagent to handle a task. "
            "Use 'sync' mode when you need the result immediately to answer the user. "
            "Use 'async' mode for long-running background tasks. "
            "You can specify an agent_role to use a specific subagent configuration. "
            "For multiple related tasks, use batch spawn (always async)."
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
                "mode": {
                    "type": "string",
                    "enum": ["sync", "async"],
                    "description": (
                        "Execution mode: "
                        "'sync' - wait for result (use for tasks that need immediate answer), "
                        "'async' - run in background (use for long-running tasks). "
                        "Default: 'async'"
                    ),
                    "default": "async",
                },
                "agent_role": {
                    "type": "string",
                    "description": (
                        "Optional subagent role name (e.g., 'common-worker', 'code-reviewer'). "
                        "Available roles can be found in the system prompt under # SubAgents section."
                    ),
                },
                "tasks": {
                    "type": "array",
                    "description": (
                        "Array of tasks for batch spawn. Each item should have 'task' and optionally "
                        "'label' and 'agent_role'. When provided, all tasks will be executed in parallel "
                        "and results will be aggregated into a single summary. Batch spawn is always async."
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
        mode: str = "async",
        agent_role: str | None = None,
        tasks: list[dict[str, Any]] | None = None,
        **kwargs: Any
    ) -> str:
        """
        Spawn a subagent to execute the given task.

        Args:
            mode: 'sync' to wait for result, 'async' for background execution
            parent_tool_call_id: Parent tool call ID (injected by AgentLoop)
        """
        parent_tool_call_id = kwargs.get("parent_tool_call_id")
        
        if tasks and len(tasks) > 0:
            return await self._batch_spawn(tasks)
        
        if mode == "sync":
            return await self._execute_sync(task, label, agent_role, parent_tool_call_id)
        
        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            agent_role=agent_role,
            session_instance_id=self._session_instance_id,
            parent_tool_call_id=parent_tool_call_id,
        )

    async def _execute_sync(
        self,
        task: str,
        label: str | None,
        agent_role: str | None,
        parent_tool_call_id: str | None = None,
    ) -> str:
        """同步执行：阻塞等待子代理结果（固定 30 分钟超时）"""
        
        try:
            task_id, result_future = await self._manager.spawn_sync_task(
                task=task,
                label=label,
                origin_channel=self._origin_channel,
                origin_chat_id=self._origin_chat_id,
                agent_role=agent_role,
                session_instance_id=self._session_instance_id,
                parent_tool_call_id=parent_tool_call_id,
            )
            
            result = await asyncio.wait_for(result_future, timeout=self.SYNC_TIMEOUT)
            
            if isinstance(result, dict):
                summary = result.get("summary", "")
                token_usage = result.get("token_usage", {})
                duration = result.get("duration", 0)
                iterations = result.get("iterations", [])
            else:
                summary = str(result)
                token_usage = {}
                duration = 0
                iterations = []
            
            if token_usage:
                self._record_subagent_token_usage(token_usage, agent_role)
            
            logger.info(f"[Spawn:sync] Task {task_id} completed in {duration:.1f}s")
            
            return json.dumps({
                "type": "subagent_sync",
                "status": "completed",
                "task_id": task_id,
                "label": label or task[:30] + ("..." if len(task) > 30 else ""),
                "summary": summary,
                "token_usage": token_usage,
                "duration": round(duration, 1),
                "iterations": iterations,
            }, ensure_ascii=False)
            
        except asyncio.TimeoutError:
            logger.warning(f"[Spawn:sync] Task timed out after {self.SYNC_TIMEOUT}s")
            return json.dumps({
                "type": "subagent_sync",
                "status": "timeout",
                "task_id": "unknown",
                "label": label or task[:30] + ("..." if len(task) > 30 else ""),
                "summary": f"子代理未能在 {self.SYNC_TIMEOUT} 秒内完成，仍在后台运行。完成后会通过系统消息通知。",
                "token_usage": {},
                "duration": self.SYNC_TIMEOUT,
                "iterations": [],
            }, ensure_ascii=False)
            
        except Exception as e:
            error_msg = str(e)
            if "Streaming is required" in error_msg or "10 minutes" in error_msg:
                logger.warning(f"[Spawn:sync] Task failed: Anthropic 10-minute limit exceeded")
                return json.dumps({
                    "type": "subagent_sync",
                    "status": "error",
                    "task_id": "unknown",
                    "label": label or task[:30] + ("..." if len(task) > 30 else ""),
                    "summary": (
                        f"⚠️ 任务执行时间超过 10 分钟 (Anthropic API 限制)。\n\n"
                        f"**建议解决方案：**\n"
                        f"1. 将 `mode` 改为 `'async'`，让任务在后台执行\n"
                        f"2. 简化任务描述，减少需要执行的步骤\n"
                        f"3. 拆分任务为多个小任务，使用 batch spawn\n\n"
                        f"原始错误：{error_msg}"
                    ),
                    "token_usage": {},
                    "duration": 0,
                    "iterations": [],
                }, ensure_ascii=False)
            
            logger.error(f"[Spawn:sync] Task failed: {e}")
            return json.dumps({
                "type": "subagent_sync",
                "status": "error",
                "task_id": "unknown",
                "label": label or task[:30] + ("..." if len(task) > 30 else ""),
                "summary": f"子代理执行失败：{error_msg}",
                "token_usage": {},
                "duration": 0,
                "iterations": [],
            }, ensure_ascii=False)
    
    def _record_subagent_token_usage(self, token_usage: dict, agent_role: str | None):
        """记录 subagent 的 token 消耗到主代理的 token 追踪系统"""
        try:
            if self._manager and hasattr(self._manager, '_token_usage'):
                self._manager._token_usage.record_usage(
                    session_instance_id=self._session_instance_id,
                    provider_name="subagent",
                    model_id=agent_role or "default",
                    usage=token_usage,
                    request_type="subagent_sync",
                )
        except Exception as e:
            logger.debug(f"Failed to record subagent token usage: {e}")
    
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
        
        return f"[Async] Batch spawn initiated with {len(tasks)} subagents (group: {group.id}). These are long-running tasks - do NOT wait or sleep for them. You may continue with other parallelizable tasks. I'll initiate a new conversation when all complete and results are aggregated."
