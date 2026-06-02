import { useState, useEffect, useRef, useCallback } from 'react';

export function useWorkflowDesignChat({ sendMessage, subscribe, unsubscribe, workflowId }) {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [lastToolResult, setLastToolResult] = useState(null);
  const streamingRef = useRef('');
  const isExpectingResponseRef = useRef(false);
  const pendingToolsRef = useRef(new Map());
  const onToolResultRef = useRef(null);

  // ── Init / Load session for workflow ──
  useEffect(() => {
    if (!workflowId) return;
    let cancelled = false;
    const load = async () => {
      try {
        const resp = await sendMessage('workflow_design', {
          action: 'init_session',
          workflow_id: workflowId,
        }, 10000);
        if (cancelled) return;
        const session = resp?.data?.session;
        if (session) {
          setSessions([session]);
          setCurrentSessionId(session.id);
        }
      } catch (e) {
        console.error('Failed to init workflow design session:', e);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [workflowId, sendMessage]);

  // ── Load messages when session changes ──
  useEffect(() => {
    if (!currentSessionId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const resp = await sendMessage('workflow_design', {
          action: 'list_messages',
          session_id: currentSessionId,
        }, 10000);
        if (cancelled) return;
        setMessages(resp?.data?.messages || []);
      } catch {}
    };
    load();
    return () => { cancelled = true; };
  }, [currentSessionId, sendMessage]);

  // ── Subscribe to streaming responses ──
  useEffect(() => {
    const handleResponse = (data, payload) => {
      if (!isExpectingResponseRef.current || data?.session_id == null) return;
      if (data.session_id !== currentSessionId) return;

      const status = data?.status;
      if (status === 'streaming' && data.content) {
        streamingRef.current += data.content;
        setStreamingContent(streamingRef.current);
      } else if (status === 'tool_start') {
        // Commit current streaming text as an assistant message before the tool call
        // so that text and tools appear interleaved in the UI
        if (streamingRef.current) {
          const text = streamingRef.current;
          streamingRef.current = '';
          setStreamingContent('');
          setMessages((prev) => [...prev, {
            id: `text-${Date.now()}`,
            session_id: data.session_id,
            role: 'assistant',
            content: text,
            created_at: new Date().toISOString(),
          }]);
        }

        const toolId = data.tool_call_id || `tool-${Date.now()}`;
        pendingToolsRef.current.set(toolId, {
          id: toolId,
          tool: data.tool,
          args: data.args,
          result: null,
          status: 'running',
        });
        setMessages((prev) => [...prev, {
          id: `tool-${toolId}`,
          session_id: data.session_id,
          role: 'tool',
          content: '',
          metadata: { tool: data.tool, args: data.args, status: 'running', tool_call_id: toolId },
          created_at: new Date().toISOString(),
        }]);
      } else if (status === 'tool_result') {
        const toolId = data.tool_call_id;
        if (toolId && pendingToolsRef.current.has(toolId)) {
          pendingToolsRef.current.get(toolId).result = data.result;
          pendingToolsRef.current.get(toolId).status = 'done';
        }
        setMessages((prev) => prev.map((msg) => {
          if (msg.role === 'tool' && msg.metadata?.tool_call_id === toolId) {
            return {
              ...msg,
              metadata: { ...msg.metadata, status: 'done', result: data.result },
            };
          }
          return msg;
        }));
        // Notify external listeners
        const toolResultData = { tool: data.tool, result: data.result, tool_call_id: toolId };
        setLastToolResult({ ...toolResultData, timestamp: Date.now() });
        if (onToolResultRef.current) {
          try { onToolResultRef.current(toolResultData); } catch {}
        }
      } else if (status === 'completed') {
        // Use only the remaining streaming text (text after the last tool call)
        // Previous text was already committed at each tool_start
        const finalText = streamingRef.current;
        streamingRef.current = '';
        setStreamingContent('');
        setLoading(false);
        isExpectingResponseRef.current = false;
        pendingToolsRef.current.clear();
        onToolResultRef.current = null;
        if (finalText) {
          setMessages((prev) => [...prev, {
            id: `a-${Date.now()}`,
            session_id: data.session_id || currentSessionId,
            role: 'assistant',
            content: finalText,
            created_at: new Date().toISOString(),
          }]);
        }
      } else if (status === 'error') {
        streamingRef.current = '';
        setStreamingContent('');
        setLoading(false);
        isExpectingResponseRef.current = false;
        pendingToolsRef.current.clear();
        onToolResultRef.current = null;
        setMessages((prev) => [...prev, {
          id: `err-${Date.now()}`,
          session_id: data.session_id || currentSessionId,
          role: 'assistant',
          content: `⚠️ ${data.error || 'Something went wrong'}`,
          created_at: new Date().toISOString(),
        }]);
      }
    };

    const unsub = subscribe('chat_response', handleResponse);
    return () => unsub();
  }, [subscribe, currentSessionId]);

  const sendChat = useCallback(async ({ content, selectedNodes, onToolResult }) => {
    const sessionId = currentSessionId;
    if (!sessionId || !workflowId) {
      console.error('No session or workflow');
      return;
    }

    // Store callback ref to avoid closure staleness
    onToolResultRef.current = onToolResult || null;

    // Optimistically add user message
    const userMsg = {
      id: `local-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    streamingRef.current = '';
    setStreamingContent('');
    setLastToolResult(null);
    isExpectingResponseRef.current = true;
    pendingToolsRef.current.clear();

    sendMessage('workflow_design', {
      action: 'chat',
      session_id: sessionId,
      workflow_id: workflowId,
      content,
      selected_nodes: selectedNodes || [],
    }, 120000).catch((e) => {
      console.error('Failed to send design chat:', e);
      setLoading(false);
      isExpectingResponseRef.current = false;
      onToolResultRef.current = null;
    });
  }, [currentSessionId, workflowId, sendMessage]);

  const clearSession = useCallback(async () => {
    if (!currentSessionId) return;
    try {
      await sendMessage('workflow_design', {
        action: 'clear_session',
        session_id: currentSessionId,
      }, 10000);
      setMessages([]);
      setLastToolResult(null);
      setLoading(false);
      streamingRef.current = '';
      setStreamingContent('');
      isExpectingResponseRef.current = false;
      pendingToolsRef.current.clear();
      onToolResultRef.current = null;

      // 后端 clear_session 会销毁旧 session，需要重新初始化
      const resp = await sendMessage('workflow_design', {
        action: 'init_session',
        workflow_id: workflowId,
      }, 10000);
      const session = resp?.data?.session;
      if (session) {
        setSessions([session]);
        setCurrentSessionId(session.id);
      }
    } catch (e) {
      console.error('Failed to clear session:', e);
    }
  }, [currentSessionId, workflowId, sendMessage]);

  return {
    sessions,
    currentSessionId,
    setCurrentSessionId,
    messages,
    loading,
    streamingContent,
    lastToolResult,
    sendChat,
    clearSession,
  };
}
