import { useState, useEffect, useCallback } from 'react';

export function useTTS(ttsAudio, messages, selectedInstance, onTtsPlayed) {
  const [messageTtsMap, setMessageTtsMap] = useState({});
  const [pendingTtsAudio, setPendingTtsAudio] = useState(null);

  useEffect(() => {
    if (ttsAudio && ttsAudio.instanceId === selectedInstance?.id) {
      setPendingTtsAudio({
        audioData: ttsAudio.audioData,
        format: ttsAudio.format,
        text: ttsAudio.text,
        durationMs: ttsAudio.durationMs
      });
      if (onTtsPlayed) onTtsPlayed();
    }
  }, [ttsAudio, selectedInstance?.id, onTtsPlayed]);

  useEffect(() => {
    if (pendingTtsAudio && messages.length > 0) {
      const lastAssistantMsg = [...messages].reverse().find(m => m.role === 'assistant');
      if (lastAssistantMsg && lastAssistantMsg.id) {
        setMessageTtsMap(prev => ({
          ...prev,
          [lastAssistantMsg.id]: pendingTtsAudio
        }));
        setPendingTtsAudio(null);
      }
    }
  }, [messages, pendingTtsAudio]);

  const clearTTS = useCallback((messageId) => {
    setMessageTtsMap(prev => {
      const newMap = { ...prev };
      delete newMap[messageId];
      return newMap;
    });
  }, []);

  const loadTTSFromMessages = useCallback((messages) => {
    const ttsMapFromMessages = {};
    messages.forEach(msg => {
      if (msg.metadata?.tts) {
        const tts = msg.metadata.tts;
        ttsMapFromMessages[msg.id] = {
          audioData: tts.audio || tts.audioData,
          format: tts.format,
          text: tts.text,
          durationMs: tts.duration_ms || tts.durationMs
        };
      }
    });
    if (Object.keys(ttsMapFromMessages).length > 0) {
      setMessageTtsMap(prev => ({ ...prev, ...ttsMapFromMessages }));
    }
  }, []);

  return {
    messageTtsMap,
    clearTTS,
    loadTTSFromMessages
  };
}
