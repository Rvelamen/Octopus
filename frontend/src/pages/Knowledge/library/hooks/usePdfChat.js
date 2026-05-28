import { useState, useEffect, useRef, useCallback } from 'react';

export function usePdfChat({ sendMessage, subscribe, unsubscribe, itemId, pdfPath }) {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const streamingRef = useRef('');
  const activeRequestIdRef = useRef(null);
  const isExpectingResponseRef = useRef(false);
  const pendingToolsRef = useRef(new Map());

  // ── Load sessions ──
  useEffect(() => {
    if (!itemId && !pdfPath) return;
    let cancelled = false;
    const load = async () => {
      try {
        const resp = await sendMessage('pdf_chat', {
          action: 'list_sessions',
          item_id: itemId ? Number(itemId) : null,
          pdf_path: pdfPath || null,
        }, 10000);
        if (cancelled) return;
        const list = resp?.data?.sessions || [];
        setSessions(list);
        if (list.length > 0) {
          setCurrentSessionId((prev) => prev || list[0].id);
        }
      } catch {}
    };
    load();
    return () => { cancelled = true; };
  }, [itemId, pdfPath, sendMessage]);

  // ── Load messages when session changes ──
  useEffect(() => {
    if (!currentSessionId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const resp = await sendMessage('pdf_chat', {
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
      // Only handle pdf_chat chat responses for the current session
      if (!isExpectingResponseRef.current || data?.session_id == null) return;
      if (data.session_id !== currentSessionId) return;

      const status = data?.status;
      if (status === 'streaming' && data.content) {
        streamingRef.current += data.content;
        setStreamingContent(streamingRef.current);
      } else if (status === 'tool_start') {
        // Track pending tool call
        const toolId = data.tool_call_id || `tool-${Date.now()}`;
        pendingToolsRef.current.set(toolId, {
          id: toolId,
          tool: data.tool,
          args: data.args,
          result: null,
          status: 'running',
        });
        // Force re-render by updating a dummy state or use a separate toolCalls state
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
        // Update the tool message with result
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
  }, [subscribe, currentSessionId]);

  const createSession = useCallback(async (title = 'New Chat') => {
    try {
      const resp = await sendMessage('pdf_chat', {
        action: 'create_session',
        title,
        item_id: itemId ? Number(itemId) : null,
        pdf_path: pdfPath || null,
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
  }, [sendMessage, itemId, pdfPath]);

  const deleteSession = useCallback(async (sessionId) => {
    try {
      await sendMessage('pdf_chat', {
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
  }, [sendMessage, currentSessionId]);

  const sendChat = useCallback(async ({ content, pageNumber, selectedText }) => {
    let sessionId = currentSessionId;
    if (!sessionId) {
      const session = await createSession();
      if (!session) return;
      sessionId = session.id;
    }

    // Optimistically add user message
    const userMsg = {
      id: `local-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content,
      page_number: pageNumber,
      selected_text: selectedText,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    streamingRef.current = '';
    setStreamingContent('');
    isExpectingResponseRef.current = true;
    pendingToolsRef.current.clear();

    // Fire and forget — streaming comes via subscribe('chat_response')
    sendMessage('pdf_chat', {
      action: 'chat',
      session_id: sessionId,
      content,
      page_number: pageNumber,
      selected_text: selectedText,
    }, 120000).catch((e) => {
      console.error('Failed to send chat:', e);
      setLoading(false);
      isExpectingResponseRef.current = false;
    });
  }, [currentSessionId, createSession, sendMessage]);

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
