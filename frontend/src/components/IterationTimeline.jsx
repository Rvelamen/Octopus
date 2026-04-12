import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Clock, CheckCircle, Loader2 } from 'lucide-react';

/**
 * 迭代时间线组件
 * 显示 Agent 执行的迭代历史
 */
function IterationTimeline({ iterations }) {
  const [expandedIterations, setExpandedIterations] = useState(new Set());

  if (!iterations || iterations.length === 0) {
    return null;
  }

  const toggleExpand = (iterationNum) => {
    const newExpanded = new Set(expandedIterations);
    if (newExpanded.has(iterationNum)) {
      newExpanded.delete(iterationNum);
    } else {
      newExpanded.add(iterationNum);
    }
    setExpandedIterations(newExpanded);
  };

  const formatElapsed = (ms) => {
    if (!ms || ms === 0) return '...';
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <div className="iteration-timeline">
      <div className="iteration-timeline-header">
        <h3 className="iteration-timeline-title">
          Iteration History ({iterations.length} iterations)
        </h3>
      </div>

      <div className="iteration-timeline-list">
        {iterations.map((iter) => {
          const isExpanded = expandedIterations.has(iter.iteration);
          const isRunning = iter.status === 'running';
          const isCompleted = iter.status === 'completed';

          return (
            <div
              key={iter.iteration}
              className={`iteration-item ${isRunning ? 'running' : isCompleted ? 'completed' : ''}`}
            >
              <div
                className="iteration-item-header"
                onClick={() => toggleExpand(iter.iteration)}
              >
                <div className="iteration-item-header-left">
                  <div className={`iteration-status-indicator ${isRunning ? 'running' : 'completed'}`}>
                    {isRunning ? (
                      <Loader2 size={14} className="spin" />
                    ) : (
                      <CheckCircle size={14} />
                    )}
                  </div>
                  <span className="iteration-number">
                    Iteration {iter.iteration}/{iter.max_iterations}
                  </span>
                  {iter.elapsed_ms > 0 && (
                    <span className="iteration-elapsed" title="Elapsed time">
                      <Clock size={12} />
                      {formatElapsed(iter.elapsed_ms)}
                    </span>
                  )}
                </div>
                <div className="iteration-item-header-right">
                  {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>
              </div>

              {isExpanded && (
                <div className="iteration-item-content">
                  <div className="iteration-item-details">
                    <div className="iteration-detail-row">
                      <span className="iteration-detail-label">Status:</span>
                      <span className={`iteration-detail-value ${isRunning ? 'running' : 'completed'}`}>
                        {isRunning ? 'Running...' : 'Completed'}
                      </span>
                    </div>
                    {iter.elapsed_ms > 0 && (
                      <div className="iteration-detail-row">
                        <span className="iteration-detail-label">Duration:</span>
                        <span className="iteration-detail-value">
                          {iter.elapsed_ms.toFixed(1)}ms ({formatElapsed(iter.elapsed_ms)})
                        </span>
                      </div>
                    )}
                    {iter.token_usage && (
                      <>
                        <div className="iteration-detail-row">
                          <span className="iteration-detail-label">Tokens:</span>
                          <span className="iteration-detail-value">
                            {iter.token_usage.total_tokens?.toLocaleString()} total
                          </span>
                        </div>
                        <div className="iteration-detail-row iteration-detail-sub">
                          <span className="iteration-detail-label">Prompt:</span>
                          <span className="iteration-detail-value">
                            {iter.token_usage.prompt_tokens?.toLocaleString()}
                          </span>
                        </div>
                        <div className="iteration-detail-row iteration-detail-sub">
                          <span className="iteration-detail-label">Completion:</span>
                          <span className="iteration-detail-value">
                            {iter.token_usage.completion_tokens?.toLocaleString()}
                          </span>
                        </div>
                        <div className="iteration-detail-row iteration-detail-sub">
                          <span className="iteration-detail-label">Model:</span>
                          <span className="iteration-detail-value iteration-detail-model">
                            {iter.token_usage.model}
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default IterationTimeline;
