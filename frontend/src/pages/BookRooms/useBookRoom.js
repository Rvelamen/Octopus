import { useEffect, useMemo, useState } from 'react';
import useBookSingleRoom from '../Knowledge/library/useBookSingleRoom';
import { projectRoomScene } from './sceneProjection.mjs';

export default function useBookRoom(detail, sendWSMessage, connectionStatus, connectionIdentity) {
  const chat = useBookSingleRoom(detail, sendWSMessage, connectionStatus, connectionIdentity);
  const [now, setNow] = useState(() => performance.now());
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [historyMessage, setHistoryMessage] = useState(null);
  const [pinned, setPinned] = useState(null);
  const animationDeadline = useMemo(() => chat.messages.reduce((deadline, message) => chat.liveAt[message.id] === undefined ? deadline : Math.max(deadline, chat.liveAt[message.id] + 8000 + message.content.length * 12), historyMessage?.until || 0), [chat.messages, chat.liveAt, historyMessage?.until]);
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(preference.matches);
    preference.addEventListener('change', update);
    return () => { preference.removeEventListener('change', update); };
  }, []);
  useEffect(() => {
    let stopped = false, timer;
    const update = () => { if (!stopped) setNow(performance.now()); };
    Promise.resolve().then(() => {
      if (stopped) return;
      update();
      if (performance.now() < animationDeadline) timer = setInterval(() => { update(); if (performance.now() >= animationDeadline) clearInterval(timer); }, 50);
    });
    return () => { stopped = true; clearInterval(timer); };
  }, [animationDeadline]);
  const key = `${chat.room?.room_id}:${chat.room?.epoch}`;
  const viewingHistory = historyMessage?.key === key && (chat.messages.at(-1)?.seq || 0) <= historyMessage.atSeq && (now < historyMessage.until || pinned === historyMessage.message.id);
  const effectivePinned = historyMessage && !viewingHistory && pinned === historyMessage.message.id ? null : pinned;
  const displayText = message => {
    const started = chat.liveAt[message.id];
    if (started === undefined || reduced || effectivePinned === message.id || ['cancelled', 'paused', 'interrupted', 'failed'].includes(chat.round?.status)) return message.content;
    return message.content.slice(0, Math.max(1, Math.floor((now - started) / 12)));
  };
  const scene = useMemo(() => projectRoomScene(chat.room, chat.round, chat.messages, chat.liveIds), [chat.room, chat.round, chat.messages, chat.liveIds]);
  const latest = new Map();
  const latestPublished = new Map(scene?.messages.map(message => [message.member_id, message]) || []);
  latestPublished.forEach(message => { if (now - chat.liveAt[message.id] < 8000 + message.content.length * 12 || effectivePinned === message.id) latest.set(message.member_id, { ...message, content: displayText(message), historical: false }); });
  if (viewingHistory) {
    const message = historyMessage.message;
    latest.set(message.speaker_member_id, { id: message.id, seq: message.seq, member_id: message.speaker_member_id, content: message.content, historical: true });
  }
  return { ...chat, scene, bubbles: [...latest.values()], displayText, reduced, viewingHistory, showHistory: message => setHistoryMessage({message,key,atSeq:chat.messages.at(-1)?.seq||0,until:performance.now()+15000}), pin: setPinned, clearHistory: () => {setHistoryMessage(null);setPinned(null);} };
}
