import { useState, useRef, useEffect, useCallback } from 'react';
import { useWebSocket } from '../contexts/WebSocketContext';

export function useChatState() {
  const { subscribe, unsubscribe } = useWebSocket();

  const [isProcessing, setIsProcessing] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const streamingContentRef = useRef("");
  const streamingFlushTimerRef = useRef(null);

  const [currentChatInstanceId, setCurrentChatInstanceId] = useState(null);
  const currentChatInstanceIdRef = useRef(null);

  const [toolCalls, _setToolCalls] = useState([]);
  const [toolCallAssistantContents, _setToolCallAssistantContents] = useState({});
  const toolCallsByInstanceRef = useRef({});
  const assistantContentsByInstanceRef = useRef({});
  const prevToolCallInstanceRef = useRef(null);

  const [lastElapsedMs, setLastElapsedMs] = useState(null);
  const [lastTokenUsage, setLastTokenUsage] = useState(null);
  const [liveTokenUsage, setLiveTokenUsage] = useState(null);

  const [ttsAudio, setTtsAudio] = useState(null);
  const [ttsAudioMap, setTtsAudioMap] = useState({});

  const [refreshInstanceId, setRefreshInstanceId] = useState(null);
  const [hasToolCallsInCurrentRun, setHasToolCallsInCurrentRun] = useState(false);

  // Sync ref with state
  useEffect(() => {
    currentChatInstanceIdRef.current = currentChatInstanceId;
  }, [currentChatInstanceId]);

  const resetStreamingContent = useCallback(() => {
    if (streamingFlushTimerRef.current) {
      clearTimeout(streamingFlushTimerRef.current);
      streamingFlushTimerRef.current = null;
    }
    streamingContentRef.current = "";
    setStreamingContent("");
  }, []);

  const appendStreamingContent = useCallback((text) => {
    streamingContentRef.current += text || "";
    if (!streamingFlushTimerRef.current) {
      streamingFlushTimerRef.current = setTimeout(() => {
        streamingFlushTimerRef.current = null;
        setStreamingContent(streamingContentRef.current);
      }, 80);
    }
  }, []);

  const syncStreamingContent = useCallback(() => {
    setStreamingContent(streamingContentRef.current);
  }, []);

  const setToolCalls = useCallback((updater) => {
    _setToolCalls((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      const id = currentChatInstanceIdRef.current;
      if (id != null) toolCallsByInstanceRef.current[id] = next;
      return next;
    });
  }, []);

  const setToolCallAssistantContents = useCallback((updater) => {
    _setToolCallAssistantContents((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      const id = currentChatInstanceIdRef.current;
      if (id != null) assistantContentsByInstanceRef.current[id] = next;
      return next;
    });
  }, []);

  const updateToolCallsForInstance = useCallback((instanceId, updater) => {
    if (instanceId == null) return;
    const prev = toolCallsByInstanceRef.current[instanceId] ?? [];
    const next = typeof updater === 'function' ? updater(prev) : updater;
    toolCallsByInstanceRef.current[instanceId] = next;
  }, []);

  const updateAssistantContentsForInstance = useCallback((instanceId, updater) => {
    if (instanceId == null) return;
    const prev = assistantContentsByInstanceRef.current[instanceId] ?? {};
    const next = typeof updater === 'function' ? updater(prev) : updater;
    assistantContentsByInstanceRef.current[instanceId] = next;
  }, []);

  // Switch instance: save/restore toolCalls and assistantContents
  useEffect(() => {
    const newId = currentChatInstanceId;
    const prevId = prevToolCallInstanceRef.current;

    if (prevId !== undefined && prevId !== null && prevId !== newId) {
      toolCallsByInstanceRef.current[prevId] = toolCallsByInstanceRef.current[prevId] || [];
    }
    prevToolCallInstanceRef.current = newId;

    if (newId !== null) {
      const restoredToolCalls = toolCallsByInstanceRef.current[newId];
      const restoredContents = assistantContentsByInstanceRef.current[newId];
      _setToolCalls(restoredToolCalls ?? []);
      _setToolCallAssistantContents(restoredContents ?? {});
    } else {
      _setToolCalls([]);
      _setToolCallAssistantContents({});
    }
  }, [currentChatInstanceId]);

  // WebSocket event handlers
  useEffect(() => {
    const handleAgentToken = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      if (!isCurrentInstance) return;
      appendStreamingContent(data.content || "");
    };

    const handleAgentChunk = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      if (!isCurrentInstance) return;
      appendStreamingContent(data.content || "");
    };

    const handleAgentStart = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      if (!isCurrentInstance) {
        updateToolCallsForInstance(eventInstanceId, () => []);
        updateAssistantContentsForInstance(eventInstanceId, () => ({}));
        return;
      }
      resetStreamingContent();
      setToolCalls(() => []);
      setToolCallAssistantContents(() => ({}));
      setLiveTokenUsage(null);
      setHasToolCallsInCurrentRun(false);
    };

    const handleAgentThinking = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      if (!isCurrentInstance) return;
      setIsProcessing(true);
      resetStreamingContent();
      setToolCallAssistantContents((prev) => prev || {});
    };

    const handleChatResponse = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      if (!isCurrentInstance) {
        updateToolCallsForInstance(eventInstanceId, () => []);
        updateAssistantContentsForInstance(eventInstanceId, () => ({}));
        return;
      }
      resetStreamingContent();
      setIsProcessing(false);
      setToolCalls(() => []);
      setToolCallAssistantContents(() => ({}));
      setLiveTokenUsage(null);
    };

    const handleError = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      if (!isCurrentInstance) {
        updateToolCallsForInstance(eventInstanceId, () => []);
        updateAssistantContentsForInstance(eventInstanceId, () => ({}));
        return;
      }
      resetStreamingContent();
      setIsProcessing(false);
      setToolCalls(() => []);
      setToolCallAssistantContents(() => ({}));
      setLiveTokenUsage(null);
    };

    const handleAgentFinish = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      if (!isCurrentInstance) {
        updateToolCallsForInstance(eventInstanceId, () => []);
        updateAssistantContentsForInstance(eventInstanceId, () => ({}));
        return;
      }
      resetStreamingContent();
      setIsProcessing(false);
      if (data.elapsed_ms != null) {
        setLastElapsedMs(data.elapsed_ms);
      }
      if (data.token_usage) {
        setLastTokenUsage(data.token_usage);
        setLiveTokenUsage(data.token_usage);
      }
      setToolCalls(() => []);
      setToolCallAssistantContents(() => ({}));
    };

    const handleAgentToolCallStart = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;

      const addToolCall = (prev) => [...prev, {
        id: data.tool_call_id || Date.now(),
        tool: data.tool,
        args: data.args || {},
        partialArgs: data.partial_args || data.args || {},
        status: 'pending',
        result: null,
        iteration: data.iteration || 1
      }];

      // 优先使用事件携带的 content，若为空则回退到已累积的 streamingContent
      const reasoningText = data.content || streamingContentRef.current || '';
      const trimmedReasoning = reasoningText.trim();
      if (trimmedReasoning) {
        const setContent = (prev) => ({ ...prev, [data.iteration]: trimmedReasoning });
        if (isCurrentInstance) {
          setToolCallAssistantContents(setContent);
          resetStreamingContent();
        } else {
          updateAssistantContentsForInstance(eventInstanceId, setContent);
        }
      }
      if (isCurrentInstance) {
        setToolCalls(addToolCall);
        setHasToolCallsInCurrentRun(true);
      } else {
        updateToolCallsForInstance(eventInstanceId, addToolCall);
      }
    };

    const handleAgentToolCallStreaming = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      const updater = (prev) => prev.map(tc =>
        tc.id === data.tool_call_id
          ? { ...tc, partialArgs: data.partial_args, status: 'streaming' }
          : tc
      );
      if (isCurrentInstance) setToolCalls(updater);
      else updateToolCallsForInstance(eventInstanceId, updater);
    };

    const handleAgentToolCallInvoking = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      const updater = (prev) => prev.map(tc =>
        tc.id === data.tool_call_id
          ? { ...tc, args: tc.partialArgs || tc.args, status: 'invoking' }
          : tc
      );
      if (isCurrentInstance) setToolCalls(updater);
      else updateToolCallsForInstance(eventInstanceId, updater);
    };

    const handleAgentToolCallComplete = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      const updater = (prev) => prev.map(tc =>
        tc.id === data.tool_call_id
          ? { ...tc, args: data.args || tc.partialArgs || tc.args, result: data.result, status: 'completed' }
          : tc
      );
      if (isCurrentInstance) setToolCalls(updater);
      else updateToolCallsForInstance(eventInstanceId, updater);
    };

    const handleAgentToolCallError = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      const updater = (prev) => prev.map(tc =>
        tc.id === data.tool_call_id
          ? { ...tc, args: data.args || tc.partialArgs || tc.args, error: data.error, status: 'error' }
          : tc
      );
      if (isCurrentInstance) setToolCalls(updater);
      else updateToolCallsForInstance(eventInstanceId, updater);
    };

    const handleAgentToolCall = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      const addToolCall = (prev) => [...prev, {
        id: data.tool_call_id || Date.now(),
        tool: data.tool,
        args: data.args,
        status: 'running',
        result: null,
        iteration: data.iteration
      }];
      if (data.content) {
        const setContent = (prev) => ({ ...prev, [data.iteration]: data.content });
        if (isCurrentInstance) setToolCallAssistantContents(setContent);
        else updateAssistantContentsForInstance(eventInstanceId, setContent);
      }
      if (isCurrentInstance) setToolCalls(addToolCall);
      else updateToolCallsForInstance(eventInstanceId, addToolCall);
    };

    const handleAgentToolResult = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      const updater = (prev) => prev.map(tc =>
        tc.id === data.tool_call_id
          ? { ...tc, status: 'completed', result: data.result }
          : tc
      );
      if (isCurrentInstance) setToolCalls(updater);
      else updateToolCallsForInstance(eventInstanceId, updater);
    };

    const handleSubagentToolCall = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      const parentToolCallId = data.parent_tool_call_id;

      const subagentUpdater = (prev) => {
        const targetTc = prev.find(tc => tc.id === parentToolCallId);
        if (targetTc) {
          return prev.map(tc =>
            tc.id === parentToolCallId
              ? {
                  ...tc,
                  subagentCalls: [...(tc.subagentCalls || []), {
                    id: data.tool_call_id,
                    tool: data.tool,
                    args: data.args,
                    status: 'running',
                    subagentId: data.subagent_id,
                    subagentLabel: data.subagent_label,
                  }]
                }
              : tc
          );
        }
        return [...prev, {
          id: parentToolCallId || `subagent-${Date.now()}`,
          tool: 'spawn',
          args: { task: 'subagent' },
          status: 'running',
          subagentCalls: [{
            id: data.tool_call_id,
            tool: data.tool,
            args: data.args,
            status: 'running',
            subagentId: data.subagent_id,
            subagentLabel: data.subagent_label,
          }],
          isSubagentContainer: true,
        }];
      };

      if (isCurrentInstance) setToolCalls(subagentUpdater);
      else updateToolCallsForInstance(eventInstanceId, subagentUpdater);
    };

    const handleSubagentToolResult = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      const parentToolCallId = data.parent_tool_call_id;

      const subagentResultUpdater = (prev) => {
        const updated = prev.map(tc =>
          tc.id === parentToolCallId && tc.subagentCalls
            ? {
                ...tc,
                subagentCalls: tc.subagentCalls?.map(sc =>
                  sc.id === data.tool_call_id
                    ? { ...sc, status: 'completed', result: data.result }
                    : sc
                )
              }
            : tc
        );
        const hasTarget = updated.some(tc => tc.id === parentToolCallId);
        if (!hasTarget) {
          return [...updated, {
            id: parentToolCallId || `subagent-${Date.now()}`,
            tool: 'spawn',
            args: { task: 'subagent' },
            status: 'completed',
            subagentCalls: [{
              id: data.tool_call_id,
              tool: data.tool,
              args: data.args,
              status: 'completed',
              result: data.result,
              subagentId: data.subagent_id,
              subagentLabel: data.subagent_label,
            }],
            isSubagentContainer: true,
          }];
        }
        return updated;
      };

      if (isCurrentInstance) setToolCalls(subagentResultUpdater);
      else updateToolCallsForInstance(eventInstanceId, subagentResultUpdater);
    };

    const handleSubagentToken = (data) => {
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      const parentToolCallId = data.parent_tool_call_id;
      const tokenUpdater = (prev) => prev.map((tc) =>
        tc.id === parentToolCallId
          ? { ...tc, subagentStreamingContent: (tc.subagentStreamingContent || '') + (data.content || '') }
          : tc
      );
      if (isCurrentInstance) setToolCalls(tokenUpdater);
      else updateToolCallsForInstance(eventInstanceId, tokenUpdater);
    };

    const handleAgentIterationComplete = (data) => {
      const targetId = data?.session_instance_id ?? currentChatInstanceIdRef.current;
      if (targetId) {
        setRefreshInstanceId(targetId);
      }
      const eventInstanceId = data?.session_instance_id ?? data?.instance_id;
      if (eventInstanceId == null) return;
      const isCurrentInstance = eventInstanceId === currentChatInstanceIdRef.current;
      if (isCurrentInstance && data?.token_usage) {
        setLiveTokenUsage(data.token_usage);
      }
    };

    const handleTtsAutoReply = (data) => {
      if (data?.audio && data?.format) {
        setTtsAudio({
          audioData: data.audio,
          format: data.format,
          text: data.text,
          durationMs: data.duration_ms,
          instanceId: data.instanceId
        });
      }
    };

    subscribe('agent_token', handleAgentToken);
    subscribe('agent_chunk', handleAgentChunk);
    subscribe('agent_start', handleAgentStart);
    subscribe('agent_thinking', handleAgentThinking);
    subscribe('chat_response', handleChatResponse);
    subscribe('error', handleError);
    subscribe('agent_finish', handleAgentFinish);
    subscribe('agent_tool_call_start', handleAgentToolCallStart);
    subscribe('agent_tool_call_streaming', handleAgentToolCallStreaming);
    subscribe('agent_tool_call_invoking', handleAgentToolCallInvoking);
    subscribe('agent_tool_call_complete', handleAgentToolCallComplete);
    subscribe('agent_tool_call_error', handleAgentToolCallError);
    subscribe('agent_tool_call', handleAgentToolCall);
    subscribe('agent_tool_result', handleAgentToolResult);
    subscribe('subagent_tool_call', handleSubagentToolCall);
    subscribe('subagent_tool_result', handleSubagentToolResult);
    subscribe('subagent_token', handleSubagentToken);
    subscribe('agent_iteration_complete', handleAgentIterationComplete);
    subscribe('tts_auto_reply', handleTtsAutoReply);

    return () => {
      unsubscribe('agent_token', handleAgentToken);
      unsubscribe('agent_chunk', handleAgentChunk);
      unsubscribe('agent_start', handleAgentStart);
      unsubscribe('agent_thinking', handleAgentThinking);
      unsubscribe('chat_response', handleChatResponse);
      unsubscribe('error', handleError);
      unsubscribe('agent_finish', handleAgentFinish);
      unsubscribe('agent_tool_call_start', handleAgentToolCallStart);
      unsubscribe('agent_tool_call_streaming', handleAgentToolCallStreaming);
      unsubscribe('agent_tool_call_invoking', handleAgentToolCallInvoking);
      unsubscribe('agent_tool_call_complete', handleAgentToolCallComplete);
      unsubscribe('agent_tool_call_error', handleAgentToolCallError);
      unsubscribe('agent_tool_call', handleAgentToolCall);
      unsubscribe('agent_tool_result', handleAgentToolResult);
      unsubscribe('subagent_tool_call', handleSubagentToolCall);
      unsubscribe('subagent_tool_result', handleSubagentToolResult);
      unsubscribe('subagent_token', handleSubagentToken);
      unsubscribe('agent_iteration_complete', handleAgentIterationComplete);
      unsubscribe('tts_auto_reply', handleTtsAutoReply);
    };
  }, [subscribe, unsubscribe, appendStreamingContent, resetStreamingContent, setToolCalls, setToolCallAssistantContents, updateToolCallsForInstance, updateAssistantContentsForInstance]);

  return {
    isProcessing,
    setIsProcessing,
    streamingContent,
    setStreamingContent,
    streamingContentRef,
    resetStreamingContent,
    appendStreamingContent,
    syncStreamingContent,
    currentChatInstanceId,
    setCurrentChatInstanceId,
    toolCalls,
    setToolCalls,
    toolCallAssistantContents,
    setToolCallAssistantContents,
    lastElapsedMs,
    setLastElapsedMs,
    lastTokenUsage,
    setLastTokenUsage,
    liveTokenUsage,
    setLiveTokenUsage,
    ttsAudio,
    setTtsAudio,
    ttsAudioMap,
    setTtsAudioMap,
    refreshInstanceId,
    setRefreshInstanceId,
    hasToolCallsInCurrentRun,
    setHasToolCallsInCurrentRun,
  };
}
