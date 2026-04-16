import { useState, useMemo } from 'react';
import { Bot, Clock, Coins, ChevronDown, ChevronRight, AlertTriangle, XCircle, Eye } from 'lucide-react';
import { Modal } from 'antd';
import IterationFold from './IterationFold.jsx';
import './SubagentSyncFold.css';

function formatTokens(count) {
  if (!count || count === 0) return '0';
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
  return count.toString();
}

function formatDuration(seconds) {
  if (!seconds || seconds === 0) return '0s';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}m ${secs}s`;
}

function iterationsToSegments(iterations) {
  if (!iterations || !Array.isArray(iterations)) return [];
  const segments = [];
  for (const iter of iterations) {
    if (iter.reasoning) {
      segments.push({ type: 'reasoning', text: iter.reasoning });
    }
    for (const tool of iter.tools || []) {
      segments.push({
        type: 'tool',
        toolCallId: tool.toolCallId,
        toolName: tool.toolName,
        args: typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args || {}),
        result: tool.result,
        status: tool.status || 'completed',
        error: tool.status === 'error' ? tool.result : undefined,
      });
    }
  }
  return segments;
}

function SubagentSyncFold({ result }) {
  const [expanded, setExpanded] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);

  if (!result) return null;

  const {
    status = 'completed',
    label = 'Subagent',
    summary = '',
    token_usage = {},
    duration = 0,
    iterations = [],
  } = result;

  const totalTokens = (token_usage.prompt_tokens || 0) + (token_usage.completion_tokens || 0);
  const hasIterations = Array.isArray(iterations) && iterations.length > 0;
  const detailSegments = useMemo(() => iterationsToSegments(iterations), [iterations]);

  const getStatusIcon = () => {
    switch (status) {
      case 'completed':
        return <Bot size={16} className="status-icon success" />;
      case 'timeout':
        return <AlertTriangle size={16} className="status-icon warning" />;
      case 'error':
        return <XCircle size={16} className="status-icon error" />;
      default:
        return <Bot size={16} className="status-icon" />;
    }
  };

  const getStatusBadge = () => {
    if (status === 'completed') return null;
    const text = status === 'timeout' ? '超时' : '错误';
    const className = `status-badge ${status}`;
    return <span className={className}>{text}</span>;
  };

  return (
    <>
      <div className="subagent-sync-fold">
        <div
          className="subagent-header"
          onClick={() => setExpanded(!expanded)}
        >
          <span className="expand-icon">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
          {getStatusIcon()}
          <span className="label">{label}</span>
          <span className="meta-info">
            <span className="meta-item">
              <Clock size={12} />
              {formatDuration(duration)}
            </span>
            {totalTokens > 0 && (
              <span className="meta-item">
                <Coins size={12} />
                {formatTokens(totalTokens)} tokens
              </span>
            )}
          </span>
          {getStatusBadge()}
          {hasIterations && (
            <span
              className="detail-btn"
              onClick={(e) => {
                e.stopPropagation();
                setDetailOpen(true);
              }}
              title="查看 ReAct 执行流程"
            >
              <Eye size={13} />
              <span>详情</span>
            </span>
          )}
        </div>

        {expanded && summary && (
          <div className="subagent-body">
            <div className="subagent-summary">
              {summary.split('\n').map((line, i) => {
                if (line.startsWith('**') && line.includes('**')) {
                  const parts = line.split(/\*\*(.*?)\*\*/g);
                  return (
                    <p key={i} className="summary-line">
                      {parts.map((part, j) =>
                        j % 2 === 1 ? <strong key={j}>{part}</strong> : part
                      )}
                    </p>
                  );
                }
                if (line.startsWith('- ') || line.startsWith('* ')) {
                  return <li key={i}>{line.substring(2)}</li>;
                }
                if (line.trim() === '') return null;
                return <p key={i}>{line}</p>;
              })}
            </div>
          </div>
        )}
      </div>

      <Modal
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        title={
          <div className="subagent-detail-title">
            <Bot size={16} />
            <span>{label} — ReAct 流程</span>
          </div>
        }
        width={720}
        footer={null}
        className="subagent-detail-modal"
        destroyOnHidden
      >
        <div className="subagent-detail-content">
          {detailSegments.length > 0 ? (
            <IterationFold
              status={status === 'completed' ? 'completed' : status}
              segments={detailSegments}
              totalMs={duration * 1000}
              tokenUsage={token_usage}
            />
          ) : (
            <div className="subagent-detail-empty">暂无执行流程记录</div>
          )}
        </div>
      </Modal>
    </>
  );
}

export default SubagentSyncFold;
