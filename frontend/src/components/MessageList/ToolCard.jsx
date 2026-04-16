import React, { useState, useMemo } from 'react';
import { Wrench, ChevronUp, ChevronDown, Check, Loader2, Copy, Clock, XCircle, AlertCircle, Maximize2, Eye, Bot } from 'lucide-react';
import { Modal, Button, Tag, Space } from 'antd';
import IterationFold from './IterationFold.jsx';

const MAX_PREVIEW_LENGTH = 300;

function formatValue(value) {
  if (value === null) return <Tag color="default">null</Tag>;
  if (typeof value === 'boolean') return <Tag color={value ? 'success' : 'error'}>{String(value)}</Tag>;
  if (typeof value === 'number') return <span className="json-number">{value}</span>;
  if (typeof value === 'string') {
    if (value.length > 200) {
      return (
        <pre className="json-pre">
          {value}
        </pre>
      );
    }
    return <span className="json-string">{value}</span>;
  }
  return (
    <pre className="json-pre">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function JsonCards({ data }) {
  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="json-card-item">
          <div className="json-card-key">{key}</div>
          <div className="json-card-value">{formatValue(value)}</div>
        </div>
      ))}
    </Space>
  );
}

function ViewModal({ title, content, onClose }) {
  if (!content) return null;
  let parsed = null;
  try {
    parsed = JSON.parse(content);
  } catch {}

  return (
    <Modal
      open
      title={<span className="tool-modal-title">{title}</span>}
      onCancel={onClose}
      className="tool-modal-terracotta"
      footer={[
        <Button key="copy" className="tool-modal-btn" onClick={() => navigator.clipboard.writeText(content)}>
          Copy
        </Button>,
        <Button key="close" type="primary" className="tool-modal-btn-primary" onClick={onClose}>
          Close
        </Button>,
      ]}
      width={760}
      bodyStyle={{ maxHeight: 600, overflow: 'auto', padding: 16 }}
    >
      {parsed && typeof parsed === 'object' ? (
        <JsonCards data={parsed} />
      ) : (
        <pre className="tool-modal-plain-pre">
          {content}
        </pre>
      )}
    </Modal>
  );
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

function SubagentDetailModal({ open, onClose, result }) {
  if (!result) return null;
  const {
    label = 'Subagent',
    status = 'completed',
    token_usage = {},
    duration = 0,
    iterations = [],
  } = result;

  const detailSegments = useMemo(() => iterationsToSegments(iterations), [iterations]);

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Bot size={16} style={{ color: '#6366f1' }} />
          <span>{label} — ReAct 流程</span>
        </div>
      }
      width={720}
      footer={null}
      destroyOnHidden
    >
      <div style={{ maxHeight: '70vh', overflowY: 'auto', paddingRight: 4 }}>
        {detailSegments.length > 0 ? (
          <IterationFold
            status={status === 'completed' ? 'completed' : status}
            segments={detailSegments}
            totalMs={duration * 1000}
            tokenUsage={token_usage}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: '#999' }}>
            暂无执行流程记录
          </div>
        )}
      </div>
    </Modal>
  );
}

function ToolCard({
  toolCallId,
  toolName,
  args,
  partialArgs,
  result,
  status,
  error,
  assistantContent,
  toolIndex = 0,
  totalTools = 1,
  renderPlainContent,
  isExpanded: isExpandedProp,
  onToggleExpand,
  compact = false
}) {
  const [isExpandedInternal, setIsExpandedInternal] = useState(false);
  const [modal, setModal] = useState(null);
  const [subagentDetailOpen, setSubagentDetailOpen] = useState(false);

  const isExpanded = isExpandedProp !== undefined ? isExpandedProp : isExpandedInternal;

  const parsedArgs = typeof args === 'string' ? (() => {
    try {
      return JSON.parse(args);
    } catch {
      return {};
    }
  })() : (args || {});

  const displayArgs = partialArgs || parsedArgs || {};

  const handleToggle = () => {
    if (onToggleExpand) {
      onToggleExpand();
    } else {
      setIsExpandedInternal(!isExpandedInternal);
    }
  };

  const parseResult = () => {
    if (!result) return null;
    try {
      const parsed = JSON.parse(result);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return typeof result === 'string' ? result : JSON.stringify(result, null, 2);
    }
  };

  const resultContent = parseResult();

  // 检测是否为 spawn 工具的 subagent_sync 结果
  const subagentResult = useMemo(() => {
    if (toolName !== 'spawn' || !result) return null;
    try {
      const parsed = JSON.parse(result);
      if (parsed.type === 'subagent_sync' && Array.isArray(parsed.iterations) && parsed.iterations.length > 0) {
        return parsed;
      }
    } catch {
      // not valid JSON
    }
    return null;
  }, [toolName, result]);
  const hasSubagentDetail = !!subagentResult;

  const argsString = Object.keys(displayArgs).length > 0
    ? JSON.stringify(displayArgs, null, 2)
    : '';

  const truncateText = (text, maxLength) => {
    if (!text) return { text: '', needsTruncate: false };
    if (text.length <= maxLength) {
      return { text, needsTruncate: false };
    }
    return {
      text: text.slice(0, maxLength),
      needsTruncate: true
    };
  };

  const argsPreview = truncateText(argsString, MAX_PREVIEW_LENGTH);
  const resultPreview = truncateText(resultContent || '', MAX_PREVIEW_LENGTH);

  // Status icon mapping
  const getStatusIcon = () => {
    switch (status) {
      case 'pending':
        return <Clock size={12} className="status-icon pending" />;
      case 'invoking':
        return <Loader2 size={12} className="status-icon invoking spin" />;
      case 'streaming':
        return <Loader2 size={12} className="status-icon streaming spin" />;
      case 'completed':
        return <Check size={12} className="status-icon completed" />;
      case 'error':
        return <XCircle size={12} className="status-icon error" />;
      default:
        return <AlertCircle size={12} className="status-icon default" />;
    }
  };

  // Status text mapping
  const getStatusText = () => {
    switch (status) {
      case 'pending':
        return '等待中';
      case 'invoking':
        return '调用中';
      case 'streaming':
        return '流式传输中';
      case 'completed':
        return '已完成';
      case 'error':
        return '错误';
      default:
        return '';
    }
  };

  return (
    <div className={`tool-card ${compact ? 'tool-card-compact' : ''}`}>
      <div
        className={`tool-card-header ${status}`}
        onClick={handleToggle}
      >
        <div className="tool-card-header-left">
          <div className={`tool-status-indicator ${status}`}>
            {getStatusIcon()}
          </div>
          <Wrench size={12} className="tool-icon" />
          <span className="tool-card-name">{toolName || 'unknown'}</span>
          {totalTools > 1 && (
            <span className="tool-card-index">({toolIndex + 1}/{totalTools})</span>
          )}
          <span className="tool-status-text">{getStatusText()}</span>
        </div>
        <div className="tool-card-header-right">
          {hasSubagentDetail && status === 'completed' && (
            <Button
              type="text"
              size="small"
              icon={<Eye size={12} />}
              onClick={(e) => {
                e.stopPropagation();
                setSubagentDetailOpen(true);
              }}
              title="查看 ReAct 执行流程"
              style={{ color: '#6366f1', marginRight: 4 }}
            >
              详情
            </Button>
          )}
          {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </div>
      </div>

      {isExpanded && (
        <div className={`tool-card-body ${compact ? 'compact' : ''}`}>
          {assistantContent && toolIndex === 0 && (
            <div className="tool-card-section">
              <div className="tool-card-section-title">Message</div>
              <div className="tool-card-assistant-content">
                {renderPlainContent(assistantContent)}
              </div>
            </div>
          )}

          {Object.keys(displayArgs).length > 0 && (
            <div className="tool-card-section">
              <div className="tool-card-section-header">
                <div className="tool-card-section-title">
                  Parameters
                  {status === 'streaming' && (
                    <span className="streaming-indicator">...</span>
                  )}
                </div>
                {argsPreview.needsTruncate && (
                  <Button
                    type="text"
                    size="small"
                    icon={<Maximize2 size={12} />}
                    onClick={(e) => {
                      e.stopPropagation();
                      setModal({ title: 'Parameters', content: argsString });
                    }}
                    title="View full parameters"
                  />
                )}
              </div>
              {argsPreview.needsTruncate ? (
                <>
                  <pre className="tool-card-code tool-card-code-collapsed">{argsPreview.text}</pre>
                  <Button
                    type="link"
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      setModal({ title: 'Parameters', content: argsString });
                    }}
                  >
                    查看完整内容
                  </Button>
                </>
              ) : (
                <table className="tool-params-table">
                  <tbody>
                    {Object.entries(displayArgs).map(([key, value]) => (
                      <tr key={key}>
                        <td className="tool-param-key">{key}</td>
                        <td className="tool-param-value">
                          <code>
                            {typeof value === 'object'
                              ? JSON.stringify(value, null, 2)
                              : String(value)}
                          </code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          <div className="tool-card-section">
            <div className="tool-card-section-header">
              <div className="tool-card-section-title">Result</div>
              <div style={{ display: 'flex', gap: 4 }}>
                {hasSubagentDetail && (
                  <Button
                    type="text"
                    size="small"
                    icon={<Eye size={12} />}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSubagentDetailOpen(true);
                    }}
                    title="查看 ReAct 执行流程"
                    style={{ color: '#6366f1' }}
                  >
                    详情
                  </Button>
                )}
                {resultContent && (
                  <Button
                    type="text"
                    size="small"
                    icon={<Copy size={12} />}
                    onClick={(e) => {
                      e.stopPropagation();
                      navigator.clipboard.writeText(resultContent);
                    }}
                    title="Copy result"
                  />
                )}
              </div>
            </div>
            {error ? (
              <div className="tool-card-error">
                <XCircle size={14} />
                <span>{error}</span>
              </div>
            ) : resultContent ? (
              <>
                {resultPreview.needsTruncate ? (
                  <>
                    <pre className="tool-card-code tool-card-code-collapsed">{resultPreview.text}</pre>
                    <Button
                      type="link"
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        setModal({ title: 'Result', content: resultContent });
                      }}
                    >
                      查看完整内容
                    </Button>
                  </>
                ) : (
                  <pre className="tool-card-code">{resultContent}</pre>
                )}
              </>
            ) : (
              <div className="tool-card-pending">
                <Loader2 size={14} className="spin" />
                <span>{getStatusText()}...</span>
              </div>
            )}
          </div>
        </div>
      )}

      <ViewModal
        title={modal?.title}
        content={modal?.content}
        onClose={() => setModal(null)}
      />

      <SubagentDetailModal
        open={subagentDetailOpen}
        onClose={() => setSubagentDetailOpen(false)}
        result={subagentResult}
      />
    </div>
  );
}

export default ToolCard;
