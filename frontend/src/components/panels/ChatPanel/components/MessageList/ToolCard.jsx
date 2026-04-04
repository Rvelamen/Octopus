import React, { useState } from 'react';
import { Wrench, ChevronUp, ChevronDown, Check, Loader2, Copy, Clock, XCircle, AlertCircle } from 'lucide-react';

function ToolCard({
  toolCallId,
  toolName,
  args,
  partialArgs,  // New: streaming arguments
  result,
  status,
  error,  // New: error message
  assistantContent,
  toolIndex = 0,
  totalTools = 1,
  renderMessageContent,
  isExpanded: isExpandedProp,
  onToggleExpand
}) {
  const [isExpandedInternal, setIsExpandedInternal] = useState(false);
  
  const isExpanded = isExpandedProp !== undefined ? isExpandedProp : isExpandedInternal;
  
  const handleToggle = () => {
    if (onToggleExpand) {
      onToggleExpand();
    } else {
      setIsExpandedInternal(!isExpandedInternal);
    }
  };

  const parsedArgs = typeof args === 'string' ? (() => {
    try {
      return JSON.parse(args);
    } catch {
      return {};
    }
  })() : (args || {});

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

  // Display arguments (prefer streaming arguments)
  const displayArgs = partialArgs || parsedArgs || {};

  return (
    <div className="tool-card">
      {assistantContent && toolIndex === 0 && (
        <div className="tool-card-assistant-content">
          {renderMessageContent(assistantContent)}
        </div>
      )}

      <div
        className={`tool-card-header ${status}`}
        onClick={handleToggle}
      >
        <div className="tool-card-header-left">
          <div className={`tool-status-indicator ${status}`}>
            {getStatusIcon()}
          </div>
          <Wrench size={14} className="tool-icon" />
          <span className="tool-card-name">{toolName || 'unknown'}</span>
          {totalTools > 1 && (
            <span className="tool-card-index">({toolIndex + 1}/{totalTools})</span>
          )}
          <span className="tool-status-text">{getStatusText()}</span>
        </div>
        <div className="tool-card-header-right">
          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>

      {isExpanded && (
        <div className="tool-card-body">
          {Object.keys(displayArgs).length > 0 && (
            <div className="tool-card-section">
              <div className="tool-card-section-title">
                Parameters
                {status === 'streaming' && (
                  <span className="streaming-indicator">...</span>
                )}
              </div>
              <table className="tool-params-table">
                <tbody>
                  {Object.entries(displayArgs).map(([key, value]) => (
                    <tr key={key}>
                      <td className="tool-param-key">{key}</td>
                      <td className="tool-param-value">
                        <code>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="tool-card-section">
            <div className="tool-card-section-header">
              <div className="tool-card-section-title">Result</div>
              {resultContent && (
                <button
                  className="tool-copy-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    navigator.clipboard.writeText(resultContent);
                  }}
                  title="Copy result"
                >
                  <Copy size={12} />
                </button>
              )}
            </div>
            {error ? (
              <div className="tool-card-error">
                <XCircle size={14} />
                <span>{error}</span>
              </div>
            ) : resultContent ? (
              <pre className="tool-card-code">{resultContent}</pre>
            ) : (
              <div className="tool-card-pending">
                <Loader2 size={14} className="spin" />
                <span>{getStatusText()}...</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ToolCard;
