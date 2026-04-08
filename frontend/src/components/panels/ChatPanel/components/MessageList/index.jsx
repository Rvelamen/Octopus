import React, { useMemo, useState, useEffect, useRef } from 'react';
import { MessageSquare } from 'lucide-react';
import MessageItem from './MessageItem';
import IterationFold from './IterationFold';
import CompressionSummary from './CompressionSummary';
import octopusAvatar from '../../../../../assets/images/octopus.png';
import './MessageList.css';

function isToolResultMessage(msg) {
  const id = msg.metadata?.tool_call_id || msg.tool_call_id;
  return (
    !!id &&
    (msg.role === 'tool' || msg.message_type === 'tool_result')
  );
}

function buildToolRow(tc, toolResults) {
  const callId = tc?.id;
  const result = toolResults.get(callId);
  return {
    type: 'tool',
    toolCallId: callId,
    toolName: tc?.function?.name,
    args: tc?.function?.arguments || '{}',
    result: result?.content,
    status: result ? 'completed' : 'pending',
    error: undefined,
  };
}

/** 单条用户消息之后、下一条用户消息之前的整段 agent 过程 → 一个折叠，无 Iteration 概念 */
function buildDisplayList(messages) {
  const toolResults = new Map();
  messages.forEach((msg) => {
    if (isToolResultMessage(msg)) {
      const callId = msg.metadata?.tool_call_id || msg.tool_call_id;
      toolResults.set(callId, msg);
    }
  });

  const out = [];
  let pendingSegments = [];
  let thoughtKeySeed = 0;
  let lastAssistantUsage = null;

  const flushThought = (usage = lastAssistantUsage) => {
    if (pendingSegments.length === 0) return;
    thoughtKeySeed += 1;
    out.push({
      type: 'thought_fold',
      key: `thought-${thoughtKeySeed}`,
      segments: pendingSegments,
      status: 'completed',
      usage: usage,
    });
    pendingSegments = [];
    lastAssistantUsage = null; // Reset after flushing
  };

  for (let i = 0; i < messages.length; i += 1) {
    const msg = messages[i];

    if (msg.metadata?.is_summary || msg.metadata?.message_type === 'context_summary') {
      flushThought();
      out.push({
        type: 'compression_summary',
        message: msg,
        compressionInfo: msg.metadata?.compression_info || {},
      });
      continue;
    }

    if (isToolResultMessage(msg)) {
      continue;
    }

    // Track usage from assistant messages
    if (msg.role === 'assistant' && msg.metadata?.usage) {
      lastAssistantUsage = msg.metadata.usage;
    }

    const toolCalls = msg.metadata?.tool_calls || msg.tool_calls;
    const isAssistantWithTools =
      msg.role === 'assistant' && toolCalls && toolCalls.length > 0;

    if (isAssistantWithTools) {
      const text = (msg.content || '').trim();
      if (text) {
        pendingSegments.push({ type: 'reasoning', text });
      }
      toolCalls.forEach((tc) => {
        pendingSegments.push(buildToolRow(tc, toolResults));
      });
      continue;
    }

    // For regular assistant messages without tools, flush pending thought
    if (msg.role === 'assistant') {
      // This is a final assistant message without tool calls
      // It should be displayed as a normal message, but we can include usage
      flushThought();
      out.push({
        type: 'normal',
        message: msg,
        usage: msg.metadata?.usage || lastAssistantUsage,
      });
      lastAssistantUsage = null;
      continue;
    }

    flushThought();

    out.push({
      type: 'normal',
      message: msg,
      usage: null,
    });
  }

  flushThought();
  return out;
}

function MessageList({
  messages,
  streamingContent,
  toolCalls,
  toolCallAssistantContents,
  messageTtsMap,
  selectedInstance,
  currentChatInstanceId,
  onImageClick,
  renderMessageContent,
  renderPlainContent,
  lastElapsedMs,
  lastTokenUsage,
}) {
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const displayList = useMemo(() => buildDisplayList(messages), [messages]);

  const isStreaming = streamingContent && streamingContent.length > 0;
  const hasActiveToolCalls =
    toolCalls &&
    toolCalls.length > 0 &&
    selectedInstance?.id === currentChatInstanceId;

  /** 实时计时：只要组件挂载就一直运行，stop 时保留最终值 */
  const [totalMs, setTotalMs] = useState(0);
  const timerStartRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    // 每次从无到有时重置起点（流式开始时）
    if (hasActiveToolCalls && timerStartRef.current === null) {
      timerStartRef.current = Date.now();
      setTotalMs(0);
    }

    if (hasActiveToolCalls && rafRef.current === null) {
      const tick = () => {
        setTotalMs(Date.now() - timerStartRef.current);
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } else if (!hasActiveToolCalls) {
      // 流结束后停止 rAF，但保留 totalMs 的最终值（0ms 在此不会显示）
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    }
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [hasActiveToolCalls]);

  /** 进行中：整段合并为一个折叠，按 iteration 顺序交错「推理 + 工具」 */
  const liveThought = useMemo(() => {
    // 如果已完成消息里已有折叠（fetchInstanceMessages 已返回完整数据），不再显示 liveThought
    if (hasActiveToolCalls) {
      const hasCompletedFolds = displayList.some((item) => item.type === 'thought_fold');
      if (hasCompletedFolds) return null;
    } else {
      return null;
    }

    const iterKeys = [
      ...new Set(toolCalls.map((tc) => tc.iteration || 1)),
    ].sort((a, b) => a - b);

    const segments = [];
    iterKeys.forEach((iter) => {
      const text = toolCallAssistantContents?.[iter];
      if (text && String(text).trim()) {
        segments.push({ type: 'reasoning', text: String(text).trim() });
      }
      toolCalls
        .filter((tc) => (tc.iteration || 1) === iter)
        .forEach((tc) => {
          segments.push({
            type: 'tool',
            toolCallId: `live-${tc.id}`,
            toolName: tc.tool,
            args: tc.args,
            partialArgs: tc.partialArgs,
            result: tc.result,
            status: tc.status,
            error: tc.error,
          });
        });
    });

    const anyActive = toolCalls.some(
      (tc) =>
        tc.status &&
        tc.status !== 'completed' &&
        tc.status !== 'error'
    );
    return {
      segments,
      status: anyActive ? 'active' : 'completed',
    };
  }, [toolCalls, toolCallAssistantContents, hasActiveToolCalls, displayList]);

  return (
    <div className="messages-list">
      {displayList.map((item, idx) => {
        if (item.type === 'compression_summary') {
          return (
            <CompressionSummary
              key={item.message.id || idx}
              message={item.message}
              compressionInfo={item.compressionInfo}
              formatTime={formatTime}
              renderMessageContent={renderMessageContent}
            />
          );
        }
        if (item.type === 'thought_fold') {
          return (
            <IterationFold
              key={item.key}
              status={item.status}
              segments={item.segments}
              totalMs={lastElapsedMs}
              tokenUsage={item.usage}
            />
          );
        }
        const msg = item.message;
        const msgTts = messageTtsMap[msg.id];
        return (
          <MessageItem
            key={msg.id || idx}
            message={msg}
            ttsAudio={msgTts}
            onImageClick={onImageClick}
            renderMessageContent={renderMessageContent}
            usage={item.usage}
          />
        );
      })}

      {liveThought && liveThought.segments.length > 0 && (
        <IterationFold
          key="active-thought"
          status={liveThought.status}
          segments={liveThought.segments}
          totalMs={totalMs}
          isExpanded
        />
      )}

      {streamingContent && selectedInstance?.id === currentChatInstanceId && (
        <div className="message-row message-row-assistant streaming">
          <div className="message-bubble message-bubble-assistant">
            <div className="message-bubble-header">
              <div className="message-bubble-avatar">
                <img
                  src={octopusAvatar}
                  className="avatar-assistant-img"
                  alt="Octopus"
                />
              </div>
              <div className="message-bubble-meta">
                <span className="message-bubble-author">Octopus</span>
                <span className="message-bubble-time streaming-indicator">
                  <span className="blink">streaming</span>
                </span>
              </div>
            </div>
            <div className="message-bubble-content">
              {renderMessageContent(streamingContent)}
              <span className="cursor-blink">_</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MessageList;
