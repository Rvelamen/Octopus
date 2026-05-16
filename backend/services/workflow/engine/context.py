"""Workflow execution context."""

from __future__ import annotations

import re
import time
import logging
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class NodeExecutionTrace:
    """Execution trace for a single node."""
    node_id: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    start_time: Optional[float] = None  # Unix timestamp
    end_time: Optional[float] = None  # Unix timestamp
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    output_snapshot: dict[str, Any] = field(default_factory=dict)
    error_detail: Optional[dict[str, Any]] = None
    retry_count: int = 0
    logs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
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
        input_variables: Optional[dict[str, Any]] = None,
        version_id: Optional[str] = None,
    ):
        """Initialize context with input variables.

        Args:
            input_variables: Initial variables.
            version_id: Version ID for sub-workflow resolution.
        """
        self._variables = input_variables or {}
        self._node_outputs: dict[str, dict[str, Any]] = {}
        self._current_node_id: Optional[str] = None
        self._version_id: Optional[str] = version_id
        # Trace recording
        self._node_traces: dict[str, NodeExecutionTrace] = {}
        self._logs: list[dict[str, Any]] = []

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
        status: Optional[str] = None,
        input_snapshot: Optional[dict[str, Any]] = None,
        output_snapshot: Optional[dict[str, Any]] = None,
        error_detail: Optional[dict[str, Any]] = None,
        retry_count: Optional[int] = None,
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
                f"Node {node_id} {status}"
            )

    def add_trace_log(self, node_id: str, level: str, message: str) -> None:
        """Add a log entry to a node's trace."""
        trace = self._node_traces.get(node_id)
        if trace:
            trace.logs.append({
                "timestamp": time.time(),
                "level": level,
                "message": message,
            })

    def add_log(self, level: str, message: str) -> None:
        """Add a log entry to the workflow context."""
        self._logs.append({
            "timestamp": time.time(),
            "level": level,
            "message": message,
        })

    def get_node_trace(self, node_id: str) -> Optional[NodeExecutionTrace]:
        """Get execution trace for a node."""
        return self._node_traces.get(node_id)

    def get_all_traces(self) -> dict[str, dict[str, Any]]:
        """Get all node traces as dictionaries."""
        return {
            node_id: trace.to_dict()
            for node_id, trace in self._node_traces.items()
        }

    def get_workflow_logs(self) -> list[dict[str, Any]]:
        """Get all workflow logs."""
        return self._logs.copy()

    def set_current_node(self, node_id: str) -> None:
        """Set current executing node."""
        self._current_node_id = node_id

    def get_current_node(self) -> Optional[str]:
        """Get current executing node."""
        return self._current_node_id

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
            match = re.match(r'^\{\{(.+?)\}\}$', value.strip())
            if match:
                ref = match.group(1)
                if '.' in ref:
                    parts = ref.split('.', 1)
                    node_id, output_key = parts[0], parts[1]
                    result = self.get_node_output(node_id, output_key)
                    if result is not None:
                        return result
                    fallback = self.get_variable(output_key)
                    if fallback is not None:
                        return fallback
                    logger.warning(
                        f"未解析的节点输出引用: {{{ref}}}, "
                        "节点ID=%s, 输出Key=%s, "
                        "可用节点=%s",
                        node_id,
                        output_key,
                        list(self._node_outputs.keys()),
                    )
                    return f"[未解析变量: {value}]"
                else:
                    result = self.get_variable(ref)
                    if result is not None:
                        return result
                    logger.warning(
                        f"未解析的全局变量引用: {{{ref}}}, 可用变量=%s",
                        list(self._variables.keys()),
                    )
                    return f"[未解析变量: {value}]"

            def replace_ref(match):
                ref = match.group(1)
                if '.' in ref:
                    parts = ref.split('.', 1)
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
                    return f"[未解析: {match.group(0)}]"
                else:
                    result = self.get_variable(ref)
                    if result is not None:
                        return str(result)
                    logger.warning("字符串内嵌全局变量未解析: {{{ref}}}", ref=ref)
                    return f"[未解析: {match.group(0)}]"

            return re.sub(r'\{\{(.+?)\}\}', replace_ref, value)

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
            "node_outputs": {
                k: v.copy() for k, v in self._node_outputs.items()
            },
            "current_node_id": self._current_node_id,
            "version_id": self._version_id,
            "traces": self.get_all_traces(),
            "logs": self.get_workflow_logs(),
        }
