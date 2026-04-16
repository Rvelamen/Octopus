import React, { useMemo, useState, useEffect, useRef } from 'react';
import { MessageSquare } from 'lucide-react';
import MessageItem from './MessageItem.jsx';
import IterationFold from './IterationFold.jsx';
import CompressionSummary from './CompressionSummary.jsx';
import SubagentSyncFold from './SubagentSyncFold.jsx';
import octopusAvatar from '@assets/images/octopus.png';
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
  const result =
    toolResults.get(callId) ??
    (callId != null ? toolResults.get(String(callId)) : undefined);
  let status = result ? 'completed' : 'pending';
  if (
    result?.metadata?.cancelled_by_user ||
    (result?.content && String(result.content).includes('已取消（用户暂停）'))
  ) {
    status = 'cancelled';
  }
  return {
    type: 'tool',
    toolCallId: callId,
    toolName: tc?.function?.name,
    args: tc?.function?.arguments || '{}',
    result: result?.content,
    status,
    error: undefined,
  };
}

/** 单条用户消息之后、下一条用户消息之前的整段 agent 过程 → 一个折叠，无 Iteration 概念 */
function buildDisplayList(messages) {
  const toolResults = new Map();
  messages.forEach((msg) => {
    if (isToolResultMessage(msg)) {
      const callId = msg.metadata?.tool_call_id || msg.tool_call_id;
      if (callId != null) {
        toolResults.set(callId, msg);
        toolResults.set(String(callId), msg);
      }
    }
  });

  const out = [];
  let pendingSegments = [];
  let thoughtKeySeed = 0;
  let lastAssistantUsage = null;
  let lastElapsedMs = null;
  let pendingThoughtStoppedByUser = false;

  const flushThought = (usage = lastAssistantUsage, elapsed = lastElapsedMs) => {
    if (pendingSegments.length === 0) return;
    thoughtKeySeed += 1;
    out.push({
      type: 'thought_fold',
      key: `thought-${thoughtKeySeed}`,
      segments: pendingSegments,
      status: pendingThoughtStoppedByUser ? 'paused' : 'completed',
      usage: usage,
      elapsedMs: elapsed,
    });
    pendingSegments = [];
    lastAssistantUsage = null; // Reset after flushing
    lastElapsedMs = null;
    pendingThoughtStoppedByUser = false;
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

    // 检测同步 subagent 结果
    if (msg.role === 'tool' && msg.metadata?.tool_name === 'spawn') {
      try {
        const parsed = JSON.parse(msg.content || '{}');
        if (parsed.type === 'subagent_sync') {
          // subagent 的 token 不累计到主 agent 的 message usage 中，
          // 因为 subagent 的 iterations 不会出现在主上下文中
          flushThought();
          out.push({
            type: 'subagent_sync',
            message: msg,
            result: parsed,
          });
          continue;
        }
      } catch (e) {
        // 不是 JSON，按普通 tool result 处理
      }
    }

    if (isToolResultMessage(msg)) {
      continue;
    }

    // Track usage and elapsed time from assistant messages
    if (msg.role === 'assistant' && msg.metadata?.usage) {
      lastAssistantUsage = msg.metadata.usage;
    }
    if (msg.role === 'assistant' && msg.metadata?.elapsed_ms != null) {
      lastElapsedMs = msg.metadata.elapsed_ms;
    }

    const toolCalls = msg.metadata?.tool_calls || msg.tool_calls;
    const isAssistantWithTools =
      msg.role === 'assistant' && toolCalls && toolCalls.length > 0;

    if (isAssistantWithTools) {
      if (msg.metadata?.stopped_by_user) {
        pendingThoughtStoppedByUser = true;
      }
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
  isProcessing = false,
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
  liveTokenUsage,
  hasToolCallsInCurrentRun = false,
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
    const isAgentRunning = isProcessing && selectedInstance?.id === currentChatInstanceId;
    const hasStreaming = !!streamingContent && selectedInstance?.id === currentChatInstanceId;
    // 只有已出现过 tool call（或当前有活跃 tool call）时，才渲染 liveThought。
    // 普通对话（始终没有 tool call）保持为普通 message 输出。
    const shouldRenderLiveThought =
      hasActiveToolCalls || (isAgentRunning && hasToolCallsInCurrentRun) || (hasStreaming && hasToolCallsInCurrentRun);
    if (!shouldRenderLiveThought) {
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
            subagentCalls: tc.subagentCalls,
            subagentStreamingContent: tc.subagentStreamingContent,
          });
        });
    });

    // Follow-up / 多轮场景：toolCallAssistantContents 只有第一轮的推理内容，
    // 后续轮次的推理内容通过 streamingContent 实时追加，
    // 需从 toolCalls 反推当前是第几轮，再拼上 streamingContent
    const lastIter = iterKeys.length > 0 ? iterKeys[iterKeys.length - 1] : 1;
    const liveIter = lastIter + 1;
    const prevContent = toolCallAssistantContents?.[liveIter] || '';
    const hasStreamingForNewIter =
      !!streamingContent &&
      selectedInstance?.id === currentChatInstanceId &&
      !prevContent;
    if (hasStreamingForNewIter && String(streamingContent).trim()) {
      segments.push({ type: 'reasoning', text: String(streamingContent).trim() });
    }

    // 工具刚返回、下一轮 LLM 尚未开始时，所有 tc 可能已是 completed，但 agent 仍在跑
    const anyToolInFlight = toolCalls.some(
      (tc) =>
        tc.status &&
        tc.status !== 'completed' &&
        tc.status !== 'error'
    );
    const agentRunInProgress =
      isProcessing && selectedInstance?.id === currentChatInstanceId;
    const streamingThisTurn =
      !!streamingContent && selectedInstance?.id === currentChatInstanceId;
    const isThoughtRunning =
      anyToolInFlight || agentRunInProgress || streamingThisTurn;
    return {
      segments,
      status: isThoughtRunning ? 'active' : 'completed',
    };
  }, [
    toolCalls,
    toolCallAssistantContents,
    hasActiveToolCalls,
    isProcessing,
    selectedInstance,
    currentChatInstanceId,
    streamingContent,
    hasToolCallsInCurrentRun,
  ]);

  const lastThoughtFoldIdx = useMemo(() => {
    const indices = [];
    displayList.forEach((item, i) => {
      if (item.type === 'thought_fold') indices.push(i);
    });
    return indices.length > 0 ? indices[indices.length - 1] : -1;
  }, [displayList]);

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
        
        if (item.type === 'subagent_sync') {
          return (
            <SubagentSyncFold
              key={item.message.id || idx}
              result={item.result}
            />
          );
        }
        
        // 仅隐藏最后一个 thought_fold（避免与 liveThought 重复展示），历史折叠正常显示
        if (item.type === 'thought_fold' && hasActiveToolCalls && idx === lastThoughtFoldIdx) {
          return null;
        }
        if (item.type === 'thought_fold') {
          return (
            <IterationFold
              key={item.key}
              status={item.status}
              segments={item.segments}
              totalMs={item.elapsedMs}
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
          tokenUsage={liveTokenUsage}
          isExpanded
        />
      )}

      {streamingContent && selectedInstance?.id === currentChatInstanceId && !liveThought && (
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
