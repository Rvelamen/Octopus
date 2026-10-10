import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Hook for annotation-bound PDF chat sessions.
 *
 * Mirrors usePdfChat but targets the `pdf_annotation_chat` MessageType
 * (handler `PdfAnnotationChatHandler`) and the `pdf_annotation_chat_*`
 * tables. Each session is permanently bound to one library_annotations row;
 * the LLM system prompt is augmented with that annotation's quote + its
 * thread comments (see PdfAnnotationChatAgent._build_system_prompt).
 *
 * Usage:
 *   const { sessions, currentSessionId, setCurrentSessionId, messages,
 *           loading, streamingContent, createSession, deleteSession, sendChat }
 *     = useAnnotationChat({ sendMessage, subscribe, unsubscribe, itemId, pdfPath, annotationId });
 *
 * - Pass `annotationId=null` (or omit) to list ALL sessions for the given
 *   itemId / pdfPath — used by the "All annotations" view in the chat drawer.
 * - Pass a concrete annotationId to scope the chat drawer to that annotation.
 *   Switching annotationId will reset the current session selection.
 */
export function useAnnotationChat({
  sendMessage,
  subscribe,
  unsubscribe,
  itemId,
  pdfPath,
  annotationId,
}) {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const streamingRef = useRef('');
  const activeRequestIdRef = useRef(null);
  const isExpectingResponseRef = useRef(false);
  const pendingToolsRef = useRef(new Map());

  // ── Load sessions (filtered by annotationId when provided) ──
  useEffect(() => {
    if (!itemId && !pdfPath && annotationId == null) {
      setSessions([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const resp = await sendMessage(
          'pdf_annotation_chat',
          {
            action: 'list_sessions',
            annotation_id: annotationId ?? null,
            item_id: itemId ? Number(itemId) : null,
            pdf_path: pdfPath || null,
          },
          10000,
        );
        if (cancelled) return;
        const list = resp?.data?.sessions || [];
        setSessions(list);
        if (list.length > 0) {
          setCurrentSessionId((prev) => prev || list[0].id);
        } else {
          setCurrentSessionId(null);
        }
      } catch {}
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [itemId, pdfPath, annotationId, sendMessage]);

  // ── Load messages when session changes ──
  useEffect(() => {
    if (!currentSessionId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const resp = await sendMessage(
          'pdf_annotation_chat',
          {
            action: 'list_messages',
            session_id: currentSessionId,
          },
          10000,
        );
        if (cancelled) return;
        setMessages(resp?.data?.messages || []);
      } catch {}
    };
    load();
    return () => {
      cancelled = true;
    };
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
        const toolId = data.tool_call_id || `tool-${Date.now()}`;
        pendingToolsRef.current.set(toolId, {
          id: toolId,
          tool: data.tool,
          args: data.args,
          result: null,
          status: 'running',
        });
        setMessages((prev) => [
          ...prev,
          {
            id: `tool-${toolId}`,
            session_id: data.session_id,
            role: 'tool',
            content: '',
            metadata: {
              tool: data.tool,
              args: data.args,
              status: 'running',
              tool_call_id: toolId,
            },
            created_at: new Date().toISOString(),
          },
        ]);
      } else if (status === 'tool_result') {
        const toolId = data.tool_call_id;
        if (toolId && pendingToolsRef.current.has(toolId)) {
          pendingToolsRef.current.get(toolId).result = data.result;
          pendingToolsRef.current.get(toolId).status = 'done';
        }
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.role === 'tool' && msg.metadata?.tool_call_id === toolId) {
              return {
                ...msg,
                metadata: { ...msg.metadata, status: 'done', result: data.result },
              };
            }
            return msg;
          }),
        );
      } else if (status === 'completed') {
        const finalText = data.content || streamingRef.current;
        streamingRef.current = '';
        setStreamingContent('');
        setLoading(false);
        isExpectingResponseRef.current = false;
        pendingToolsRef.current.clear();
        if (finalText) {
          setMessages((prev) => [
            ...prev,
            {
              id: `a-${Date.now()}`,
              session_id: data.session_id || currentSessionId,
              role: 'assistant',
              content: finalText,
              created_at: new Date().toISOString(),
            },
          ]);
        }
      } else if (status === 'error') {
        streamingRef.current = '';
        setStreamingContent('');
        setLoading(false);
        isExpectingResponseRef.current = false;
        pendingToolsRef.current.clear();
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            session_id: data.session_id || currentSessionId,
            role: 'assistant',
            content: `⚠️ ${data.error || 'Something went wrong'}`,
            created_at: new Date().toISOString(),
          },
        ]);
      }
    };
    const unsub = subscribe('chat_response', handleResponse);
    return () => unsub();
  }, [subscribe, currentSessionId]);

  const createSession = useCallback(
    async (
      title = 'Annotation Chat',
      options = {},
    ) => {
      try {
        const resp = await sendMessage(
          'pdf_annotation_chat',
          {
            action: 'create_session',
            annotation_id:
              options.annotation_id ?? annotationId ?? null,
            title,
            item_id: itemId ? Number(itemId) : null,
            pdf_path: pdfPath || null,
          },
          10000,
        );
        const session = resp?.data?.session;
        if (session) {
          setSessions((prev) => [session, ...prev]);
          setCurrentSessionId(session.id);
          return session;
        }
      } catch (e) {
        console.error('Failed to create annotation chat session:', e);
      }
      return null;
    },
    [sendMessage, itemId, pdfPath, annotationId],
  );

  const deleteSession = useCallback(
    async (sessionId) => {
      try {
        await sendMessage(
          'pdf_annotation_chat',
          {
            action: 'delete_session',
            session_id: sessionId,
          },
          10000,
        );
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (currentSessionId === sessionId) {
          setCurrentSessionId(null);
          setMessages([]);
        }
      } catch (e) {
        console.error('Failed to delete annotation chat session:', e);
      }
    },
    [currentSessionId, sendMessage],
  );

  const sendChat = useCallback(
    async ({ content, pageNumber, selectedText }) => {
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

      sendMessage(
        'pdf_annotation_chat',
        {
          action: 'chat',
          session_id: sessionId,
          content,
          page_number: pageNumber,
          selected_text: selectedText,
        },
        120000,
      ).catch((e) => {
        console.error('Failed to send annotation chat:', e);
        setLoading(false);
        isExpectingResponseRef.current = false;
      });
    },
    [currentSessionId, createSession, sendMessage],
  );

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
