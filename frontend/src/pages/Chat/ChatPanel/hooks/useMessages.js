import { useState, useCallback, useRef, useLayoutEffect } from 'react';

/**
 * 按 session instance 隔离消息列表，避免切换对话时互相覆盖；
 * 后台刷新（如 agent_iteration_complete）只更新对应 instance 的缓存，不污染当前正在看的对话。
 */
export function useMessages(sendWSMessage, selectedInstance) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const messagesByInstanceRef = useRef({});
  const messagesRef = useRef([]);
  messagesRef.current = messages;

  const selectedInstanceIdRef = useRef(null);
  selectedInstanceIdRef.current = selectedInstance?.id ?? null;

  const prevSelectedIdRef = useRef(undefined);

  useLayoutEffect(() => {
    const newId = selectedInstance?.id ?? null;
    const prevId = prevSelectedIdRef.current;

    if (prevId !== undefined && newId !== null && prevId !== null && prevId !== newId) {
      messagesByInstanceRef.current[prevId] = messagesRef.current;
    }
    prevSelectedIdRef.current = newId;

    if (newId === null) {
      setMessages([]);
      return;
    }
    const restored = messagesByInstanceRef.current[newId];
    setMessages(restored ?? []);
  }, [selectedInstance?.id]);

  const mergeFetchedWithExisting = useCallback((fetchedMessages, existingSource) => {
    const existingMap = new Map();
    existingSource.forEach((msg) => {
      const key = `${msg.role}:${msg.content}`;
      existingMap.set(key, msg);
    });

    return fetchedMessages.map((msg) => {
      const key = `${msg.role}:${msg.content}`;
      const existing = existingMap.get(key);

      const existingImages = existing?.metadata?.images || existing?.metadata?.metadata?.images;
      const fetchedImages = msg.metadata?.images || msg.metadata?.metadata?.images;
      const hasFetchedImages = fetchedImages && fetchedImages.length > 0;

      const existingFiles = existing?.metadata?.files || existing?.metadata?.metadata?.files;
      const fetchedFiles = msg.metadata?.files || msg.metadata?.metadata?.files;
      const hasFetchedFiles = fetchedFiles && fetchedFiles.length > 0;

      const needMerge =
        (existingImages && existingImages.length > 0 && !hasFetchedImages) ||
        (existingFiles && existingFiles.length > 0 && !hasFetchedFiles);

      if (needMerge) {
        const mergedMetadata = { ...msg.metadata };
        if (existingImages && existingImages.length > 0 && !hasFetchedImages) {
          mergedMetadata.images = existingImages;
        }
        if (existingFiles && existingFiles.length > 0 && !hasFetchedFiles) {
          mergedMetadata.files = existingFiles;
        }
        return {
          ...msg,
          metadata: mergedMetadata,
        };
      }
      return msg;
    });
  }, []);

  const fetchInstanceMessages = useCallback(
    async (instanceId) => {
      if (!sendWSMessage) return;
      setLoading(true);
      try {
        const response = await sendWSMessage(
          'session_get_messages',
          { instance_id: instanceId, limit: 1000 },
          5000
        );
        if (response.data?.messages) {
          const fetchedMessages = response.data.messages;
          const existingSource = messagesByInstanceRef.current[instanceId] ?? [];

          const merged = mergeFetchedWithExisting(fetchedMessages, existingSource);
          messagesByInstanceRef.current[instanceId] = merged;

          if (selectedInstanceIdRef.current === instanceId) {
            setMessages(merged);
          }
        }
      } catch (err) {
        console.error('Failed to fetch messages:', err);
      } finally {
        setLoading(false);
      }
    },
    [sendWSMessage, mergeFetchedWithExisting]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    const id = selectedInstanceIdRef.current;
    if (id != null) {
      delete messagesByInstanceRef.current[id];
    }
  }, []);

  const addMessage = useCallback((message) => {
    setMessages((prev) => {
      const next = [...prev, message];
      const id = selectedInstanceIdRef.current;
      if (id != null) {
        messagesByInstanceRef.current[id] = next;
      }
      return next;
    });
  }, []);

  const setMessagesSynced = useCallback((updater) => {
    setMessages((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      const id = selectedInstanceIdRef.current;
      if (id != null) {
        messagesByInstanceRef.current[id] = next;
      }
      return next;
    });
  }, []);

  return {
    messages,
    loading,
    fetchInstanceMessages,
    clearMessages,
    addMessage,
    setMessages: setMessagesSynced,
  };
}
