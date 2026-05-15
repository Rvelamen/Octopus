import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  GitBranch,
  ChevronDown,
  ChevronRight,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  SkipForward,
  AlertCircle,
  ExternalLink,
} from "lucide-react";
import { useWorkflowStore } from "../../workflow/hooks/useWorkflowStore";
import "./WorkflowStatusFold.css";

const STATUS_META = {
  pending:   { color: "#f59e0b", icon: Clock,       label: "Pending" },
  running:   { color: "#3b82f6", icon: Loader2,     label: "Running" },
  paused:    { color: "#a855f7", icon: AlertCircle, label: "Paused" },
  completed: { color: "#22c55e", icon: CheckCircle, label: "Completed" },
  failed:    { color: "#ef4444", icon: XCircle,     label: "Failed" },
  cancelled: { color: "#6b7280", icon: XCircle,     label: "Cancelled" },
};

const NODE_STATUS_META = {
  pending:   { color: "#9ca3af", icon: Clock },
  running:   { color: "#3b82f6", icon: Loader2 },
  completed: { color: "#22c55e", icon: CheckCircle },
  failed:    { color: "#ef4444", icon: XCircle },
  skipped:   { color: "#d1d5db", icon: SkipForward },
};

export default function WorkflowStatusFold({ message }) {
  const navigate = useNavigate();
  const [isExpanded, setIsExpanded] = useState(false);
  const setPendingOpenRun = useWorkflowStore((s) => s.setPendingOpenRun);

  const meta = message.metadata || {};
  const status = meta.status || "pending";
  const statusMeta = STATUS_META[status] || STATUS_META.pending;
  const StatusIcon = statusMeta.icon;

  const workflowName = meta.workflow_name || "Workflow";
  const runId = meta.workflow_run_id;
  const workflowId = meta.workflow_id;
  const progress = meta.progress || { completed: 0, total: 0 };
  const nodeStatuses = meta.node_statuses || {};
  const error = meta.error;

  const total = progress.total || 1;
  const completed = progress.completed || 0;
  const pct = Math.min(100, Math.round((completed / total) * 100));

  const handleOpenDetail = () => {
    // Use Zustand store instead of sessionStorage for cross-page communication
    setPendingOpenRun({ runId, workflowName, workflowId });
    navigate("/workflows");
  };

  return (
    <div className="workflow-status-fold">
      {/* Header */}
      <div
        className="workflow-status-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="workflow-status-header-left">
          {isExpanded ? (
            <ChevronDown size={14} className="workflow-status-chevron" />
          ) : (
            <ChevronRight size={14} className="workflow-status-chevron" />
          )}
          <GitBranch size={14} className="workflow-status-branch-icon" />
          <span className="workflow-status-name">{workflowName}</span>
        </div>

        <div className="workflow-status-header-right">
          <div
            className="workflow-status-badge"
            style={{
              background: statusMeta.color + "18",
              color: statusMeta.color,
            }}
          >
            <StatusIcon
              size={12}
              className={status === "running" ? "spinning" : ""}
            />
            <span>{statusMeta.label}</span>
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="workflow-status-progress-row">
        <div className="workflow-status-progress-track">
          <div
            className="workflow-status-progress-fill"
            style={{
              width: `${pct}%`,
              background: statusMeta.color,
            }}
          />
        </div>
        <span className="workflow-status-progress-text">
          {completed}/{total}
        </span>
      </div>

      {/* Expanded body */}
      {isExpanded && (
        <div className="workflow-status-body">
          {error && (
            <div className="workflow-status-error">{error}</div>
          )}

          {Object.keys(nodeStatuses).length > 0 && (
            <div className="workflow-status-nodes">
              {Object.entries(nodeStatuses).map(([nodeId, ns]) => {
                const nsMeta = NODE_STATUS_META[ns] || NODE_STATUS_META.pending;
                const NsIcon = nsMeta.icon;
                return (
                  <div key={nodeId} className="workflow-status-node-item">
                    <NsIcon
                      size={10}
                      color={nsMeta.color}
                      className={ns === "running" ? "spinning" : ""}
                    />
                    <span
                      className="workflow-status-node-id"
                      title={nodeId}
                    >
                      {nodeId}
                    </span>
                    <span
                      className="workflow-status-node-label"
                      style={{ color: nsMeta.color }}
                    >
                      {ns}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          <button
            className="workflow-status-open-btn"
            onClick={(e) => {
              e.stopPropagation();
              handleOpenDetail();
            }}
          >
            <ExternalLink size={12} />
            Open in Workflows
          </button>
        </div>
      )}
    </div>
  );
}
