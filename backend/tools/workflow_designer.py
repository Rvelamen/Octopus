"""Workflow designer tools for AI-assisted workflow authoring.

These tools allow an AI agent to programmatically create, modify, and test
workflows by interacting with the WorkflowStore and WorkflowEngine.
"""

import contextlib
import json
import uuid
from typing import Any

from loguru import logger

from backend.data.database import Database
from backend.services.workflow.auto_binding import (
    _extract_inputs,
    _extract_outputs,
    auto_bind_variables,
)
from backend.services.workflow.engine.engine import WorkflowEngine
from backend.services.workflow.node_registry import NodeRegistry
from backend.services.workflow.store import WorkflowStore
from backend.tools.base import Tool


class _WorkflowToolBase(Tool):
    """Base class for workflow designer tools with shared store/engine access.

    The workflow_id is set automatically by the agent before each tool execution,
    so the AI does not need to pass it as a parameter.
    """

    def __init__(self, db: Database | None = None):
        self.db = db or Database()
        self.store = WorkflowStore(self.db)
        self.engine = WorkflowEngine(self.db)
        self.registry = NodeRegistry()
        self._workflow_id: str | None = None

    def set_workflow_id(self, workflow_id: str) -> None:
        """Set the current workflow ID (called by the agent before execution)."""
        self._workflow_id = workflow_id

    @property
    def _current_workflow_id(self) -> str:
        if not self._workflow_id:
            raise RuntimeError(
                "workflow_id not set — agent must call set_workflow_id() before executing tools"
            )
        return self._workflow_id

    def _get_or_create_version_id(self, workflow_id: str) -> str:
        """Get the latest version ID, or create a draft version if none exists."""
        version = self.store.get_latest_version(workflow_id)
        if version:
            return version.id
        # Create a new draft version
        workflow = self.store.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        new_version = self.store.create_version(
            workflow_id=workflow_id,
            version=1,
            name="Draft",
            description="Auto-created by AI designer",
        )
        return new_version.id

    def _load_canvas(self, workflow_id: str) -> tuple[list[dict], list[dict]]:
        """Load current nodes and edges for a workflow."""
        version_id = self._get_or_create_version_id(workflow_id)
        nodes = self.store.list_nodes(version_id)
        edges = self.store.list_edges(version_id)
        return (
            [
                {
                    "id": n.id,
                    "type": n.type.value if hasattr(n.type, "value") else n.type,
                    "label": n.label,
                    "position_x": n.position_x,
                    "position_y": n.position_y,
                    "width": n.width,
                    "height": n.height,
                    "config": n.config,
                    "parent_id": n.parent_id,
                }
                for n in nodes
            ],
            [
                {
                    "id": e.id,
                    "source": e.source_node_id,
                    "target": e.target_node_id,
                    "source_handle": e.source_handle,
                    "target_handle": e.target_handle,
                    "condition": e.condition,
                }
                for e in edges
            ],
        )

    def _save_canvas(self, workflow_id: str, nodes: list[dict], edges: list[dict]) -> None:
        """Save nodes and edges back to the store."""
        from enum import Enum

        version_id = self._get_or_create_version_id(workflow_id)

        # Convert to store format
        store_nodes = []
        for n in nodes:
            config = dict(n.get("config", {}))
            # Ensure type is a string (NodeType enum may come from _load_canvas)
            node_type = n.get("type", "emptyNode")
            if isinstance(node_type, Enum):
                node_type = node_type.value
            store_nodes.append(
                {
                    "id": n["id"],
                    "type": node_type,
                    "label": n.get("label", node_type),
                    "position_x": n.get("position_x", 0),
                    "position_y": n.get("position_y", 0),
                    "width": n.get("width", 200),
                    "height": n.get("height", 80),
                    "config": config,
                    "parent_id": n.get("parent_id"),
                }
            )

        store_edges = []
        for e in edges:
            store_edges.append(
                {
                    "id": e["id"],
                    "source": e["source"],
                    "target": e["target"],
                    "sourceHandle": e.get("source_handle", ""),
                    "targetHandle": e.get("target_handle", ""),
                    "condition": e.get("condition", ""),
                }
            )

        self.store.save_nodes(version_id, store_nodes)
        self.store.save_edges(version_id, store_edges)


# Aliases for intuitive node type names → registry names
_NODE_TYPE_ALIASES = {
    "llm": "chatNode",
    "http": "httpRequest468",
}


class WorkflowAddNodeTool(_WorkflowToolBase):
    """Add a new node to the workflow canvas."""

    @property
    def name(self) -> str:
        return "add_node"

    @property
    def description(self) -> str:
        return (
            "Add a new node to the workflow. Returns the created node with its ID, "
            "position, and auto-bound variables. Common node types: workflowStart, chatNode(llm), "
            "workflowEnd, httpRequest468(http), database, ifElseNode, code, textEditor, classifyQuestion, contentExtract. "
            "For database node config: tableName (string), operation ('QUERY'/'INSERT'/'UPDATE'/'DELETE'), "
            "fieldMappings (array of {name, value}), whereCondition (string), orderBy (string)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_type": {
                    "type": "string",
                    "description": "Type of node to add (e.g. 'chatNode' for LLM, 'httpRequest468' for HTTP, 'ifElseNode')",
                },
                "name": {
                    "type": "string",
                    "description": "Display name for the node (in Chinese preferred)",
                },
                "position": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                    "description": "Optional position. If omitted, auto-layout will be applied.",
                },
                "config": {
                    "type": "object",
                    "description": "Optional node-specific configuration (e.g. systemPrompt for chatNode, system_httpReqUrl for httpRequest468)",
                },
            },
            "required": ["node_type", "name"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        node_type = kwargs["node_type"]
        name = kwargs["name"]
        position = kwargs.get("position", {})
        config = kwargs.get("config", {})

        # Resolve aliases (e.g. 'llm' → 'chatNode')
        node_type = _NODE_TYPE_ALIASES.get(node_type, node_type)

        nodes, edges = self._load_canvas(workflow_id)

        # Generate a unique ID using UUID4 to avoid all collision scenarios
        node_id = f"{node_type}-{uuid.uuid4().hex[:8]}"
        existing_ids = {n["id"] for n in nodes}
        while node_id in existing_ids:
            node_id = f"{node_type}-{uuid.uuid4().hex[:8]}"

        # Build node config with defaults
        node_info = self.registry.get(node_type)
        node_config: dict[str, Any] = dict(config)
        node_config.setdefault("name", name)
        node_config.setdefault("intro", node_info.description if node_info else "")

        # Default inputs based on node type
        default_inputs = _extract_inputs({"type": node_type, "config": node_config})
        if default_inputs and node_type != "workflowEnd":
            node_config["inputs"] = [
                {"key": i["key"], "name": i["key"], "type": i["type"], "value": i.get("value", "")}
                for i in default_inputs
            ]

        # Default outputs
        default_outputs = _extract_outputs({"type": node_type, "config": node_config})
        if default_outputs:
            node_config["outputs"] = [
                {
                    "key": o["key"],
                    "name": o["key"],
                    "type": o["type"],
                    "label": o.get("label", o["key"]),
                }
                for o in default_outputs
            ]

        new_node = {
            "id": node_id,
            "type": node_type,
            "label": name,
            "position_x": position.get("x", 100 + len(nodes) * 250),
            "position_y": position.get("y", 200),
            "width": 200,
            "height": 80,
            "config": node_config,
        }

        # Auto-bind variables
        bindings = auto_bind_variables(new_node, nodes, edges)
        if bindings:
            if node_type == "workflowEnd" and "outputs" in node_config:
                for input_key, bound_value, _confidence in bindings:
                    for out in node_config["outputs"]:
                        if out["key"] == input_key:
                            out["value"] = bound_value
                            break
            elif "inputs" in node_config:
                for input_key, bound_value, _confidence in bindings:
                    for inp in node_config["inputs"]:
                        if inp["key"] == input_key:
                            inp["value"] = bound_value
                            break

        nodes.append(new_node)
        self._save_canvas(workflow_id, nodes, edges)

        result = {
            "node_id": node_id,
            "type": node_type,
            "name": name,
            "position": {"x": new_node["position_x"], "y": new_node["position_y"]},
            "auto_bindings": [{"input": k, "value": v, "confidence": c} for k, v, c in bindings],
        }
        return json.dumps(result, ensure_ascii=False)


class WorkflowConnectNodesTool(_WorkflowToolBase):
    """Connect two nodes with an edge."""

    @property
    def name(self) -> str:
        return "connect_nodes"

    @property
    def description(self) -> str:
        return "Create a directed edge from source node to target node. For ifElseNode, specify branch condition."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source node ID"},
                "target": {"type": "string", "description": "Target node ID"},
                "source_handle": {
                    "type": "string",
                    "description": "Optional source handle (for branch outputs)",
                },
                "target_handle": {
                    "type": "string",
                    "description": "Optional target handle (for specific inputs)",
                },
                "condition": {
                    "type": "string",
                    "description": "Optional condition label for the edge",
                },
            },
            "required": ["source", "target"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        source = kwargs["source"]
        target = kwargs["target"]
        source_handle = kwargs.get("source_handle", "")
        target_handle = kwargs.get("target_handle", "")
        condition = kwargs.get("condition", "")

        nodes, edges = self._load_canvas(workflow_id)

        # Validate nodes exist
        source_node = next((n for n in nodes if n["id"] == source), None)
        target_node = next((n for n in nodes if n["id"] == target), None)
        if not source_node:
            return json.dumps({"error": f"Source node '{source}' not found"}, ensure_ascii=False)
        if not target_node:
            return json.dumps({"error": f"Target node '{target}' not found"}, ensure_ascii=False)

        # Check for duplicate edge
        existing = next(
            (e for e in edges if e["source"] == source and e["target"] == target),
            None,
        )
        if existing:
            return json.dumps(
                {"error": f"Edge from {source} to {target} already exists"}, ensure_ascii=False
            )

        edge_id = f"e-{uuid.uuid4().hex[:8]}"
        new_edge = {
            "id": edge_id,
            "source": source,
            "target": target,
            "source_handle": source_handle or f"{source}-source",
            "target_handle": target_handle or f"{target}-target",
            "condition": condition,
        }
        edges.append(new_edge)
        self._save_canvas(workflow_id, nodes, edges)

        return json.dumps(
            {
                "edge_id": edge_id,
                "source": source,
                "target": target,
                "success": True,
            },
            ensure_ascii=False,
        )


class WorkflowSetVariableTool(_WorkflowToolBase):
    """Set a variable binding on a node's input."""

    @property
    def name(self) -> str:
        return "set_variable"

    @property
    def description(self) -> str:
        return "Bind an input variable of a node to an upstream output using {{nodeId.outputKey}} syntax."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Target node ID"},
                "input_key": {
                    "type": "string",
                    "description": "Input key to bind (e.g. 'input', 'result')",
                },
                "value": {
                    "type": "string",
                    "description": "Value or reference, e.g. '{{start-1.userChatInput}}' or '{{?}}' for placeholder",
                },
            },
            "required": ["node_id", "input_key", "value"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        node_id = kwargs["node_id"]
        input_key = kwargs["input_key"]
        value = kwargs["value"]

        nodes, edges = self._load_canvas(workflow_id)

        node = next((n for n in nodes if n["id"] == node_id), None)
        if not node:
            return json.dumps({"error": f"Node '{node_id}' not found"}, ensure_ascii=False)

        config = node.get("config", {})
        if not isinstance(config, dict):
            return json.dumps({"error": f"Node '{node_id}' has invalid config"}, ensure_ascii=False)

        node_type = node.get("type", "")

        # workflowEnd stores variable bindings in outputs, not inputs
        if node_type == "workflowEnd":
            outputs_list = config.get("outputs", [])
            if not isinstance(outputs_list, list):
                outputs_list = []
            config["outputs"] = outputs_list

            if not outputs_list:
                outputs_list = [
                    {"key": input_key, "name": input_key, "type": "string", "value": value}
                ]
            else:
                found = False
                for out in outputs_list:
                    if out.get("key") == input_key or out.get("name") == input_key:
                        out["value"] = value
                        found = True
                        break
                if not found:
                    outputs_list.append(
                        {"key": input_key, "name": input_key, "type": "string", "value": value}
                    )
        else:
            inputs_list = config.get("inputs", [])
            if not isinstance(inputs_list, list):
                inputs_list = []
            config["inputs"] = inputs_list

            if not inputs_list:
                inputs_list = [
                    {"key": input_key, "name": input_key, "type": "string", "value": value}
                ]
            else:
                found = False
                for inp in inputs_list:
                    if inp.get("key") == input_key or inp.get("name") == input_key:
                        inp["value"] = value
                        found = True
                        break
                if not found:
                    inputs_list.append(
                        {"key": input_key, "name": input_key, "type": "string", "value": value}
                    )

        self._save_canvas(workflow_id, nodes, edges)

        return json.dumps(
            {
                "node_id": node_id,
                "input_key": input_key,
                "value": value,
                "success": True,
            },
            ensure_ascii=False,
        )


class WorkflowAddInputTool(_WorkflowToolBase):
    """Add a new input variable to a node's config.inputs list."""

    @property
    def name(self) -> str:
        return "add_input_variable"

    @property
    def description(self) -> str:
        return (
            "Add a new input variable to a node. "
            "Use this when you need to create a new input slot that doesn't already exist. "
            "For binding an existing input to an upstream output, use set_variable instead."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Target node ID"},
                "key": {
                    "type": "string",
                    "description": "Input variable key/name, e.g. 'userQuery', 'context'",
                },
                "type": {
                    "type": "string",
                    "description": "Variable data type",
                    "enum": [
                        "string",
                        "number",
                        "integer",
                        "boolean",
                        "object",
                        "array",
                        "arrayString",
                        "arrayNumber",
                        "arrayObject",
                        "file",
                        "any",
                    ],
                    "default": "string",
                },
                "label": {
                    "type": "string",
                    "description": "Human-readable display label. Defaults to key.",
                    "default": "",
                },
                "required": {
                    "type": "boolean",
                    "description": "Whether this input is required",
                    "default": False,
                },
                "value": {
                    "type": "string",
                    "description": "Initial binding value, e.g. '{{upstreamId.outputKey}}' or '{{?}}' for placeholder. Leave empty for manual entry.",
                    "default": "",
                },
            },
            "required": ["node_id", "key"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        node_id = kwargs["node_id"]
        key = kwargs["key"]
        var_type = kwargs.get("type", "string")
        label = kwargs.get("label", key)
        required = kwargs.get("required", False)
        value = kwargs.get("value", "")

        nodes, edges = self._load_canvas(workflow_id)
        node = next((n for n in nodes if n["id"] == node_id), None)
        if not node:
            return json.dumps({"error": f"Node '{node_id}' not found"}, ensure_ascii=False)

        config = node.get("config", {})
        if not isinstance(config, dict):
            config = {}
            node["config"] = config

        inputs_list = config.get("inputs", [])
        if not isinstance(inputs_list, list):
            inputs_list = []
        config["inputs"] = inputs_list

        # Check for duplicate (by key or name)
        for inp in inputs_list:
            if inp.get("key") == key or inp.get("name") == key:
                return json.dumps(
                    {"error": f"Input '{key}' already exists on node '{node_id}'"},
                    ensure_ascii=False,
                )

        new_input: dict[str, Any] = {
            "key": key,
            "name": key,
            "type": var_type,
            "label": label,
            "required": required,
        }
        if value:
            new_input["value"] = value

        inputs_list.append(new_input)
        self._save_canvas(workflow_id, nodes, edges)

        return json.dumps(
            {"node_id": node_id, "input": new_input, "success": True},
            ensure_ascii=False,
        )


class WorkflowAddOutputTool(_WorkflowToolBase):
    """Add a new output variable to a node's config.outputs list."""

    @property
    def name(self) -> str:
        return "add_output_variable"

    @property
    def description(self) -> str:
        return (
            "Add a new output variable to a node. "
            "Useful for workflowEnd nodes (to define what the workflow returns) "
            "or custom nodes that need additional outputs."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Target node ID"},
                "key": {
                    "type": "string",
                    "description": "Output variable key/name, e.g. 'result', 'summary'",
                },
                "type": {
                    "type": "string",
                    "description": "Variable data type",
                    "enum": [
                        "string",
                        "number",
                        "integer",
                        "boolean",
                        "object",
                        "array",
                        "arrayString",
                        "arrayNumber",
                        "arrayObject",
                        "file",
                        "any",
                    ],
                    "default": "string",
                },
                "label": {
                    "type": "string",
                    "description": "Human-readable display label. Defaults to key.",
                    "default": "",
                },
            },
            "required": ["node_id", "key"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        node_id = kwargs["node_id"]
        key = kwargs["key"]
        var_type = kwargs.get("type", "string")
        label = kwargs.get("label", key)

        nodes, edges = self._load_canvas(workflow_id)
        node = next((n for n in nodes if n["id"] == node_id), None)
        if not node:
            return json.dumps({"error": f"Node '{node_id}' not found"}, ensure_ascii=False)

        config = node.get("config", {})
        if not isinstance(config, dict):
            config = {}
            node["config"] = config

        outputs_list = config.get("outputs", [])
        if not isinstance(outputs_list, list):
            outputs_list = []
        config["outputs"] = outputs_list

        # Check for duplicate (by key or name)
        for out in outputs_list:
            if out.get("key") == key or out.get("name") == key:
                return json.dumps(
                    {"error": f"Output '{key}' already exists on node '{node_id}'"},
                    ensure_ascii=False,
                )

        new_output = {
            "key": key,
            "name": key,
            "type": var_type,
            "label": label,
        }
        outputs_list.append(new_output)
        self._save_canvas(workflow_id, nodes, edges)

        return json.dumps(
            {"node_id": node_id, "output": new_output, "success": True},
            ensure_ascii=False,
        )


class WorkflowRemoveVariableTool(_WorkflowToolBase):
    """Remove an input or output variable from a node."""

    @property
    def name(self) -> str:
        return "remove_variable"

    @property
    def description(self) -> str:
        return "Remove an input or output variable from a node by its key."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Target node ID"},
                "variable_key": {"type": "string", "description": "Variable key to remove"},
                "variable_type": {
                    "type": "string",
                    "enum": ["input", "output"],
                    "description": "Whether to remove from inputs or outputs",
                },
            },
            "required": ["node_id", "variable_key", "variable_type"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        node_id = kwargs["node_id"]
        var_key = kwargs["variable_key"]
        var_type = kwargs["variable_type"]

        nodes, edges = self._load_canvas(workflow_id)
        node = next((n for n in nodes if n["id"] == node_id), None)
        if not node:
            return json.dumps({"error": f"Node '{node_id}' not found"}, ensure_ascii=False)

        config = node.get("config", {})
        if not isinstance(config, dict):
            return json.dumps({"error": f"Node '{node_id}' has no config"}, ensure_ascii=False)

        if var_type == "input":
            inputs_list = config.get("inputs", [])
            if not isinstance(inputs_list, list):
                return json.dumps({"error": f"Node '{node_id}' has no inputs"}, ensure_ascii=False)
            original_len = len(inputs_list)
            config["inputs"] = [
                i for i in inputs_list if i.get("key") != var_key and i.get("name") != var_key
            ]
            removed = original_len - len(config["inputs"])
        else:  # output
            outputs_list = config.get("outputs", [])
            if not isinstance(outputs_list, list):
                return json.dumps({"error": f"Node '{node_id}' has no outputs"}, ensure_ascii=False)
            original_len = len(outputs_list)
            config["outputs"] = [
                o for o in outputs_list if o.get("key") != var_key and o.get("name") != var_key
            ]
            removed = original_len - len(config["outputs"])

        if removed == 0:
            return json.dumps(
                {"error": f"Variable '{var_key}' not found in {var_type}s of node '{node_id}'"},
                ensure_ascii=False,
            )

        self._save_canvas(workflow_id, nodes, edges)
        return json.dumps(
            {
                "node_id": node_id,
                "variable_key": var_key,
                "variable_type": var_type,
                "removed": removed,
                "success": True,
            },
            ensure_ascii=False,
        )


class WorkflowGetNodeIOTool(_WorkflowToolBase):
    """Get detailed input/output definitions for workflow nodes."""

    @property
    def name(self) -> str:
        return "get_node_io"

    @property
    def description(self) -> str:
        return (
            "Get detailed input/output definitions for a specific node or all nodes. "
            "Use this to inspect what inputs a node accepts and what outputs it produces, "
            "before adding variables or setting bindings."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "description": "Optional: specific node ID. If omitted, returns IO summary for all nodes.",
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        target_node_id = kwargs.get("node_id")

        nodes, edges = self._load_canvas(workflow_id)

        from backend.services.workflow.auto_binding import _extract_inputs, _extract_outputs

        if target_node_id:
            node = next((n for n in nodes if n["id"] == target_node_id), None)
            if not node:
                return json.dumps(
                    {"error": f"Node '{target_node_id}' not found"},
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "node_id": node["id"],
                    "type": node.get("type", ""),
                    "label": node.get("label", ""),
                    "inputs": _extract_inputs(node),
                    "outputs": _extract_outputs(node),
                },
                ensure_ascii=False,
                default=str,
            )

        # Return summary for all nodes
        result = []
        for node in nodes:
            inputs = _extract_inputs(node)
            outputs = _extract_outputs(node)
            result.append(
                {
                    "node_id": node["id"],
                    "type": node.get("type", ""),
                    "label": node.get("label", ""),
                    "inputs": [
                        {
                            "key": i.get("key"),
                            "type": i.get("type", "string"),
                            "value": i.get("value", ""),
                        }
                        for i in inputs
                    ],
                    "outputs": [
                        {"key": o.get("key"), "type": o.get("type", "string")} for o in outputs
                    ],
                }
            )
        return json.dumps({"nodes": result}, ensure_ascii=False, default=str)


class WorkflowGetNodesTool(_WorkflowToolBase):
    """Get all nodes in the current workflow with their full configuration."""

    @property
    def name(self) -> str:
        return "get_nodes"

    @property
    def description(self) -> str:
        return (
            "Get a complete list of all nodes in the current workflow, including their IDs, types, "
            "names, positions, and full configurations (prompts, URLs, code, etc.). "
            "Use this when you need to inspect the current state of the workflow before making changes."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        nodes, edges = self._load_canvas(workflow_id)

        result_nodes = []
        for node in nodes:
            config = node.get("config", {})
            if not isinstance(config, dict):
                config = {}
            result_nodes.append(
                {
                    "id": node["id"],
                    "type": node.get("type", ""),
                    "label": node.get("label", ""),
                    "position": {"x": node.get("position_x", 0), "y": node.get("position_y", 0)},
                    "width": node.get("width", 200),
                    "height": node.get("height", 80),
                    "config": config,
                }
            )

        return json.dumps(
            {
                "nodes": result_nodes,
                "node_count": len(result_nodes),
                "edge_count": len(edges),
            },
            ensure_ascii=False,
            default=str,
        )


class WorkflowListDatabaseTablesTool(_WorkflowToolBase):
    """List all user-defined database tables and their schemas."""

    @property
    def name(self) -> str:
        return "list_database_tables"

    @property
    def description(self) -> str:
        return (
            "List all user-defined database tables available for the database node. "
            "Returns table names, descriptions, and column schemas. "
            "Use this before configuring a database node to know which tables exist and what columns they have."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        from backend.data.db_store import DBRepository

        db = self.db
        repo = DBRepository(db)
        tables = repo.list_tables()

        result = []
        for t in tables:
            fields = []
            with contextlib.suppress(json.JSONDecodeError):
                fields = json.loads(t.fields_json or "[]")
            result.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "fields": [
                        {
                            "name": f.get("name", ""),
                            "type": f.get("type", "string"),
                            "description": f.get("description", ""),
                            "required": f.get("required", False),
                        }
                        for f in fields
                    ],
                }
            )

        return json.dumps(
            {
                "tables": result,
                "count": len(result),
            },
            ensure_ascii=False,
            default=str,
        )


class WorkflowRemoveNodeTool(_WorkflowToolBase):
    """Remove a node and its connected edges."""

    @property
    def name(self) -> str:
        return "remove_node"

    @property
    def description(self) -> str:
        return "Remove a node from the workflow along with all its connected edges."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
            },
            "required": ["node_id"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        node_id = kwargs["node_id"]

        nodes, edges = self._load_canvas(workflow_id)

        original_count = len(nodes)
        nodes = [n for n in nodes if n["id"] != node_id]
        if len(nodes) == original_count:
            return json.dumps({"error": f"Node '{node_id}' not found"}, ensure_ascii=False)

        edges = [e for e in edges if e["source"] != node_id and e["target"] != node_id]
        self._save_canvas(workflow_id, nodes, edges)

        return json.dumps({"node_id": node_id, "removed": True}, ensure_ascii=False)


class WorkflowUpdateNodeTool(_WorkflowToolBase):
    """Update an existing node's configuration, name, or position."""

    @property
    def name(self) -> str:
        return "update_node"

    @property
    def description(self) -> str:
        return (
            "Update an existing node's fixed configuration parameters, display name, or position. "
            "Use this to set systemPrompt, userPrompt, temperature, maxToken, modelId, providerId, etc. "
            "For chatNode: config.systemPrompt sets the system role, config.userPrompt sets the user message template. "
            "For database node: config.tableName, config.operation ('QUERY'/'INSERT'/'UPDATE'/'DELETE'), "
            "config.fieldMappings (array of {name, value} objects), config.whereCondition, config.orderBy. "
            "These fields support {{variableName}} references to the node's input variables (e.g. {{input}}, {{systemPrompt}}). "
            "For binding inputs to upstream outputs, use set_variable instead. "
            "Only the provided fields will be updated; others remain unchanged."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "ID of the node to update"},
                "name": {"type": "string", "description": "New display name (optional)"},
                "config": {
                    "type": "object",
                    "description": "Configuration updates to merge (e.g. {'systemPrompt': 'new prompt', 'temperature': 0.5})",
                },
                "position": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                    "description": "New position (optional)",
                },
            },
            "required": ["node_id"],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        node_id = kwargs["node_id"]

        nodes, edges = self._load_canvas(workflow_id)

        node = next((n for n in nodes if n["id"] == node_id), None)
        if not node:
            return json.dumps({"error": f"Node '{node_id}' not found"}, ensure_ascii=False)

        # Update name
        if "name" in kwargs:
            node["label"] = kwargs["name"]

        # Update position
        position = kwargs.get("position", {})
        if "x" in position:
            node["position_x"] = position["x"]
        if "y" in position:
            node["position_y"] = position["y"]

        # Update config (merge, not replace)
        config_updates = kwargs.get("config", {})
        if config_updates:
            node_config = node.get("config", {})
            if not isinstance(node_config, dict):
                node_config = {}
            for key, value in config_updates.items():
                if key == "inputs" and isinstance(value, list):
                    # Merge inputs by key
                    existing_inputs = node_config.get("inputs", [])
                    input_map = {
                        (i.get("key") or i.get("name")): i
                        for i in existing_inputs
                        if isinstance(i, dict)
                    }
                    for new_inp in value:
                        if not isinstance(new_inp, dict):
                            continue
                        inp_key = new_inp.get("key") or new_inp.get("name")
                        if inp_key and inp_key in input_map:
                            input_map[inp_key].update(new_inp)
                        else:
                            existing_inputs.append(new_inp)
                    node_config["inputs"] = existing_inputs
                else:
                    node_config[key] = value
            node["config"] = node_config

        self._save_canvas(workflow_id, nodes, edges)

        return json.dumps(
            {
                "node_id": node_id,
                "updated": True,
                "name": node["label"],
                "config": node.get("config", {}),
            },
            ensure_ascii=False,
        )


class WorkflowAutoLayoutTool(_WorkflowToolBase):
    """Apply automatic layout to the workflow canvas."""

    @property
    def name(self) -> str:
        return "auto_layout"

    @property
    def description(self) -> str:
        return "Rearrange all nodes in the workflow into a clean left-to-right layout."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "algorithm": {
                    "type": "string",
                    "enum": ["grid", "topological"],
                    "description": "Layout algorithm to use",
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        algorithm = kwargs.get("algorithm", "topological")

        nodes, edges = self._load_canvas(workflow_id)

        if not nodes:
            return json.dumps({"message": "No nodes to layout"}, ensure_ascii=False)

        # Build adjacency list
        adjacency: dict[str, list[str]] = {n["id"]: [] for n in nodes}
        for e in edges:
            if e["source"] in adjacency:
                adjacency[e["source"]].append(e["target"])

        # Simple topological level assignment
        levels: dict[str, int] = {}
        in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
        for e in edges:
            if e["target"] in in_degree:
                in_degree[e["target"]] += 1

        queue = [n_id for n_id, deg in in_degree.items() if deg == 0]
        for n_id in queue:
            levels[n_id] = 0

        while queue:
            current = queue.pop(0)
            for neighbor in adjacency.get(current, []):
                levels[neighbor] = max(levels.get(neighbor, 0), levels[current] + 1)
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Assign positions
        level_counts: dict[int, int] = {}
        for n in nodes:
            lvl = levels.get(n["id"], 0)
            n["position_x"] = 100 + lvl * 300
            idx = level_counts.get(lvl, 0)
            n["position_y"] = 100 + idx * 150
            level_counts[lvl] = idx + 1

        self._save_canvas(workflow_id, nodes, edges)

        return json.dumps(
            {
                "algorithm": algorithm,
                "node_count": len(nodes),
                "success": True,
            },
            ensure_ascii=False,
        )


class WorkflowValidateTool(_WorkflowToolBase):
    """Validate the workflow for structural correctness."""

    @property
    def name(self) -> str:
        return "validate_workflow"

    @property
    def description(self) -> str:
        return "Check the workflow for common issues: missing start/end, disconnected nodes, invalid variable references."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        nodes, edges = self._load_canvas(workflow_id)

        errors: list[str] = []
        warnings: list[str] = []

        # Check for start/end
        has_start = any(n["type"] in ("workflowStart", "start") for n in nodes)
        has_end = any(n["type"] in ("workflowEnd", "end") for n in nodes)
        if not has_start:
            errors.append("Missing workflow start node")
        if not has_end:
            errors.append("Missing workflow end node")

        # Check for disconnected nodes (except start)
        connected_ids = set()
        for e in edges:
            connected_ids.add(e["source"])
            connected_ids.add(e["target"])
        for n in nodes:
            if n["type"] not in ("workflowStart", "start") and n["id"] not in connected_ids:
                warnings.append(f"Node '{n['label']}' ({n['id']}) is disconnected")

        # Check for dangling variable references
        node_ids = {n["id"] for n in nodes}
        for n in nodes:
            config = n.get("config", {})
            if not isinstance(config, dict):
                continue
            inputs_list = config.get("inputs", [])
            for inp in inputs_list:
                val = inp.get("value", "")
                if val and val.startswith("{{") and val.endswith("}}") and val != "{{?}}":
                    ref = val[2:-2]  # strip {{}}
                    if "." in ref:
                        ref_node_id = ref.split(".")[0]
                        if ref_node_id not in node_ids:
                            errors.append(
                                f"Node '{n['id']}' references unknown node '{ref_node_id}'"
                            )

        result = {
            "valid": len(errors) == 0,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
        }
        return json.dumps(result, ensure_ascii=False)


class WorkflowRunTestTool(_WorkflowToolBase):
    """Run the workflow in test mode."""

    @property
    def name(self) -> str:
        return "run_test"

    @property
    def description(self) -> str:
        return "Execute the workflow in test mode with optional input variables. Returns execution trace."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "inputs": {
                    "type": "object",
                    "description": "Optional input variables, e.g. {'userChatInput': 'hello'}",
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        inputs = kwargs.get("inputs", {})

        version = self.store.get_latest_version(workflow_id)
        if not version:
            return json.dumps({"error": "No version found for workflow"}, ensure_ascii=False)

        trace: list[dict] = []

        async def on_node_update(run_id: str, node_id: str | None, status: str, data: dict):
            trace.append(
                {
                    "run_id": run_id,
                    "node_id": node_id,
                    "status": status,
                    "data": data,
                }
            )

        try:
            result = await self.engine.execute(
                workflow_id=workflow_id,
                version_id=version.id,
                input_variables=inputs,
                trigger_type="test",
                on_node_update=on_node_update,
                test_mode=True,
            )
            return json.dumps(
                {
                    "success": result.status == "completed",
                    "status": result.status,
                    "output": result.output_result,
                    "trace": trace,
                },
                ensure_ascii=False,
                default=str,
            )
        except Exception as e:
            logger.error(f"[WorkflowRunTestTool] Test execution failed: {e}")
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                    "trace": trace,
                },
                ensure_ascii=False,
            )


class WorkflowGetVariableContextTool(_WorkflowToolBase):
    """Get the current variable context for AI prompt injection."""

    @property
    def name(self) -> str:
        return "get_variable_context"

    @property
    def description(self) -> str:
        return "Get a markdown summary of all available variables in the current workflow for reference."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        workflow_id = self._current_workflow_id
        nodes, edges = self._load_canvas(workflow_id)

        lines = ["## 当前画布状态", ""]

        if not nodes:
            lines.append("（画布为空，尚无节点）")
            lines.append("")
            lines.append("## 变量引用语法")
            lines.append("使用 {{nodeId.outputKey}} 语法引用上游输出")
            lines.append("示例: {{workflowStart-1.userChatInput}}, {{chatNode-1.answerText}}")
            lines.append("如果不确定最佳匹配，使用 {{?}} 占位符")
            return "\n".join(lines)

        lines.append("### 节点列表")
        for node in nodes:
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            label = node.get("label", node_id)
            config = node.get("config", {})
            pos_x = node.get("position_x", 0)
            pos_y = node.get("position_y", 0)
            lines.append(f"- {node_id} ({node_type}, 名称: {label}, 位置: {pos_x},{pos_y})")
            # 显示关键配置
            cfg_items = []
            for k, v in config.items():
                if k in ("inputs", "outputs", "name", "intro"):
                    continue
                if isinstance(v, str) and len(v) > 60:
                    v = v[:60] + "..."
                cfg_items.append(f"{k}={v}")
            if cfg_items:
                lines.append(f"  配置: {', '.join(cfg_items)}")
            # 显示输入绑定
            inputs = config.get("inputs", [])
            bound = [f"{i.get('key')}={i.get('value', '')}" for i in inputs if i.get("value")]
            if bound:
                lines.append(f"  输入绑定: {', '.join(bound)}")

        lines.append("")
        lines.append("### 连线")
        if edges:
            for edge in edges:
                src = edge.get("source", "")
                tgt = edge.get("target", "")
                cond = edge.get("condition", "")
                if cond:
                    lines.append(f"- {src} → {tgt} (条件: {cond})")
                else:
                    lines.append(f"- {src} → {tgt}")
        else:
            lines.append("（暂无连线）")

        lines.append("")
        lines.append("### 可用输出变量")
        for node in nodes:
            node_id = node.get("id", "")
            node_type = node.get("type", "")
            label = node.get("label", node_id)
            outputs = _extract_outputs(node)
            if not outputs:
                continue
            lines.append(f"- {node_id} ({node_type}, 名称: {label}):")
            for o in outputs:
                lines.append(
                    f"  - {o['key']} [{o['type']}]"
                    + (f" — {o.get('label', '')}" if o.get("label") else "")
                )

        lines.append("")
        lines.append("## 变量引用语法")
        lines.append("使用 {{nodeId.outputKey}} 语法引用上游输出")
        lines.append("示例: {{workflowStart-1.userChatInput}}, {{chatNode-1.answerText}}")
        lines.append("如果不确定最佳匹配，使用 {{?}} 占位符")

        return "\n".join(lines)
