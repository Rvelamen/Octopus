import { useChat } from '../../hooks/useChat';

export function useLibraryChat({ sendMessage, subscribe, unsubscribe, scope }) {
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

  return useChat({
    sendMessage,
    subscribe,
    unsubscribe,
    scope,
    wsAction: 'library_chat',
    getScopeKey,
    serializeScope,
  });
}
