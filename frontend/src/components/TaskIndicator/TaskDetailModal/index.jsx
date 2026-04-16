import React, { useState, useEffect } from 'react';
import { X, Bot, Clock, Coins, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import IterationFold from '@components/MessageList/IterationFold.jsx';

export default function TaskDetailModal({ task, visible, onClose, sendWSMessage }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (visible && task?.id) {
      loadTaskDetail(true);
    }
  }, [visible, task?.id]);

  useEffect(() => {
    if (!visible || !task?.id) return;
    if (task.status !== 'running' && task.status !== 'queued') return;

    const interval = setInterval(() => {
      loadTaskDetail(false);
    }, 2000);

    return () => clearInterval(interval);
  }, [visible, task?.id, task?.status]);

  const loadTaskDetail = async (showLoading = true) => {
    if (!task?.id) return;
    if (showLoading) setLoading(true);
    try {
      const response = await sendWSMessage('knowledge_distill_detail', { task_id: task.id });
      // 后端返回的数据结构是 { task: {...}, result: { iterations, token_usage, duration, ... } }
      const result = response.data?.result;
      setDetail(result || null);
    } catch (err) {
      console.error('Failed to load task detail:', err);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  if (!visible || !task) return null;

  const { status, sourceFile, template, progress, message } = task;

  const formatDuration = (seconds) => {
    if (!seconds) return '0s';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const segments = [];
  if (detail?.iterations) {
    for (const iter of detail.iterations) {
      if (iter.reasoning) {
        segments.push({ type: 'reasoning', text: iter.reasoning });
      }
      for (const tool of iter.tools || []) {
        segments.push({
          type: 'tool',
          toolCallId: tool.toolCallId || `tc-${tool.toolName}-${Math.random().toString(36).slice(2, 6)}`,
          toolName: tool.toolName,
          args: typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args || {}),
          result: tool.result,
          status: tool.status || 'completed',
          error: tool.status === 'error' ? tool.result : undefined,
        });
      }
    }
  }

  const totalTokens = (detail?.token_usage?.prompt_tokens || 0) + (detail?.token_usage?.completion_tokens || 0);

  return (
    <div
      className="dialog-overlay"
      onClick={onClose}
      onMouseDown={(e) => e.stopPropagation()}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        className="dialog-content"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '80vw',
          maxWidth: 900,
          maxHeight: '80vh',
          background: 'var(--surface)',
          borderRadius: 8,
          border: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Bot
              size={20}
              style={{
                color:
                  status === 'completed'
                    ? 'var(--accent-green)'
                    : status === 'running'
                    ? 'var(--accent)'
                    : status === 'failed'
                    ? 'var(--accent-red)'
                    : 'var(--text-2)',
              }}
            />
            <div>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Distill Task Detail</h3>
              <div style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 12 }}>
                <span>{sourceFile?.split('/').pop() || 'Unknown'}</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span
                    style={{
                      fontWeight: 600,
                      color:
                        status === 'completed'
                          ? 'var(--accent-green)'
                          : status === 'running'
                          ? 'var(--accent)'
                          : status === 'failed'
                          ? 'var(--accent-red)'
                          : 'var(--text-2)',
                    }}
                  >
                    {status}
                  </span>
                  <span>·</span>
                  <span>{template || 'custom'}</span>
                  {detail?.duration > 0 && (
                    <>
                      <span>·</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Clock size={10} />
                        {formatDuration(detail.duration)}
                      </span>
                    </>
                  )}
                  {totalTokens > 0 && (
                    <>
                      <span>·</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Coins size={10} />
                        {totalTokens.toLocaleString()}
                      </span>
                    </>
                  )}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-2)',
              cursor: 'pointer',
              padding: 4,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={20} />
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Loader2 size={32} style={{ animation: 'spin 1s linear infinite' }} />
              <p style={{ marginTop: 16, color: 'var(--text-2)' }}>Loading...</p>
            </div>
          ) : (
            <>
              {(status === 'running' || status === 'queued') && (
                <div style={{ marginBottom: 20 }}>
                  <div
                    style={{
                      width: '100%',
                      height: 4,
                      background: 'var(--border)',
                      borderRadius: 2,
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${progress * 100}%`,
                        height: '100%',
                        background: 'var(--accent)',
                        transition: 'width 0.3s ease',
                      }}
                    />
                  </div>
                  {message && (
                    <div style={{ margin: '8px 0 0', fontSize: 11, color: 'var(--text-2)' }}>
                      <ReactMarkdown>{message}</ReactMarkdown>
                    </div>
                  )}
                </div>
              )}

              {segments.length > 0 && (
                <div>
                  <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>ReAct Flow ({segments.filter(s => s.type === 'tool').length} tool calls)</h4>
                  <IterationFold
                    status={status === 'completed' ? 'completed' : status === 'failed' ? 'error' : 'running'}
                    segments={segments}
                    totalMs={(detail?.duration || 0) * 1000}
                    tokenUsage={detail?.token_usage}
                  />
                </div>
              )}

              {/* 最终生成的 Markdown 内容 */}
              {detail?.summary && (
                <div style={{ marginTop: 20 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Generated Content</h4>
                  <div
                    style={{
                      padding: 16,
                      background: 'var(--surface-2)',
                      borderRadius: 8,
                      border: '1px solid var(--border)',
                      fontSize: 13,
                      lineHeight: 1.6,
                      maxHeight: '40vh',
                      overflow: 'auto',
                    }}
                  >
                    <ReactMarkdown>{detail.summary}</ReactMarkdown>
                  </div>
                </div>
              )}

              {status === 'completed' && detail?.output_path && (
                <div style={{ marginTop: 20, textAlign: 'center' }}>
                  <button
                    className="pixel-button"
                    onClick={() => {
                      onClose();
                      // Navigate to the output file
                      window.dispatchEvent(new CustomEvent('knowledge-open-file', {
                        detail: { path: detail.output_path }
                      }));
                    }}
                  >
                    Open Output File
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}