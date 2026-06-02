import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Send, Bot, User, Loader2, Wand2, Sparkles, X, ChevronRight, Play, LayoutTemplate, CheckCircle2, Terminal } from 'lucide-react';
import { useWorkflowDesignChat } from '../../hooks/useWorkflowDesignChat';
import { useWebSocket } from '../../../contexts/WebSocketContext';
import { useWorkflowStore } from '../../hooks/useWorkflowStore';

/* ── Inline keyframes for blink (not available in Workflow page scope) ── */
const BlinkStyle = () => (
  <style>{`
    @keyframes wf-blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }
  `}</style>
);

/* ── Tool summary formatter ── */
const TOOL_LABELS = {
  add_node: '添加节点',
  connect_nodes: '连接节点',
  set_variable: '设置变量',
  remove_node: '删除节点',
  auto_layout: '自动布局',
  validate_workflow: '验证工作流',
  run_test: '运行测试',
  get_variable_context: '获取变量',
};

function formatToolSummary(tool, args, result) {
  const label = TOOL_LABELS[tool] || tool;
  switch (tool) {
    case 'add_node':
      return `${label}「${args.name || args.node_type || ''}」`;
    case 'connect_nodes':
      return `${label}：${args.source || ''} → ${args.target || ''}`;
    case 'set_variable':
      return `${label}：${args.node_id || ''}.${args.input_key || ''}`;
    case 'remove_node':
      return `${label}：${args.node_id || ''}`;
    case 'auto_layout':
      return result?.node_count ? `${label}（${result.node_count} 个节点）` : label;
    case 'validate_workflow':
      if (result?.valid) return `${label} ✅ 通过`;
      if (result?.errors?.length) return `${label} ❌ ${result.errors.length} 个错误`;
      return label;
    case 'run_test':
      return result?.status ? `${label} — ${result.status}` : label;
    default:
      return label;
  }
}

/* ── Cursor blink for streaming ── */
const CursorBlink = () => (
  <span
    style={{
      display: 'inline-block',
      width: '2px',
      height: '16px',
      background: '#8b5cf6',
      marginLeft: '3px',
      verticalAlign: 'middle',
      animation: 'wf-blink 1s step-end infinite',
    }}
  />
);

/* ── ToolCallCard (embedded in assistant message) ── */
const ToolCallCard = ({ tool, args, result, status, index, total }) => {
  const [expanded, setExpanded] = useState(false);
  const isRunning = status === 'running';
  const summary = formatToolSummary(tool, args, result);

  return (
    <div
      style={{
        borderRadius: '8px',
        background: isRunning ? '#fefce8' : '#f0fdf4',
        border: `1px solid ${isRunning ? '#fde047' : '#86efac'}`,
        overflow: 'hidden',
        transition: 'all 0.3s ease',
        opacity: isRunning ? 0.9 : 1,
      }}
    >
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 10px',
          cursor: 'pointer',
          fontSize: '11px',
        }}
      >
        {isRunning ? (
          <Loader2 size={12} style={{ animation: 'spin 1s linear infinite', color: '#ca8a04', flexShrink: 0 }} />
        ) : (
          <CheckCircle2 size={12} color="#16a34a" style={{ flexShrink: 0 }} />
        )}
        {total > 1 && (
          <span
            style={{
              fontSize: '10px',
              fontWeight: 700,
              color: isRunning ? '#ca8a04' : '#16a34a',
              background: isRunning ? '#fef9c3' : '#dcfce7',
              padding: '1px 5px',
              borderRadius: '4px',
              flexShrink: 0,
            }}
          >
            {index}/{total}
          </span>
        )}
        <span style={{ fontWeight: 500, color: isRunning ? '#854d0e' : '#166534', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {summary}
        </span>
        <ChevronRight
          size={12}
          style={{
            transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
            color: '#6b7280',
            flexShrink: 0,
          }}
        />
      </div>
      {expanded && (
        <div style={{ padding: '0 10px 10px', fontSize: '11px', fontFamily: 'monospace' }}>
          <div style={{ color: '#4b5563', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Terminal size={10} />
            <strong>参数</strong>
          </div>
          <pre
            style={{
              background: 'rgba(0,0,0,0.03)',
              padding: '6px 8px',
              borderRadius: '4px',
              overflow: 'auto',
              maxHeight: '100px',
              margin: 0,
              fontSize: '10px',
            }}
          >
            {JSON.stringify(args, null, 2)}
          </pre>
          {result !== undefined && result !== null && (
            <>
              <div style={{ color: '#4b5563', marginTop: '8px', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Terminal size={10} />
                <strong>结果</strong>
              </div>
              <pre
                style={{
                  background: 'rgba(0,0,0,0.03)',
                  padding: '6px 8px',
                  borderRadius: '4px',
                  overflow: 'auto',
                  maxHeight: '100px',
                  margin: 0,
                  fontSize: '10px',
                }}
              >
                {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  );
};

/* ── UserMessage ── */
const UserMessage = ({ content }) => (
  <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexDirection: 'row-reverse' }}>
    <div
      style={{
        width: 28,
        height: 28,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        background: '#3b82f6',
      }}
    >
      <User size={14} color="white" />
    </div>
    <div
      style={{
        maxWidth: 'calc(100% - 44px)',
        padding: '10px 14px',
        borderRadius: '14px 14px 2px 14px',
        background: '#3b82f6',
        color: 'white',
        fontSize: '13px',
        lineHeight: 1.5,
        wordBreak: 'break-word',
      }}
    >
      {content}
    </div>
  </div>
);

/* ── AssistantMessageGroup (text + embedded tool calls) ── */
const AssistantMessageGroup = ({ message, tools, isStreaming }) => {
  const hasTools = tools && tools.length > 0;

  return (
    <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
      {/* AI Avatar */}
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          background: '#8b5cf6',
        }}
      >
        <Bot size={14} color="white" />
      </div>

      {/* Content column */}
      <div style={{ maxWidth: 'calc(100% - 44px)', display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
        {/* Text bubble */}
        {message.content && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '14px 14px 14px 2px',
              background: '#f3f4f6',
              color: '#1f2937',
              fontSize: '13px',
              lineHeight: 1.5,
              wordBreak: 'break-word',
            }}
          >
            {message.content}
            {isStreaming && <CursorBlink />}
          </div>
        )}

        {/* Embedded tool calls */}
        {hasTools && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingLeft: '2px' }}>
            {tools.map((toolMsg, idx) => (
              <ToolCallCard
                key={toolMsg.id}
                tool={toolMsg.metadata?.tool}
                args={toolMsg.metadata?.args}
                result={toolMsg.metadata?.result}
                status={toolMsg.metadata?.status}
                index={idx + 1}
                total={tools.length}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

/* ── Group messages: assistant + trailing tool messages ──
   Also collects orphaned tool messages (those appearing before their
   corresponding assistant message in the stream) as pendingTools. ── */
function groupMessages(messages) {
  const groups = [];
  let pendingTools = [];
  let i = 0;
  while (i < messages.length) {
    const msg = messages[i];
    if (msg.role === 'user') {
      groups.push({ type: 'user', message: msg });
      i++;
    } else if (msg.role === 'tool') {
      pendingTools.push(msg);
      i++;
    } else if (msg.role === 'assistant') {
      const group = {
        type: 'assistant',
        message: msg,
        tools: [...pendingTools],
      };
      pendingTools = [];
      i++;
      while (i < messages.length && messages[i].role === 'tool') {
        group.tools.push(messages[i]);
        i++;
      }
      groups.push(group);
    } else {
      i++;
    }
  }
  return { groups, pendingTools };
}

/* ── Main Panel ── */
export default function DesignChatPanel({ workflowId, versionId, isOpen, onToggle, onRefreshCanvas }) {
  const { sendMessage, subscribe, unsubscribe } = useWebSocket();

  const {
    messages,
    loading,
    streamingContent,
    lastToolResult,
    sendChat,
    clearSession,
  } = useWorkflowDesignChat({ sendMessage, subscribe, unsubscribe, workflowId });

  // ── Real-time canvas refresh ──
  // Refresh on EVERY tool result (not debounced across tools) so the user sees
  // each add_node / connect / update / layout happen in real time.
  const isRefreshingRef = useRef(false);
  const pendingRefreshRef = useRef(false);

  const doRefresh = useCallback(async () => {
    if (isRefreshingRef.current) {
      pendingRefreshRef.current = true;
      return;
    }
    isRefreshingRef.current = true;
    try {
      if (onRefreshCanvas) {
        await onRefreshCanvas(versionId);
      }
    } catch (e) {
      console.error('[DesignChatPanel] Refresh failed:', e);
    } finally {
      isRefreshingRef.current = false;
      if (pendingRefreshRef.current) {
        pendingRefreshRef.current = false;
        // flush any pending refresh that arrived while we were busy
        setTimeout(() => doRefresh(), 50);
      }
    }
  }, [onRefreshCanvas, versionId]);

  useEffect(() => {
    if (!lastToolResult?.timestamp) return;
    // Each tool result triggers its own refresh after a short delay
    const timer = setTimeout(() => doRefresh(), 50);
    return () => clearTimeout(timer);
  }, [lastToolResult?.timestamp, doRefresh]);

  // Fallback refresh when AI finishes responding
  const wasLoadingRef = useRef(false);
  useEffect(() => {
    if (wasLoadingRef.current && !loading) {
      const timer = setTimeout(() => doRefresh(), 200);
      return () => clearTimeout(timer);
    }
    wasLoadingRef.current = loading;
  }, [loading, doRefresh]);

  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleSend = useCallback(() => {
    if (!inputValue.trim() || loading) return;
    sendChat({ content: inputValue.trim() });
    setInputValue('');
  }, [inputValue, loading, sendChat]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const quickActions = [
    {
      label: '生成简单工作流',
      icon: Wand2,
      prompt: '帮我生成一个简单的智能客服工作流：用户输入问题，大模型回复，输出结果',
    },
    {
      label: '运行测试',
      icon: Play,
      prompt: '帮我测试一下当前工作流是否能正常运行',
    },
    {
      label: '自动布局',
      icon: LayoutTemplate,
      prompt: '帮我把当前工作流的节点重新排列整齐',
    },
  ];

  const { groups: messageGroups, pendingTools } = useMemo(() => groupMessages(messages), [messages]);

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        style={{
          position: 'absolute',
          left: 12,
          top: 70,
          zIndex: 20,
          width: 40,
          height: 40,
          borderRadius: '50%',
          border: '1px solid #e5e7eb',
          background: 'white',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          color: '#8b5cf6',
        }}
        title="AI 设计助手"
      >
        <Sparkles size={20} />
      </button>
    );
  }

  return (
    <>
      <BlinkStyle />
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 48,
          bottom: 0,
          width: 340,
          background: 'white',
          borderRight: '1px solid #e5e7eb',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 20,
          boxShadow: '2px 0 12px rgba(0,0,0,0.06)',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 16px',
            borderBottom: '1px solid #f3f4f6',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bot size={18} color="#8b5cf6" />
            <span style={{ fontSize: '14px', fontWeight: 600, color: '#1f2937' }}>
              AI 设计助手
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <button
              onClick={clearSession}
              title="清空对话"
              style={{
                padding: '4px 8px',
                borderRadius: '6px',
                border: 'none',
                background: 'transparent',
                color: '#9ca3af',
                fontSize: '11px',
                cursor: 'pointer',
              }}
            >
              清空
            </button>
            <button
              onClick={onToggle}
              title="关闭"
              style={{
                padding: '4px',
                borderRadius: '6px',
                border: 'none',
                background: 'transparent',
                color: '#9ca3af',
                cursor: 'pointer',
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {messages.length === 0 && !streamingContent && (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#9ca3af' }}>
              <Bot size={40} style={{ marginBottom: '12px', opacity: 0.5 }} />
              <p style={{ fontSize: '13px', marginBottom: '16px' }}>
                描述你想构建的工作流，AI 会帮你生成
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {quickActions.map((action) => (
                  <button
                    key={action.label}
                    onClick={() => sendChat({ content: action.prompt })}
                    disabled={loading}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 14px',
                      borderRadius: '10px',
                      border: '1px solid #e5e7eb',
                      background: 'white',
                      color: '#4b5563',
                      fontSize: '12px',
                      cursor: loading ? 'not-allowed' : 'pointer',
                      textAlign: 'left',
                      opacity: loading ? 0.5 : 1,
                    }}
                  >
                    <action.icon size={14} color="#8b5cf6" />
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Grouped messages */}
          {messageGroups.map((group) => {
            if (group.type === 'user') {
              return <UserMessage key={group.message.id} content={group.message.content} />;
            }
            return (
              <AssistantMessageGroup
                key={group.message.id}
                message={group.message}
                tools={group.tools}
                isStreaming={false}
              />
            );
          })}

          {/* Streaming: text + pending (orphan) tool calls */}
          {(streamingContent || pendingTools.length > 0) && (
            <AssistantMessageGroup
              message={{ role: 'assistant', content: streamingContent || '' }}
              tools={pendingTools}
              isStreaming={true}
            />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid #f3f4f6',
            background: '#fafafa',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-end',
              gap: '8px',
              background: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '12px',
              padding: '8px 12px',
            }}
          >
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="描述你想构建的工作流..."
              disabled={loading}
              rows={1}
              style={{
                flex: 1,
                border: 'none',
                outline: 'none',
                resize: 'none',
                fontSize: '13px',
                lineHeight: 1.5,
                background: 'transparent',
                maxHeight: '100px',
                minHeight: '20px',
                fontFamily: 'inherit',
              }}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || loading}
              style={{
                width: 32,
                height: 32,
                borderRadius: '8px',
                border: 'none',
                background: inputValue.trim() && !loading ? '#8b5cf6' : '#e5e7eb',
                color: inputValue.trim() && !loading ? 'white' : '#9ca3af',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: inputValue.trim() && !loading ? 'pointer' : 'not-allowed',
                flexShrink: 0,
              }}
            >
              {loading ? (
                <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <Send size={16} />
              )}
            </button>
          </div>
          <div style={{ fontSize: '10px', color: '#9ca3af', marginTop: '6px', textAlign: 'center' }}>
            AI 会自动创建节点、连线和绑定变量
          </div>
        </div>
      </div>
    </>
  );
}
