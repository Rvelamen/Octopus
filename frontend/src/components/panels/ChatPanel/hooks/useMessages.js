import { useState, useCallback } from 'react';

export function useMessages(sendWSMessage, selectedInstance) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchInstanceMessages = useCallback(async (instanceId) => {
    if (!sendWSMessage) return;
    setLoading(true);
    try {
      const response = await sendWSMessage('session_get_messages', { instance_id: instanceId, limit: 1000 }, 5000);
      console.log('fetchInstanceMessages response:', response.data);
      if (response.data?.messages) {
        console.log('Fetched messages:', response.data.messages);
        const fetchedMessages = response.data.messages;
        
        setMessages(prev => {
          const existingMap = new Map();
          prev.forEach(msg => {
            const key = `${msg.role}:${msg.content}`;
            existingMap.set(key, msg);
          });

          return fetchedMessages.map(msg => {
            const key = `${msg.role}:${msg.content}`;
            const existing = existingMap.get(key);

            const existingImages = existing?.metadata?.images || existing?.metadata?.metadata?.images;
            const fetchedImages = msg.metadata?.images || msg.metadata?.metadata?.images;
            const hasFetchedImages = fetchedImages && fetchedImages.length > 0;
            
            const existingFiles = existing?.metadata?.files || existing?.metadata?.metadata?.files;
            const fetchedFiles = msg.metadata?.files || msg.metadata?.metadata?.files;
            const hasFetchedFiles = fetchedFiles && fetchedFiles.length > 0;

            const needMerge = (existingImages && existingImages.length > 0 && !hasFetchedImages) ||
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
                metadata: mergedMetadata
              };
            }
            return msg;
          });
        });
      }
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const addMessage = useCallback((message) => {
    setMessages(prev => [...prev, message]);
  }, []);

  return {
    messages,
    loading,
    fetchInstanceMessages,
    clearMessages,
    addMessage,
    setMessages
  };
}
