import React from 'react';
import { Bot, Clock, Coins, Eye } from 'lucide-react';
import IterationFold from '../ChatPanel/components/MessageList/IterationFold';

export default function DistillTaskDetail({ result, sendWSMessage }) {
  if (!result) return null;

  const { status, label, summary, token_usage, duration, iterations } = result;
  const totalTokens = (token_usage?.prompt_tokens || 0) + (token_usage?.completion_tokens || 0);

  const segments = [];
  for (const iter of (iterations || [])) {
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

  const formatDuration = (s) => {
    if (!s || s === 0) return '0s';
    if (s < 60) return `${s.toFixed(1)}s`;
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    return `${mins}m ${secs}s`;
  };

  const formatTokens = (count) => {
    if (!count || count === 0) return '0';
    if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
    return count.toString();
  };

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
        paddingBottom: 10,
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Bot size={16} style={{ color: status === 'completed' ? 'var(--accent-green)' : 'var(--accent)' }} />
          <span style={{ fontSize: 13, fontWeight: 600 }}>{label}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--text-2)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Clock size={12} /> {formatDuration(duration)}
          </span>
          {totalTokens > 0 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Coins size={12} /> {formatTokens(totalTokens)} tokens
            </span>
          )}
        </div>
      </div>

      {summary && (
        <div style={{
          fontSize: 12,
          lineHeight: 1.6,
          color: 'var(--text)',
          marginBottom: 14,
          padding: 10,
          background: 'var(--surface-2)',
          borderRadius: 6,
          whiteSpace: 'pre-wrap',
        }}>
          {summary.split('\n').map((line, i) => {
            if (line.startsWith('**') && line.includes('**')) {
              const parts = line.split(/\*\*(.*?)\*\*/g);
              return (
                <p key={i} style={{ margin: '4px 0' }}>
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
            return <p key={i} style={{ margin: '4px 0' }}>{line}</p>;
          })}
        </div>
      )}

      {segments.length > 0 ? (
        <div>
          <h4 style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--text-2)' }}>
            ReAct Flow ({segments.filter(s => s.type === 'tool').length} tool calls)
          </h4>
          <IterationFold
            status={status === 'completed' ? 'completed' : 'error'}
            segments={segments}
            totalMs={duration * 1000}
            tokenUsage={token_usage}
          />
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: 16, color: 'var(--text-2)', fontSize: 12 }}>
          No execution details available
        </div>
      )}

      {status === 'completed' && result.output_path && (
        <div style={{ marginTop: 12, textAlign: 'center' }}>
          <button
            className="pixel-button"
            onClick={() => {
              sendWSMessage('knowledge_read', { path: result.output_path });
            }}
            style={{ fontSize: 12, padding: '6px 14px' }}
          >
            <Eye size={14} style={{ marginRight: 4 }} /> Open Output Note
          </button>
        </div>
      )}
    </div>
  );
}
