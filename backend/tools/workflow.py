"""Workflow execution tools for the main agent.

Allows the main agent to list available workflows and execute them
without doing any workflow design or node editing.
"""

from __future__ import annotations

import json
from typing import Any

from backend.data.database import Database
from backend.services.workflow.engine.engine import WorkflowEngine
from backend.services.workflow.store import WorkflowStore
from backend.tools.base import Tool


def _check_type(value: Any, expected_type: str) -> bool:
    """Check if a value matches the expected workflow variable type.

    Performs loose type checking suitable for LLM-provided values.
    """
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type in ("arrayString", "arrayNumber", "arrayBoolean", "arrayObject"):
        return isinstance(value, list)
    if expected_type in ("chatHistory", "datasetQuote"):
        return isinstance(value, (list, dict))
    # Unknown types: be permissive
    return True


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
            "Returns workflow IDs, names, descriptions, and input variable definitions. "
            "When presenting the result to the user, ALWAYS show the input_variables for each workflow "
            "so the user knows what parameters are needed. "
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
        result = []
        for w in workflows:
            versions = store.list_versions(w.id)
            published = [v for v in versions if v.status.value == "published"]
            published_version = published[0] if published else None

            # 获取 published 版本的输入变量定义，让 Agent 知道需要什么参数
            input_variables = []
            if published_version:
                vars = store.list_variables(published_version.id)
                for v in vars:
                    if v.is_input:
                        input_variables.append(
                            {
                                "name": v.name,
                                "type": v.type.value if hasattr(v.type, "value") else str(v.type),
                                "description": v.description or "",
                                "required": v.required,
                                "default_value": v.default_value,
                            }
                        )

            # 构建运行提示
            run_hint = ""
            if published_version and input_variables:
                required_vars = [v for v in input_variables if v.get("required")]
                optional_vars = [v for v in input_variables if not v.get("required")]
                parts = []
                if required_vars:
                    parts.append(f"Required: {', '.join(v['name'] for v in required_vars)}")
                if optional_vars:
                    parts.append(f"Optional: {', '.join(v['name'] for v in optional_vars)}")
                run_hint = " | ".join(parts)

            result.append(
                {
                    "id": w.id,
                    "name": w.name,
                    "description": w.description or "",
                    "category": w.category or "general",
                    "status": w.status.value if hasattr(w.status, "value") else str(w.status),
                    "has_published_version": published_version is not None,
                    "published_version": (
                        {
                            "id": published_version.id,
                            "version": published_version.version,
                            "published_at": (
                                published_version.published_at.isoformat()
                                if published_version.published_at
                                else None
                            ),
                        }
                        if published_version
                        else None
                    ),
                    "input_variables": input_variables,
                    "run_hint": run_hint,
                }
            )
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
            "Execute a workflow that the user has already built and published. "
            "You MUST map the user's intent and any values they provide into the input_variables dict. "
            "For example, if the user says 'run my search workflow for AI', and the workflow has an input variable named 'query', "
            "you should call this tool with input_variables={'query': 'AI'}. "
            "If you are unsure what input variables the workflow expects, call workflow_list first to check its input_variables. "
            "If version_id is omitted, the currently published version is used automatically. "
            "Only published versions are executed by default; to run a specific draft version, provide its version_id. "
            "If required variables are missing, the call will fail with a list of what's needed. "
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
                    "description": "Input variables to pass to the workflow. If the user mentions any values that correspond to the workflow's input variables, you MUST include them here. For example, if the workflow expects 'query' and the user says 'search for AI', pass {'query': 'AI'}. If you are unsure what variables are needed, call workflow_list first.",
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
                    {
                        "error": f"Workflow '{workflow_name}' not found. Call workflow_list to see available workflows."
                    },
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

        # Resolve version_id if not provided (same logic as engine)
        resolved_version_id = version_id
        if not resolved_version_id:
            versions = store.list_versions(target_id)
            published = [v for v in versions if v.status.value == "published"]
            if published:
                resolved_version_id = published[0].id
            else:
                return json.dumps(
                    {
                        "error": "No published version found for this workflow. Please publish a version first."
                    },
                    ensure_ascii=False,
                )

        # Validate input variables before execution
        variables = store.list_variables(resolved_version_id)
        input_vars = input_variables or {}
        input_var_defs = [v for v in variables if v.is_input]

        # 1. Check for missing required variables
        required_missing = [v for v in input_var_defs if v.required and v.name not in input_vars]

        # 2. Check for type mismatches in provided variables
        type_errors = []
        for v in input_var_defs:
            if v.name in input_vars:
                value = input_vars[v.name]
                var_type = v.type.value if hasattr(v.type, "value") else str(v.type)
                if not _check_type(value, var_type):
                    type_errors.append(
                        {
                            "name": v.name,
                            "expected_type": var_type,
                            "actual_type": type(value).__name__,
                            "value_preview": str(value)[:50],
                        }
                    )

        if required_missing or type_errors:
            all_vars = [
                {
                    "name": v.name,
                    "type": v.type.value if hasattr(v.type, "value") else str(v.type),
                    "description": v.description or "",
                    "required": v.required,
                    "default_value": v.default_value,
                }
                for v in input_var_defs
            ]
            return json.dumps(
                {
                    "error": "Input validation failed.",
                    "details": {
                        "missing_required": [v.name for v in required_missing],
                        "type_errors": type_errors,
                    },
                    "all_input_variables": all_vars,
                    "hint": "Fix the issues above and retry. Example: input_variables={'query': 'AI'}",
                },
                ensure_ascii=False,
                default=str,
            )

        engine = WorkflowEngine(self._db)
        try:
            run = await engine.execute(
                workflow_id=target_id,
                version_id=resolved_version_id,
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
