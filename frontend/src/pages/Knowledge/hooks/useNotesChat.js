import { useChat } from './useChat';

export function useNotesChat({ sendMessage, subscribe, unsubscribe, scope }) {
  const getScopeKey = (s) => {
    if (!s) return 'global:';
    return `${s.type}:${s.type === 'file' ? (s.file_path || '') : s.type === 'vault' ? (s.vault || '') : ''}`;
  };

  const serializeScope = (s) => {
    const scope_type = s?.type || 'global';
    const scope_value = s?.type === 'file'
      ? (s.file_path || '')
      : s?.type === 'vault'
        ? (s.vault || '')
        : '';
    return { scope_type, scope_value };
  };

  return useChat({
    sendMessage,
    subscribe,
    unsubscribe,
    scope,
    wsAction: 'notes_chat',
    getScopeKey,
    serializeScope,
  });
}
