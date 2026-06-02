"""Workflow execution tools for the main agent.

Allows the main agent to list available workflows and execute them
without doing any workflow design or node editing.
"""

from __future__ import annotations

import json
from typing import Any

from backend.tools.base import Tool
from backend.services.workflow.store import WorkflowStore
from backend.services.workflow.engine.engine import WorkflowEngine
from backend.data.database import Database


class WorkflowListTool(Tool):
    """List available workflows that can be executed."""

    def __init__(self, db: Database | None = None):
        self._db = db or Database()

    @property
    def name(self) -> str:
        return "workflow_list"

    @property
    def description(self) -> str:
        return (
            "List all available workflows that the user has created. "
            "Returns workflow IDs, names, descriptions, and categories. "
            "Use this when the user asks to run a workflow but you don't know the exact ID, "
            "or when you need to show the user what workflows are available."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        store = WorkflowStore(self._db)
        workflows = store.list_workflows()
        result = [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description or "",
                "category": w.category or "general",
                "status": w.status.value if hasattr(w.status, "value") else str(w.status),
            }
            for w in workflows
        ]
        return json.dumps(
            {"workflows": result, "count": len(result)},
            ensure_ascii=False,
            default=str,
        )


class WorkflowRunTool(Tool):
    """Execute a workflow by its ID or name."""

    def __init__(self, db: Database | None = None):
        self._db = db or Database()

    @property
    def name(self) -> str:
        return "workflow_run"

    @property
    def description(self) -> str:
        return (
            "Execute a workflow that the user has already built. "
            "Provide the workflow_id (or workflow_name as a fallback), and optional input variables. "
            "The workflow will run to completion and return the final output. "
            "Use this when the user asks you to run, trigger, or execute a specific workflow."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "The workflow ID to execute. If unsure, call workflow_list first.",
                },
                "workflow_name": {
                    "type": "string",
                    "description": "Optional: the workflow name. Used as fallback if workflow_id is not provided.",
                },
                "input_variables": {
                    "type": "object",
                    "description": "Optional input variables to pass to the workflow (e.g. {'userInput': 'hello'}).",
                    "default": {},
                },
                "version_id": {
                    "type": "string",
                    "description": "Optional specific version ID. If omitted, the latest published version (or latest draft) is used.",
                },
            },
            "required": [],
        }

    async def execute(
        self,
        workflow_id: str = "",
        workflow_name: str = "",
        input_variables: dict | None = None,
        version_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        store = WorkflowStore(self._db)

        # Resolve workflow_id from name if needed
        target_id = workflow_id
        if not target_id and workflow_name:
            workflows = store.list_workflows()
            for w in workflows:
                if w.name == workflow_name:
                    target_id = w.id
                    break
            if not target_id:
                return json.dumps(
                    {"error": f"Workflow '{workflow_name}' not found. Call workflow_list to see available workflows."},
                    ensure_ascii=False,
                )

        if not target_id:
            return json.dumps(
                {"error": "workflow_id or workflow_name is required"},
                ensure_ascii=False,
            )

        # Validate workflow exists
        wf = store.get_workflow(target_id)
        if not wf:
            return json.dumps(
                {"error": f"Workflow '{target_id}' not found"},
                ensure_ascii=False,
            )

        engine = WorkflowEngine(self._db)
        try:
            run = await engine.execute(
                workflow_id=target_id,
                version_id=version_id or None,
                input_variables=input_variables or {},
                trigger_type="agent",
            )
        except Exception as e:
            return json.dumps(
                {"error": str(e), "workflow_id": target_id},
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "run_id": run.id,
                "workflow_id": target_id,
                "workflow_name": wf.name,
                "status": run.status,
                "output": run.output_result,
                "error": getattr(run, "error_message", None),
            },
            ensure_ascii=False,
            default=str,
        )
