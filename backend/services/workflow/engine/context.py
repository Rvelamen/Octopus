"""Workflow execution context."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NodeExecutionTrace:
    """Execution trace for a single node."""

    node_id: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    start_time: float | None = None  # Unix timestamp
    end_time: float | None = None  # Unix timestamp
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    output_snapshot: dict[str, Any] = field(default_factory=dict)
    error_detail: dict[str, Any] | None = None
    retry_count: int = 0
    logs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        """Get execution duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "input_snapshot": self.input_snapshot,
            "output_snapshot": self.output_snapshot,
            "error_detail": self.error_detail,
            "retry_count": self.retry_count,
            "logs": self.logs,
        }


class WorkflowContext:
    """Context for workflow execution.

    Manages variables, node outputs, and execution traces during workflow execution.
    """

    def __init__(
        self,
        input_variables: dict[str, Any] | None = None,
        version_id: str | None = None,
    ):
        """Initialize context with input variables.

        Args:
            input_variables: Initial variables.
            version_id: Version ID for sub-workflow resolution.
        """
        self._variables = input_variables or {}
        self._node_outputs: dict[str, dict[str, Any]] = {}
        self._current_node_id: str | None = None
        self._current_inputs: dict[str, Any] = {}
        self._version_id: str | None = version_id
        # Trace recording
        self._node_traces: dict[str, NodeExecutionTrace] = {}
        self._logs: list[dict[str, Any]] = []
        # Unresolved variable references per node
        self._unresolved_refs: dict[str, list[dict[str, Any]]] = {}

    def start_node_trace(self, node_id: str) -> NodeExecutionTrace:
        """Start recording execution trace for a node."""
        trace = NodeExecutionTrace(
            node_id=node_id,
            status="running",
            start_time=time.time(),
        )
        self._node_traces[node_id] = trace
        self.add_log("info", f"Node {node_id} started")
        return trace

    def update_node_trace(
        self,
        node_id: str,
        status: str | None = None,
        input_snapshot: dict[str, Any] | None = None,
        output_snapshot: dict[str, Any] | None = None,
        error_detail: dict[str, Any] | None = None,
        retry_count: int | None = None,
    ) -> None:
        """Update execution trace for a node."""
        trace = self._node_traces.get(node_id)
        if not trace:
            trace = NodeExecutionTrace(node_id=node_id)
            self._node_traces[node_id] = trace

        if status:
            trace.status = status
        if status in ("completed", "failed", "skipped"):
            trace.end_time = time.time()
        if input_snapshot is not None:
            trace.input_snapshot = input_snapshot
        if output_snapshot is not None:
            trace.output_snapshot = output_snapshot
        if error_detail is not None:
            trace.error_detail = error_detail
        if retry_count is not None:
            trace.retry_count = retry_count

        if status:
            self.add_log(
                "info" if status == "completed" else "error" if status == "failed" else "warn",
                f"Node {node_id} {status}",
            )

    def add_trace_log(self, node_id: str, level: str, message: str) -> None:
        """Add a log entry to a node's trace."""
        trace = self._node_traces.get(node_id)
        if trace:
            trace.logs.append(
                {
                    "timestamp": time.time(),
                    "level": level,
                    "message": message,
                }
            )

    def add_log(self, level: str, message: str) -> None:
        """Add a log entry to the workflow context."""
        self._logs.append(
            {
                "timestamp": time.time(),
                "level": level,
                "message": message,
            }
        )

    def get_node_trace(self, node_id: str) -> NodeExecutionTrace | None:
        """Get execution trace for a node."""
        return self._node_traces.get(node_id)

    def get_all_traces(self) -> dict[str, dict[str, Any]]:
        """Get all node traces as dictionaries."""
        return {node_id: trace.to_dict() for node_id, trace in self._node_traces.items()}

    def get_workflow_logs(self) -> list[dict[str, Any]]:
        """Get all workflow logs."""
        return self._logs.copy()

    def set_current_node(self, node_id: str) -> None:
        """Set current executing node."""
        self._current_node_id = node_id
        self._current_inputs = {}

    def get_current_node(self) -> str | None:
        """Get current executing node."""
        return self._current_node_id

    def record_unresolved_ref(
        self, node_id: str, ref: str, ref_type: str, details: dict[str, Any] | None = None
    ) -> None:
        """Record an unresolved variable reference for a node."""
        if node_id not in self._unresolved_refs:
            self._unresolved_refs[node_id] = []
        entry = {"ref": ref, "type": ref_type}
        if details:
            entry.update(details)
        self._unresolved_refs[node_id].append(entry)
        # Also add to node trace logs
        self.add_trace_log(node_id, "warning", f"未解析变量引用: {{{ref}}}")

    def get_unresolved_refs(self, node_id: str) -> list[dict[str, Any]]:
        """Get unresolved references for a node."""
        return self._unresolved_refs.get(node_id, []).copy()

    def clear_unresolved_refs(self, node_id: str) -> None:
        """Clear unresolved references for a node."""
        self._unresolved_refs.pop(node_id, None)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a global variable."""
        self._variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a global variable."""
        return self._variables.get(name, default)

    def set_node_output(self, node_id: str, key: str, value: Any) -> None:
        """Set a node output value."""
        if node_id not in self._node_outputs:
            self._node_outputs[node_id] = {}
        self._node_outputs[node_id][key] = value

    def get_node_output(self, node_id: str, key: str, default: Any = None) -> Any:
        """Get a node output value."""
        return self._node_outputs.get(node_id, {}).get(key, default)

    def get_all_outputs(self) -> dict[str, Any]:
        """Get all node outputs."""
        result = {}
        for node_id, outputs in self._node_outputs.items():
            for key, value in outputs.items():
                result[f"{node_id}.{key}"] = value
        return result

    def resolve_value(self, value: Any) -> Any:
        """Resolve a value that may contain variable references.

        Variable references are in the format {{nodeId.outputKey}} or {{variableName}}.
        When resolution fails, returns a clear marker instead of the raw reference string.
        """
        if isinstance(value, str):
            match = re.match(r"^\{\{(.+?)\}\}$", value.strip())
            if match:
                ref = match.group(1)
                if "." in ref:
                    parts = ref.split(".", 1)
                    node_id, output_key = parts[0], parts[1]
                    result = self.get_node_output(node_id, output_key)
                    if result is not None:
                        return result
                    fallback = self.get_variable(output_key)
                    if fallback is not None:
                        return fallback
                    logger.warning(
                        f"未解析的节点输出引用: {{{ref}}}, 节点ID=%s, 输出Key=%s, 可用节点=%s",
                        node_id,
                        output_key,
                        list(self._node_outputs.keys()),
                    )
                    self.record_unresolved_ref(
                        self._current_node_id or node_id,
                        ref,
                        "node_output",
                        {
                            "node_id": node_id,
                            "output_key": output_key,
                            "available_nodes": list(self._node_outputs.keys()),
                        },
                    )
                    # Variable not found → keep the original {{xxx}} text as-is
                    return value
                else:
                    # {{varName}} → 只在当前节点已定义的 inputs 中查找
                    if ref in self._current_inputs:
                        return self._current_inputs[ref]
                    # 不在当前节点 inputs 中 → 保持原样不解析
                    return value

            def replace_ref(match):
                ref = match.group(1)
                if "." in ref:
                    parts = ref.split(".", 1)
                    node_id, output_key = parts[0], parts[1]
                    result = self.get_node_output(node_id, output_key)
                    if result is not None:
                        return str(result)
                    fallback = self.get_variable(output_key)
                    if fallback is not None:
                        return str(fallback)
                    logger.warning(
                        "字符串内嵌变量引用未解析: {{{ref}}}, 节点ID=%s, 输出Key=%s",
                        node_id,
                        output_key,
                    )
                    self.record_unresolved_ref(
                        self._current_node_id or node_id,
                        ref,
                        "inline_node_output",
                        {"node_id": node_id, "output_key": output_key},
                    )
                    # Variable not found → keep the original {{xxx}} text as-is
                    return match.group(0)
                else:
                    # {{varName}} → 只在当前节点已定义的 inputs 中查找
                    if ref in self._current_inputs:
                        return str(self._current_inputs[ref])
                    # 不在当前节点 inputs 中 → 保持原样不解析
                    return match.group(0)

            return re.sub(r"\{\{(.+?)\}\}", replace_ref, value)

        elif isinstance(value, dict):
            return {k: self.resolve_value(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [self.resolve_value(item) for item in value]

        return value

    def resolve_inputs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Resolve all input values."""
        return {k: self.resolve_value(v) for k, v in inputs.items()}

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "variables": self._variables.copy(),
            "node_outputs": {k: v.copy() for k, v in self._node_outputs.items()},
            "current_node_id": self._current_node_id,
            "version_id": self._version_id,
            "traces": self.get_all_traces(),
            "logs": self.get_workflow_logs(),
            "unresolved_refs": {k: v for k, v in self._unresolved_refs.items() if v},
        }
