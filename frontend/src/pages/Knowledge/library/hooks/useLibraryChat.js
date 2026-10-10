import { useCallback } from 'react';
import { useChat } from '../../hooks/useChat';

export function useLibraryChat({ sendMessage, subscribe, unsubscribe, scope, agentConfigName } = {}) {
  const getScopeKey = (s) => {
    if (!s) return 'global:';
    return `${s.type}:${s.type === 'items' ? (s.item_ids || []).sort().join(',') : s.collection_id || ''}`;
  };

  const serializeScope = (s) => {
    const scope_type = s?.type || 'global';
    const scope_value = s?.type === 'items'
      ? (s.item_ids || []).sort().join(',')
      : String(s?.collection_id || '');
    return { scope_type, scope_value };
  };

  const chat = useChat({
    sendMessage,
    subscribe,
    unsubscribe,
    scope,
    wsAction: 'library_chat',
    getScopeKey,
    serializeScope,
  });

  // Wrap createSession so a built-in agent name (e.g. "library-thinker") is
  // automatically forwarded on every new session, and so the sidebar shows
  // a friendly default title instead of the generic "New Chat".
  const createSession = useCallback(
    async (title = 'New Chat', options = {}) => {
      const merged = { ...options };
      if (agentConfigName && merged.agentConfigName == null && merged.agentConfigId == null) {
        merged.agentConfigName = agentConfigName;
      }
      let effectiveTitle = title;
      if (agentConfigName === 'library-thinker' && (title === 'New Chat' || !title)) {
        effectiveTitle = '向思考者提问';
      }
      return chat.createSession(effectiveTitle, merged);
    },
    [chat.createSession, agentConfigName]
  );

  return { ...chat, createSession };
}
