import { useCallback, useEffect, useRef, useState } from 'react';

export default function useBookSingleRoom(detail, sendWSMessage) {
  const [room, setRoom] = useState(null);
  const [messages, setMessages] = useState([]);
  const [round, setRound] = useState(null);
  const [memory, setMemory] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [models, setModels] = useState([]);
  const [modelKey, setModelKey] = useState(null);
  const generation = useRef(0);
  const revision = useRef(0);
  const roomRef = useRef(null);
  const historyRef = useRef({ key: null, messages: [] });
  const requestId = useRef(crypto.randomUUID());
  const pendingTurn = useRef(null);
  const modelTouched = useRef(false);

  const request = useCallback(async (action, values = {}) => {
    const response = await sendWSMessage('book_room', { action, workspace_id: detail.workspace_id, ...values }, 120000);
    if (response.type === 'error') {
      const failure = new Error(response.data.error);
      failure.code = response.data.code;
      throw failure;
    }
    return response.data;
  }, [detail.workspace_id, sendWSMessage]);

  const refresh = useCallback(async (identity) => {
    const current = generation.current;
    const sequence = ++revision.current;
    const valid = () => current === generation.current && sequence === revision.current;
    try {
      const snapshot = await request('get_room', identity);
      if (!valid()) return;
      const job = snapshot.latest_round_id ? await request('get_round', { ...identity, round_id: snapshot.latest_round_id }) : null;
      if (!valid()) return;
      const recalled = await request('get_memory', identity);
      if (!valid()) return;
      const key = `${snapshot.workspace_id}:${identity.room_id}:${identity.expected_epoch}`;
      const history = historyRef.current.key === key ? [...historyRef.current.messages] : [];
      let cursor = history.at(-1)?.seq || 0;
      do {
        const page = await request('read_messages', { ...identity, after_seq: cursor, limit: 100 });
        if (!valid()) return;
        const ids = new Set(history.map((message) => message.id));
        history.push(...page.messages.filter((message) => !ids.has(message.id)));
        cursor = page.next_seq;
      } while (cursor !== null);
      roomRef.current = { ...identity, workspace_id: snapshot.workspace_id };
      historyRef.current = { key, messages: history };
      setRoom(snapshot); setMessages(history); setRound(job); setMemory(recalled.memory);
      if (job?.generation_config?.model_record_id && (!modelTouched.current || ['queued', 'running', 'paused', 'interrupted'].includes(job.status))) setModelKey(`${job.generation_config.provider_id}:${job.generation_config.model_record_id}`);
    } catch (failure) {
      if (valid()) {
        if (failure.code === 'invalid_scope') {
          roomRef.current = null; historyRef.current = { key: null, messages: [] };
          setRoom(null); setMessages([]); setRound(null); setMemory(null);
        }
        throw failure;
      }
    }
  }, [request]);

  useEffect(() => {
    const current = ++generation.current;
    Promise.resolve().then(async () => {
      if (current !== generation.current) return;
      const choices = await request('list_chat_models');
      if (current !== generation.current) return;
      setModels(choices.models);
      if (choices.models.length) setModelKey(`${choices.models[0].provider_id}:${choices.models[0].model_record_id}`);
      const created = detail.room_id ? { room_id: detail.room_id, epoch: detail.epoch } : await request('create_single_room', { item_id: detail.item_id, build_id: detail.build_id, character_id: detail.character_id, client_room_id: requestId.current, reuse_existing: true });
      if (current !== generation.current) return;
      await refresh({ room_id: created.room_id, expected_epoch: created.epoch });
    }).catch((failure) => { if (current === generation.current) setError(failure.message); });
    return () => { generation.current += 1; revision.current += 1; };
  }, [detail.item_id, detail.build_id, detail.character_id, detail.room_id, detail.epoch, request, refresh]);

  useEffect(() => {
    if (!roomRef.current || busy) return undefined;
    let stopped = false;
    let timer;
    const poll = async () => {
      try { await refresh(roomRef.current); if (!stopped) setPollError(''); }
      catch (failure) { if (!stopped) setPollError(failure.message); }
      if (!stopped) timer = setTimeout(poll, ['queued', 'running'].includes(round?.status) ? 1000 : 5000);
    };
    timer = setTimeout(poll, 500);
    return () => { stopped = true; clearTimeout(timer); };
  }, [round?.status, room?.room_id, busy, refresh]);

  const act = async (operation, content, controls = {}) => {
    if (!roomRef.current) return false;
    const current = operation === 'reset_memory' ? ++generation.current : generation.current;
    revision.current += 1;
    setBusy(true); setError('');
    try {
      let values;
      if (operation === 'submit_turn') {
        const signature = JSON.stringify({ content, controls });
        if (!pendingTurn.current || pendingTurn.current.signature !== signature) pendingTurn.current = { signature, values: { client_turn_id: crypto.randomUUID(), content, ...controls } };
        values = pendingTurn.current.values;
        const model = models.find((entry) => `${entry.provider_id}:${entry.model_record_id}` === modelKey);
        if (model) values = { ...values, provider_id: model.provider_id, model_record_id: model.model_record_id };
      } else values = ['set_member', 'add_members', 'retry_source_cleanup'].includes(operation) ? controls : operation === 'reset_memory' ? {} : { round_id: round.round_id };
      const result = await request(operation, { ...roomRef.current, ...values });
      if (current !== generation.current) return false;
      if (operation === 'reset_memory') {
        roomRef.current = { room_id: result.room_id, expected_epoch: result.epoch, workspace_id: result.workspace_id };
        pendingTurn.current = null;
        historyRef.current = { key: null, messages: [] };
        setMessages([]); setRound(null); setMemory(null); setRoom(result);
      }
      await refresh(roomRef.current);
      if (operation === 'submit_turn') pendingTurn.current = null;
      return true;
    } catch (failure) { if (current === generation.current) setError(failure.message); return false; }
    finally { if (current === generation.current) setBusy(false); }
  };

  const evidence = async (messageId) => request('get_message_evidence', { ...roomRef.current, message_id: messageId });
  const chooseModel = (value) => { modelTouched.current = true; setModelKey(value); };
  const refreshCurrent = useCallback(() => roomRef.current && refresh(roomRef.current), [refresh]);
  return { room, messages, round: pollError && round ? { ...round, generation: null } : round, memory, busy, error: error || pollError, models, modelKey, setModelKey: chooseModel, act, evidence, refresh: refreshCurrent };
}
