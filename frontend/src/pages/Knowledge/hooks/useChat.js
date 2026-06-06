import { useState, useEffect, useRef, useCallback } from 'react';

export function useChat({
  sendMessage,
  subscribe,
  unsubscribe,
  scope,
  wsAction,
  getScopeKey,
  serializeScope,
}) {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const streamingRef = useRef('');
  const isExpectingResponseRef = useRef(false);
  const pendingToolsRef = useRef(new Map());
  const scopeRef = useRef(scope);
  const serializeScopeRef = useRef(serializeScope);

  // Keep refs in sync without causing effect re-runs
  useEffect(() => { scopeRef.current = scope; }, [scope]);
  useEffect(() => { serializeScopeRef.current = serializeScope; }, [serializeScope]);

  const currentScopeKey = getScopeKey(scope);

  // ── Load sessions for current scope ──
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const { scope_type, scope_value } = serializeScopeRef.current(scopeRef.current);
        const resp = await sendMessage(wsAction, {
          action: 'list_sessions',
          scope_type,
          scope_value,
        }, 10000);
        if (cancelled) return;
        const list = resp?.data?.sessions || [];
        setSessions(list);
        setCurrentSessionId((prev) => {
          // Keep previous session if it still exists in the new scope;
          // otherwise pick the first available session
          if (prev && list.some((s) => s.id === prev)) return prev;
          return list[0]?.id || null;
        });
        if (list.length === 0) {
          setMessages([]);
        }
      } catch {}
    };
    load();
    return () => { cancelled = true; };
  }, [currentScopeKey, sendMessage, wsAction]);

  // ── Load messages when session changes ──
  useEffect(() => {
    if (!currentSessionId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const resp = await sendMessage(wsAction, {
          action: 'list_messages',
          session_id: currentSessionId,
        }, 10000);
        if (cancelled) return;
        setMessages(resp?.data?.messages || []);
      } catch {}
    };
    load();
    return () => { cancelled = true; };
  }, [currentSessionId, sendMessage, wsAction]);

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
        const thinkingText = streamingRef.current;
        if (thinkingText && thinkingText.trim()) {
          setMessages((prev) => [...prev, {
            id: `a-think-${Date.now()}`,
            session_id: data.session_id || currentSessionId,
            role: 'assistant',
            content: thinkingText,
            created_at: new Date().toISOString(),
          }]);
          streamingRef.current = '';
          setStreamingContent('');
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
      } else if (status === 'completed') {
        const finalText = data.content || streamingRef.current;
        streamingRef.current = '';
        setStreamingContent('');
        setLoading(false);
        isExpectingResponseRef.current = false;
        pendingToolsRef.current.clear();
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
  }, [subscribe, currentSessionId, wsAction]);

  const createSession = useCallback(async (title = 'New Chat') => {
    try {
      const { scope_type, scope_value } = serializeScopeRef.current(scopeRef.current);
      const resp = await sendMessage(wsAction, {
        action: 'create_session',
        title,
        scope_type,
        scope_value,
      }, 10000);
      const session = resp?.data?.session;
      if (session) {
        setSessions((prev) => [session, ...prev]);
        setCurrentSessionId(session.id);
        return session;
      }
    } catch (e) {
      console.error('Failed to create session:', e);
    }
    return null;
  }, [sendMessage, wsAction]);

  const deleteSession = useCallback(async (sessionId) => {
    try {
      await sendMessage(wsAction, {
        action: 'delete_session',
        session_id: sessionId,
      }, 10000);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
        setMessages([]);
      }
    } catch (e) {
      console.error('Failed to delete session:', e);
    }
  }, [sendMessage, currentSessionId, wsAction]);

  const sendChat = useCallback(async ({ content }) => {
    let sessionId = currentSessionId;
    if (!sessionId) {
      const session = await createSession();
      if (!session) return;
      sessionId = session.id;
    }

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
    isExpectingResponseRef.current = true;
    pendingToolsRef.current.clear();

    sendMessage(wsAction, {
      action: 'chat',
      session_id: sessionId,
      content,
      scope: scopeRef.current,
    }, 120000).catch((e) => {
      console.error('Failed to send chat:', e);
      setLoading(false);
      isExpectingResponseRef.current = false;
    });
  }, [currentSessionId, createSession, sendMessage, wsAction]);

  return {
    sessions,
    currentSessionId,
    setCurrentSessionId,
    messages,
    loading,
    streamingContent,
    createSession,
    deleteSession,
    sendChat,
  };
}
