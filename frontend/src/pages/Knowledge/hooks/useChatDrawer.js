import { useState, useEffect, useRef, useCallback } from 'react';

export function useChatDrawer(initialWidth = 480) {
  const [chatOpen, setChatOpen] = useState(false);
  const [chatDrawerWidth, setChatDrawerWidth] = useState(initialWidth);
  const chatResizeStateRef = useRef(null);

  const startChatResize = useCallback((e) => {
    e.preventDefault();
    chatResizeStateRef.current = {
      startX: e.clientX,
      startWidth: chatDrawerWidth,
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [chatDrawerWidth]);

  useEffect(() => {
    const handleMove = (e) => {
      const state = chatResizeStateRef.current;
      if (!state) return;
      const delta = state.startX - e.clientX;
      setChatDrawerWidth(Math.max(280, Math.min(900, state.startWidth + delta)));
    };
    const handleUp = () => {
      chatResizeStateRef.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
    return () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
    };
  }, []);

  return { chatOpen, setChatOpen, chatDrawerWidth, startChatResize };
}
