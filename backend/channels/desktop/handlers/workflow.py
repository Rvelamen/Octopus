"""WebSocket message handlers for workflow operations.

Mirrors the REST API but over WebSocket for real-time updates.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.data import Database
from backend.services.workflow import (
    WorkflowStore,
    WorkflowRunStore,
    WorkflowEngine,
    WorkflowStatus,
)

# Sensitive patterns to sanitize from error messages
_SENSITIVE_PATTERNS = [
    r"/Users/[^\s]+",
    r"/home/[^\s]+",
    r"[a-zA-Z]:\\[^\s]+",
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    r"\b(?:sk|pk)_[a-zA-Z0-9]{20,}\b",
    r"\b[a-f0-9]{32,}\b",
]


def _sanitize_error(error: str) -> str:
    """Sanitize sensitive information from error messages."""
    import re

    sanitized = error
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized)
    return sanitized


class WorkflowHandler(MessageHandler):
    """Handle workflow-related WebSocket messages."""

    def __init__(self, bus):
        super().__init__(bus)
        self._db = Database()
        self._store = WorkflowStore(self._db)
        self._run_store = WorkflowRunStore(self._db)
        self._engine = WorkflowEngine(self._db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        handler_map = {
            "workflow_list": self._handle_list,
            "workflow_get": self._handle_get,
            "workflow_save": self._handle_save,
            "workflow_update": self._handle_update,
            "workflow_publish": self._handle_publish,
            "workflow_delete": self._handle_delete,
            "workflow_definition_get": self._handle_definition_get,
            "workflow_definition_save": self._handle_definition_save,
            "workflow_export": self._handle_export,
            "workflow_import": self._handle_import,
            "workflow_run": self._handle_run,
            "workflow_run_status": self._handle_run_status,
            "workflow_run_cancel": self._handle_run_cancel,
            "workflow_run_list": self._handle_run_list,
            "workflow_run_detail": self._handle_run_detail,
            "workflow_run_delete": self._handle_run_delete,
            "workflow_run_list_delete": self._handle_run_list_delete,
            "workflow_version_create": self._handle_version_create,
            "workflow_version_list": self._handle_version_list,
            "workflow_get_node_registry": self._handle_get_node_registry,
        }

        msg_type_str = message.type.value if hasattr(message.type, 'value') else str(message.type)
        handler = handler_map.get(msg_type_str)
        if handler:
            await handler(websocket, message)
        else:
            await self._send_error(websocket, message.request_id, f"Unknown workflow message type: {message.type}")

    async def _send_response(self, websocket: WebSocket, request_id: str, data: dict[str, Any]) -> None:
        await websocket.send_json({
            "type": "workflow_response",
            "request_id": request_id,
            "data": data,
        })

    async def _send_error(self, websocket: WebSocket, request_id: str, error: str) -> None:
        sanitized = _sanitize_error(error)
        await websocket.send_json({
            "type": "workflow_error",
            "request_id": request_id,
            "error": sanitized,
        })

    # ── Workflow CRUD ──

    async def _handle_list(self, websocket: WebSocket, message: WSMessage) -> None:
        category = message.data.get("category")
        status_str = message.data.get("status")
        status = WorkflowStatus(status_str) if status_str else None
        workflows = self._store.list_workflows(category=category, status=status)
        await self._send_response(websocket, message.request_id, {
            "workflows": [
                {
                    "id": w.id,
                    "name": w.name,
                    "description": w.description,
                    "category": w.category,
                    "status": w.status.value,
                    "current_version": w.current_version,
                    "created_at": w.created_at.isoformat() if w.created_at else None,
                    "updated_at": w.updated_at.isoformat() if w.updated_at else None,
                }
                for w in workflows
            ]
        })

    async def _handle_get(self, websocket: WebSocket, message: WSMessage) -> None:
        workflow_id = message.data.get("workflow_id")
        if not workflow_id:
            await self._send_error(websocket, message.request_id, "workflow_id required")
            return

        wf = self._store.get_workflow(workflow_id)
        if not wf:
            await self._send_error(websocket, message.request_id, "Workflow not found")
            return

        versions = self._store.list_versions(workflow_id)
        triggers = self._store.list_triggers(workflow_id)
        await self._send_response(websocket, message.request_id, {
            "id": wf.id,
            "name": wf.name,
            "description": wf.description,
            "category": wf.category,
            "status": wf.status.value,
            "current_version": wf.current_version,
            "versions": [
                {
                    "id": v.id,
                    "version": v.version,
                    "name": v.name,
                    "status": v.status.value,
                    "published_at": v.published_at.isoformat() if v.published_at else None,
                }
                for v in versions
            ],
            "triggers": [
                {
                    "id": t.id,
                    "type": t.trigger_type.value,
                    "enabled": t.enabled,
                }
                for t in triggers
            ],
        })

    async def _handle_update(self, websocket: WebSocket, message: WSMessage) -> None:
        workflow_id = message.data.get("workflow_id")
        if not workflow_id:
            await self._send_error(websocket, message.request_id, "workflow_id required")
            return

        updates = {k: v for k, v in message.data.items() if k in {"name", "description", "category", "status"}}
        if "status" in updates:
            updates["status"] = WorkflowStatus(updates["status"])
        wf = self._store.update_workflow(workflow_id, **updates)
        if not wf:
            await self._send_error(websocket, message.request_id, "Workflow not found")
            return
        await self._send_response(websocket, message.request_id, {
            "id": wf.id,
            "name": wf.name,
            "status": wf.status.value,
        })

    async def _handle_save(self, websocket: WebSocket, message: WSMessage) -> None:
        data = message.data
        workflow_id = data.get("workflow_id")
        name = data.get("name")
        description = data.get("description", "")
        category = data.get("category", "general")

        if workflow_id:
            wf = self._store.update_workflow(workflow_id, name=name, description=description, category=category)
            if not wf:
                await self._send_error(websocket, message.request_id, "Workflow not found")
                return
        else:
            wf = self._store.create_workflow(name=name, description=description, category=category)
            # Create initial version
            self._store.create_version(wf.id, 1, name, description)

        await self._send_response(websocket, message.request_id, {
            "id": wf.id,
            "name": wf.name,
            "status": wf.status.value,
        })

    async def _handle_publish(self, websocket: WebSocket, message: WSMessage) -> None:
        version_id = message.data.get("version_id")
        if not version_id:
            await self._send_error(websocket, message.request_id, "version_id required")
            return

        version = self._store.publish_version(version_id)
        if not version:
            await self._send_error(websocket, message.request_id, "Version not found")
            return

        await self._send_response(websocket, message.request_id, {
            "id": version.id,
            "status": version.status.value,
        })

    async def _handle_delete(self, websocket: WebSocket, message: WSMessage) -> None:
        workflow_id = message.data.get("workflow_id")
        if not workflow_id:
            await self._send_error(websocket, message.request_id, "workflow_id required")
            return

        if self._store.delete_workflow(workflow_id):
            await self._send_response(websocket, message.request_id, {"deleted": True})
        else:
            await self._send_error(websocket, message.request_id, "Workflow not found")

    # ── Definition ──

    async def _handle_definition_get(self, websocket: WebSocket, message: WSMessage) -> None:
        version_id = message.data.get("version_id")
        if not version_id:
            await self._send_error(websocket, message.request_id, "version_id required")
            return

        version = self._store.get_version(version_id)
        if not version:
            await self._send_error(websocket, message.request_id, "Version not found")
            return

        nodes = self._store.list_nodes(version_id)
        edges = self._store.list_edges(version_id)
        variables = self._store.list_variables(version_id)

        await self._send_response(websocket, message.request_id, {
            "version_id": version_id,
            "workflow_id": version.workflow_id,
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type.value if hasattr(n.type, 'value') else n.type,
                    "label": n.label,
                    "position": {"x": n.position_x, "y": n.position_y},
                    "width": n.width,
                    "height": n.height,
                    "config": n.config,
                    "timeout_seconds": n.timeout_seconds,
                    "max_retries": n.max_retries,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "id": e.id,
                    "source": e.source_node_id,
                    "target": e.target_node_id,
                    "label": e.label,
                    "condition": e.condition,
                    "sourceHandle": e.source_handle,
                    "targetHandle": e.target_handle,
                }
                for e in edges
            ],
            "variables": [
                {
                    "name": v.name,
                    "type": v.type.value if hasattr(v.type, 'value') else v.type,
                    "default_value": v.default_value,
                    "description": v.description,
                    "required": v.required,
                    "is_input": v.is_input,
                }
                for v in variables
            ],
        })

    async def _handle_definition_save(self, websocket: WebSocket, message: WSMessage) -> None:
        data = message.data
        version_id = data.get("version_id")
        nodes_data = data.get("nodes", [])
        edges_data = data.get("edges", [])
        variables_data = data.get("variables", [])

        if not version_id:
            await self._send_error(websocket, message.request_id, "version_id required")
            return

        version = self._store.get_version(version_id)
        if not version:
            await self._send_error(websocket, message.request_id, "Version not found")
            return

        if version.status.value != "draft":
            await self._send_error(websocket, message.request_id, "Can only edit draft versions")
            return

        result = self._store.save_definition(
            version_id=version_id,
            nodes_data=nodes_data,
            edges_data=edges_data,
            variables_data=variables_data,
        )

        await self._send_response(websocket, message.request_id, {
            "saved": True,
            **result,
        })

    async def _handle_export(self, websocket: WebSocket, message: WSMessage) -> None:
        """Export a workflow as JSON for backup or migration."""
        workflow_id = message.data.get("workflow_id")
        if not workflow_id:
            await self._send_error(websocket, message.request_id, "workflow_id required")
            return

        wf = self._store.get_workflow(workflow_id)
        if not wf:
            await self._send_error(websocket, message.request_id, "Workflow not found")
            return

        versions = self._store.list_versions(workflow_id)
        triggers = self._store.list_triggers(workflow_id)

        export_data = {
            "format_version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "workflow": {
                "name": wf.name,
                "description": wf.description,
                "category": wf.category,
                "status": wf.status.value,
            },
            "versions": [],
            "triggers": [
                {
                    "type": t.trigger_type.value,
                    "config": t.config,
                    "enabled": t.enabled,
                }
                for t in triggers
            ],
        }

        for version in versions:
            nodes = self._store.list_nodes(version.id)
            edges = self._store.list_edges(version.id)
            variables = self._store.list_variables(version.id)

            export_data["versions"].append({
                "version": version.version,
                "name": version.name,
                "description": version.description,
                "status": version.status.value,
                "nodes": [
                    {
                        "id": n.id,
                        "type": n.type.value if hasattr(n.type, 'value') else n.type,
                        "label": n.label,
                        "position": {"x": n.position_x, "y": n.position_y},
                        "width": n.width,
                        "height": n.height,
                        "config": n.config,
                        "timeout_seconds": n.timeout_seconds,
                        "max_retries": n.max_retries,
                    }
                    for n in nodes
                ],
                "edges": [
                    {
                        "id": e.id,
                        "source": e.source_node_id,
                        "target": e.target_node_id,
                        "label": e.label,
                        "condition": e.condition,
                    }
                    for e in edges
                ],
                "variables": [
                    {
                        "name": v.name,
                        "type": v.type.value if hasattr(v.type, 'value') else v.type,
                        "default_value": v.default_value,
                        "description": v.description,
                        "required": v.required,
                        "is_input": v.is_input,
                    }
                    for v in variables
                ],
            })

        await self._send_response(websocket, message.request_id, {
            "exported": True,
            "data": export_data,
        })

    async def _handle_import(self, websocket: WebSocket, message: WSMessage) -> None:
        """Import a workflow from JSON export data."""
        import_data = message.data.get("data")
        if not import_data:
            await self._send_error(websocket, message.request_id, "Import data required")
            return

        try:
            wf_data = import_data.get("workflow", {})
            name = wf_data.get("name", "Imported Workflow")
            description = wf_data.get("description", "")
            category = wf_data.get("category", "general")

            # Create workflow
            wf = self._store.create_workflow(name=name, description=description, category=category)

            # Import versions
            versions_data = import_data.get("versions", [])
            for idx, v_data in enumerate(versions_data):
                version = self._store.create_version(
                    workflow_id=wf.id,
                    version=v_data.get("version", idx + 1),
                    name=v_data.get("name", f"Version {idx + 1}"),
                    description=v_data.get("description", ""),
                )

                # Save definition
                self._store.save_definition(
                    version_id=version.id,
                    nodes_data=v_data.get("nodes", []),
                    edges_data=v_data.get("edges", []),
                    variables_data=v_data.get("variables", []),
                )

                # Restore status if published
                if v_data.get("status") == "published":
                    self._store.publish_version(version.id)

            # Import triggers
            for t_data in import_data.get("triggers", []):
                from backend.services.workflow.models import TriggerType
                trigger_type = TriggerType(t_data.get("type", "manual"))
                self._store.create_trigger(
                    workflow_id=wf.id,
                    trigger_type=trigger_type,
                    config=t_data.get("config", {}),
                    enabled=t_data.get("enabled", True),
                )

            await self._send_response(websocket, message.request_id, {
                "imported": True,
                "workflow_id": wf.id,
                "name": wf.name,
            })

        except Exception as e:
            logger.error(f"Workflow import failed: {e}")
            await self._send_error(websocket, message.request_id, f"Import failed: {str(e)}")

    # ── Run Management ──

    async def _handle_run(self, websocket: WebSocket, message: WSMessage) -> None:
        data = message.data
        workflow_id = data.get("workflow_id")
        version_id = data.get("version_id")
        input_variables = data.get("input_variables", {})
        test_mode = data.get("test_mode", False)

        if not workflow_id:
            await self._send_error(websocket, message.request_id, "workflow_id required")
            return

        async def on_node_update(run_id: str, node_id: str | None, status: str, data: dict):
            await websocket.send_json({
                "type": "workflow_node_update",
                "data": {
                    "run_id": run_id,
                    "node_id": node_id,
                    "status": status,
                    "output": data,
                },
            })

        try:
            run = await self._engine.execute(
                workflow_id=workflow_id,
                version_id=version_id,
                input_variables=input_variables,
                trigger_type="manual",
                on_node_update=on_node_update,
                test_mode=test_mode,
            )
            await self._send_response(websocket, message.request_id, {
                "run_id": run.id,
                "status": run.status,
            })
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_run_status(self, websocket: WebSocket, message: WSMessage) -> None:
        run_id = message.data.get("run_id")
        if not run_id:
            await self._send_error(websocket, message.request_id, "run_id required")
            return

        status = self._engine.get_run_status(run_id)
        if not status:
            await self._send_error(websocket, message.request_id, "Run not found")
            return

        await self._send_response(websocket, message.request_id, status)

    async def _handle_run_cancel(self, websocket: WebSocket, message: WSMessage) -> None:
        run_id = message.data.get("run_id")
        if not run_id:
            await self._send_error(websocket, message.request_id, "run_id required")
            return

        if self._engine.cancel_run(run_id):
            await self._send_response(websocket, message.request_id, {"cancelled": True})
        else:
            await self._send_error(websocket, message.request_id, "Run not found or cannot be cancelled")

    async def _handle_run_delete(self, websocket: WebSocket, message: WSMessage) -> None:
        run_id = message.data.get("run_id")
        if not run_id:
            await self._send_error(websocket, message.request_id, "run_id required")
            return

        if self._store.delete_run(run_id):
            await self._send_response(websocket, message.request_id, {"deleted": True})
        else:
            await self._send_error(websocket, message.request_id, "Run not found")

    async def _handle_run_list_delete(self, websocket: WebSocket, message: WSMessage) -> None:
        workflow_id = message.data.get("workflow_id")
        if not workflow_id:
            await self._send_error(websocket, message.request_id, "workflow_id required")
            return

        count = self._store.delete_workflow_runs(workflow_id)
        await self._send_response(websocket, message.request_id, {"deleted": count})

    async def _handle_run_list(self, websocket: WebSocket, message: WSMessage) -> None:
        workflow_id = message.data.get("workflow_id")
        status = message.data.get("status")
        limit = message.data.get("limit", 50)
        offset = message.data.get("offset", 0)

        runs = self._run_store.list_runs(
            workflow_id=workflow_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        def _parse_json_field(field):
            if field is None:
                return {}
            if isinstance(field, str):
                try:
                    return json.loads(field)
                except json.JSONDecodeError:
                    return {}
            return field

        await self._send_response(websocket, message.request_id, {
            "runs": [
                {
                    "id": r.id,
                    "version_id": r.version_id,
                    "status": r.status,
                    "trigger_type": r.trigger_type,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "error_message": r.error_message,
                    "input_variables": _parse_json_field(r.input_variables),
                    "output_result": _parse_json_field(r.output_result),
                }
                for r in runs
            ]
        })

    async def _handle_run_detail(self, websocket: WebSocket, message: WSMessage) -> None:
        run_id = message.data.get("run_id")
        if not run_id:
            await self._send_error(websocket, message.request_id, "run_id required")
            return

        status = self._engine.get_run_status(run_id)
        if not status:
            await self._send_error(websocket, message.request_id, "Run not found")
            return

        await self._send_response(websocket, message.request_id, status)

    async def _handle_version_create(self, websocket: WebSocket, message: WSMessage) -> None:
        workflow_id = message.data.get("workflow_id")
        version = message.data.get("version")
        name = message.data.get("name", "")
        description = message.data.get("description", "")

        if not workflow_id:
            await self._send_error(websocket, message.request_id, "workflow_id required")
            return

        try:
            version_record = self._store.create_version(workflow_id, version, name, description)
            await self._send_response(websocket, message.request_id, {
                "id": version_record.id,
                "version": version_record.version,
                "name": version_record.name,
                "status": version_record.status.value,
            })
        except Exception as e:
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_version_list(self, websocket: WebSocket, message: WSMessage) -> None:
        workflow_id = message.data.get("workflow_id")
        if not workflow_id:
            await self._send_error(websocket, message.request_id, "workflow_id required")
            return

        versions = self._store.list_versions(workflow_id)
        await self._send_response(websocket, message.request_id, {
            "versions": [
                {
                    "id": v.id,
                    "version": v.version,
                    "name": v.name,
                    "description": v.description,
                    "status": v.status.value,
                    "published_at": v.published_at.isoformat() if v.published_at else None,
                }
                for v in versions
            ]
        })

    async def _handle_get_node_registry(self, websocket: WebSocket, message: WSMessage) -> None:
        from backend.services.workflow.node_registry import get_node_types_dict
        registry = get_node_types_dict()
        await self._send_response(websocket, message.request_id, {
            "nodes": registry,
        })
