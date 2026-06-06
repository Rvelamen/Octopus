import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Bot, X, Plus, Send, Loader2, BookOpen, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import './LibraryChatDrawer.css';

const LibraryChatDrawer = ({
  sessions,
  currentSessionId,
  setCurrentSessionId,
  messages,
  loading,
  streamingContent,
  onSend,
  onNewSession,
  onDeleteSession,
  scopeLabel,
  width,
  onResizeStart,
  title = 'Library Chat',
}) => {
  const [input, setInput] = useState('');
  const [showSessions, setShowSessions] = useState(false);
  const [copiedMsgId, setCopiedMsgId] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Focus input when opened
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = useCallback(() => {
    if (!input.trim() || loading) return;
    onSend({ content: input.trim() });
    setInput('');
  }, [input, loading, onSend]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopyMessage = async (msgId, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMsgId(msgId);
      setTimeout(() => setCopiedMsgId(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const currentSession = sessions.find((s) => s.id === currentSessionId);

  // Only the last assistant message gets a copy button
  const lastAssistantMsgId = messages.reduce((lastId, m) => {
    if (m.role === 'assistant' && m.content?.trim()) return m.id;
    return lastId;
  }, null);

  return (
    <div className="libchat-drawer" style={{ width, minWidth: width }}>
      {/* Header */}
      <div className="libchat-header">
        <div className="libchat-title">
          <div className="libchat-title-icon">
            <Bot size={15} />
          </div>
          <span>{title}</span>
          {scopeLabel && (
            <span className="libchat-scope-badge" title={scopeLabel}>
              {scopeLabel}
            </span>
          )}
        </div>
        <div className="libchat-header-actions">
          <button
            className="libchat-header-btn"
            onClick={() => onNewSession()}
            title="New session"
          >
            <Plus size={14} />
          </button>
        </div>
      </div>

      {/* Sessions toggle */}
      {sessions.length > 0 && (
        <div
          className="libchat-session-toggle"
          onClick={() => setShowSessions((s) => !s)}
        >
          <span className={`libchat-session-toggle-arrow ${showSessions ? 'open' : ''}`}>
            ▸
          </span>
          <span>{sessions.length} session{sessions.length > 1 ? 's' : ''}</span>
        </div>
      )}

      {/* Sessions list */}
      {showSessions && (
        <div className="libchat-sessions">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`libchat-session ${s.id === currentSessionId ? 'libchat-session-active' : ''}`}
              onClick={() => {
                setCurrentSessionId(s.id);
                setShowSessions(false);
              }}
            >
              <span className="libchat-session-title">
                {s.title || `Session ${s.id}`}
              </span>
              <button
                className="libchat-session-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(s.id);
                }}
              >
                <X size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="libchat-messages">
        {messages.length === 0 && !loading && (
          <div className="libchat-empty">
            <BookOpen size={32} />
            <div>Ask me anything about your library notes</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Scope: {scopeLabel || 'All items'}
            </div>
          </div>
        )}

        {messages.map((msg) => {
            // Skip empty assistant messages (they only carry tool_calls in the backend)
            if (msg.role === 'assistant' && !msg.content?.trim()) {
              return null;
            }
            if (msg.role === 'tool') {
              const isRunning = msg.metadata?.status === 'running';
              return (
                <div key={msg.id} className="libchat-msg">
                  <details className="libchat-tool-card" open={isRunning}>
                    <summary className="libchat-tool-header">
                      <span className="libchat-tool-name">
                        <span className="libchat-tool-icon">🔧</span>
                        {msg.metadata?.tool || 'Tool'}
                      </span>
                      <span className={`libchat-tool-status libchat-tool-status-${isRunning ? 'running' : 'done'}`}>
                        {isRunning ? (
                          <>
                            <Loader2 size={11} className="libchat-spinner" />
                            Running
                          </>
                        ) : (
                          <>
                            <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                              <circle cx="5.5" cy="5.5" r="5.5" fill="currentColor" opacity="0.15"/>
                              <path d="M3 5.5L4.75 7.5L8 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                            Done
                          </>
                        )}
                      </span>
                    </summary>
                    <div className="libchat-tool-body">
                      {msg.metadata?.args && (
                        <details className="libchat-tool-details" open>
                          <summary>Arguments</summary>
                          <pre className="libchat-tool-code">
                            {JSON.stringify(msg.metadata.args, null, 2)}
                          </pre>
                        </details>
                      )}
                      {(msg.metadata?.result || msg.content) && !isRunning && (
                        <details className="libchat-tool-details" open>
                          <summary>Result</summary>
                          <pre className="libchat-tool-code">
                            {typeof (msg.metadata?.result || msg.content) === 'string'
                              ? (msg.metadata?.result || msg.content)
                              : JSON.stringify(msg.metadata?.result || msg.content, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  </details>
                </div>
              );
            }

            const isUser = msg.role === 'user';
            const canCopy = !isUser && msg.content?.trim() && msg.id === lastAssistantMsgId;
            return (
            <div key={msg.id} className={`libchat-msg libchat-msg-${msg.role}`}>
              <div className="libchat-msg-bubble">
                {msg.role === 'assistant' && (
                  <div className="libchat-msg-avatar">
                    <Bot size={14} />
                  </div>
                )}
                <div className="libchat-msg-content">
                  {isUser ? (
                    msg.content
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>{msg.content}</ReactMarkdown>
                  )}
                  {canCopy && (
                    <div className="libchat-msg-actions">
                      <button
                        type="button"
                        className="libchat-msg-copy-btn"
                        onClick={() => handleCopyMessage(msg.id, msg.content)}
                        title="复制内容"
                      >
                        {copiedMsgId === msg.id ? (
                          <>
                            <Check size={12} />
                            <span>已复制</span>
                          </>
                        ) : (
                          <>
                            <Copy size={12} />
                            <span>复制</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {streamingContent && (
          <div className="libchat-msg libchat-msg-assistant">
            <div className="libchat-msg-bubble">
              <div className="libchat-msg-avatar">
                <Bot size={12} />
              </div>
              <div className="libchat-msg-content">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>{streamingContent}</ReactMarkdown>
                <span className="libchat-streaming-cursor" />
              </div>
            </div>
          </div>
        )}

        {loading && !streamingContent && messages[messages.length - 1]?.role === 'user' && (
          <div className="libchat-msg libchat-msg-assistant">
            <div className="libchat-msg-bubble">
              <div className="libchat-msg-avatar">
                <Bot size={14} />
              </div>
              <div className="libchat-msg-content">
                <span className="libchat-typing">
                  <span /><span /><span />
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="libchat-input-wrap">
        <textarea
          ref={inputRef}
          className="libchat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your library notes..."
          rows={1}
          onInput={(e) => {
            e.target.style.height = 'auto';
            e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
          }}
        />
        <button
          className="libchat-send"
          onClick={handleSend}
          disabled={!input.trim() || loading}
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
};

export default LibraryChatDrawer;
