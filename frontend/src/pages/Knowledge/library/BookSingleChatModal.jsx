import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Empty, Input, Modal, Select, Space, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import useBookSingleRoom from './useBookSingleRoom';

export default function BookSingleChatModal({ detail, sendWSMessage, onClose, group = false, onAddMembers, refreshRevision = 0 }) {
  const { t } = useTranslation();
  const chat = useBookSingleRoom(detail, sendWSMessage);
  const refreshChat = chat.refresh;
  const [draft, setDraft] = useState('');
  const [evidence, setEvidence] = useState(null);
  const [evidenceError, setEvidenceError] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [resetOpen, setResetOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [speakerMode, setSpeakerMode] = useState('natural');
  const [targets, setTargets] = useState([]);
  const anchor = useRef(null);
  const generation = useRef(0);
  const evidenceRevision = useRef(0);
  const round = chat.round;
  const active = ['queued', 'running', 'paused', 'interrupted'].includes(round?.status);
  const available = chat.room?.status === 'active' && chat.room.members.some((member) => member.available && member.active && member.speaking_mode !== 'muted');
  const eligible = chat.room?.members.filter((member) => member.available && member.active && member.speaking_mode !== 'muted') || [];
  const speakerLabel = (message) => message.speaker_type === 'user' ? t('bookRoom.you') : group ? `${message.identity.name} · ${message.identity.book_title} · ${message.speaker_member_id?.slice(0, 6)}` : message.identity.name;
  const canSend = available && (!group || speakerMode === 'all' || (speakerMode === 'natural' ? eligible.some((member) => member.speaking_mode === 'auto') : targets.length > 0 && targets.every((id) => eligible.some((member) => member.id === id))));

  useEffect(() => { if (refreshRevision) refreshChat().catch((failure) => setEvidenceError(failure.message)); }, [refreshRevision, refreshChat]);

  useEffect(() => {
    generation.current += 1;
    return () => { generation.current += 1; evidenceRevision.current += 1; };
  }, []);

  useEffect(() => {
    const key = `${round?.round_id}:${round?.execution_window}:${round?.run_started_at}`;
    if (round?.status !== 'running') { anchor.current = null; return undefined; }
    if (!anchor.current || anchor.current.key !== key) anchor.current = { key, start: performance.now(), base: round.elapsedSeconds || 0 };
    const update = () => setSeconds(Math.min(round.timeLimitSeconds, anchor.current.base + (performance.now() - anchor.current.start) / 1000));
    const timer = setInterval(update, 200);
    return () => clearInterval(timer);
  }, [round?.round_id, round?.status, round?.execution_window, round?.run_started_at, round?.timeLimitSeconds, round?.elapsedSeconds]);

  const send = async () => { if (await chat.act('submit_turn', draft.trim(), group ? { mode: speakerMode, ...(speakerMode === 'directed' ? { target_member_ids: targets } : {}) } : {})) setDraft(''); };
  const openEvidence = async (id) => {
    const current = generation.current;
    const revision = ++evidenceRevision.current;
    setEvidenceError('');
    try {
      const result = await chat.evidence(id);
      if (current === generation.current && revision === evidenceRevision.current) setEvidence(result.evidence);
    } catch (failure) { if (current === generation.current && revision === evidenceRevision.current) setEvidenceError(failure.message); }
  };
  const resetMemory = async () => {
    generation.current += 1;
    evidenceRevision.current += 1;
    setEvidence(null); setEvidenceError(''); setMemoryOpen(false);
    if (await chat.act('reset_memory')) { setDraft(''); setResetOpen(false); }
  };

  return <Modal open title={`${detail.public.name} · ${t('bookRoom.title')}`} width={800} onCancel={onClose} footer={<Button onClick={onClose}>{t('bookWorld.closeArchive')}</Button>}>
    <Alert type="info" showIcon title={t('bookRoom.hint')} style={{ marginBottom: 12 }} />
    {chat.error && <Alert type="error" showIcon title={chat.error} />}
    {evidenceError && <Alert type="error" showIcon title={evidenceError} />}
    {chat.room && !available && <Alert type="warning" title={t('bookRoom.sourceUnavailable')} />}
    {chat.room && !chat.models.length && <Alert type="warning" title={t('bookRoom.noModels')} />}
    <Select aria-label={t('bookRoom.model')} placeholder={t('bookRoom.model')} value={chat.modelKey} onChange={chat.setModelKey} disabled={chat.busy || active} style={{ width: '100%', margin: '10px 0' }} options={chat.models.map((entry) => ({ value: `${entry.provider_id}:${entry.model_record_id}`, label: entry.label }))} />
    <small>{t('bookRoom.modelHint')}</small>
    {group && <section aria-label={t('bookRoom.members')} style={{ padding: '10px 0' }}>
      <strong>{t('bookRoom.members')}</strong>
      {chat.room?.members.map((member) => <div key={member.id} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', margin: '8px 0' }}>
        <span>{member.identity.name} · {member.identity.book_title} · {member.id.slice(0, 6)}</span>
        <Select aria-label={t('bookRoom.memberMode', { name: member.identity.name, id: member.id.slice(0, 6) })} size="small" value={member.speaking_mode} disabled={chat.busy || !member.active} style={{ width: 110 }} onChange={(speaking_mode) => chat.act('set_member', null, { member_id: member.id, speaking_mode })} options={['auto', 'mention_only', 'muted'].map((value) => ({ value, label: t(`bookRoom.speaking.${value}`) }))} />
        {member.active ? <Button danger size="small" disabled={chat.busy} onClick={() => chat.act('set_member', null, { member_id: member.id, active: false })}>{t('bookRoom.remove')}</Button> : <Button size="small" disabled={chat.busy || active || !member.available} onClick={() => chat.act('set_member', null, { member_id: member.id, active: true })}>{t('bookRoom.rejoin')}</Button>}
        {!member.available && <Tag>{t('bookRoom.sourceUnavailable')}</Tag>}
      </div>)}
      <Button size="small" disabled={!chat.room || chat.busy || active || chat.room.status !== 'active'} onClick={() => onAddMembers?.(chat.room)}>{t('bookRoom.addMembers')}</Button>
      <p>{t('bookRoom.naturalHint')}</p>
      <Select aria-label={t('bookRoom.speakerMode')} value={active ? round.mode : speakerMode} disabled={chat.busy || active} onChange={setSpeakerMode} style={{ width: 150 }} options={['natural', 'directed', 'all'].map((value) => ({ value, label: t(`bookRoom.selection.${value}`) }))} />
      {(active ? round.mode : speakerMode) === 'directed' && <Select aria-label={t('bookRoom.mention')} mode="multiple" placeholder={t('bookRoom.mention')} value={targets} disabled={chat.busy || active} onChange={setTargets} optionFilterProp="label" style={{ width: '100%', marginTop: 8 }} options={eligible.map((member) => ({ value: member.id, label: `${member.identity.name} · ${member.identity.book_title} · ${member.id.slice(0, 6)}` }))} />}
    </section>}
    <div style={{ margin: '8px 0' }}>
      <Button size="small" disabled={!chat.room || chat.busy} onClick={() => setResetOpen(true)}>{t('bookRoom.reset')}</Button>
      {chat.memory && <Button type="link" size="small" onClick={() => setMemoryOpen(true)}>{t('bookRoom.memoryCount', { count: chat.memory.items.length })}</Button>}
    </div>
    <div aria-label={t('bookRoom.messages')} style={{ maxHeight: '45vh', overflowY: 'auto', padding: '8px 0' }}>
      {!chat.messages.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('bookRoom.empty')} />}
      {chat.messages.map((message) => <article key={message.id} id={`book-room-message-${message.id}`} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
        <strong>{speakerLabel(message)}</strong>
        {group && message.reply_to_id && <div><Button type="link" size="small" onClick={() => document.getElementById(`book-room-message-${message.reply_to_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })}>{t('bookRoom.replyTo', { name: chat.messages.find((entry) => entry.id === message.reply_to_id) ? speakerLabel(chat.messages.find((entry) => entry.id === message.reply_to_id)) : message.reply_to_id.slice(0, 6) })}</Button></div>}
        <p style={{ whiteSpace: 'pre-wrap', margin: '6px 0' }}>{message.content}</p>
        {message.refs.length > 0 && <Button type="link" size="small" onClick={() => openEvidence(message.id)}>{t('bookRoom.evidence')}</Button>}
      </article>)}
    </div>
    {round && <div style={{ margin: '10px 0' }}>
      <Tag>{t(`bookRoom.status.${round.status}`)}</Tag>
      <span>{t('bookRoom.window', { window: round.executionWindow, limit: round.timeLimitSeconds, remaining: Math.max(0, Math.ceil(round.timeLimitSeconds - (round.status === 'running' ? seconds : round.elapsedSeconds))) })}</span>
      {round.generation && <p role="status">{t('bookRoom.generationProgress', { name: chat.room?.members.find((member) => member.id === round.generation.member_id)?.identity.name, phase: t(`bookRoom.phase.${round.generation.phase}`) })}</p>}
      {round.error_code && <Alert type="warning" title={t(`bookRoom.error.${round.error_code}`, { defaultValue: round.error_code })} />}
      {group && <ul>{round.slots.map((slot) => <li key={slot.id}>{chat.room?.members.find((member) => member.id === slot.member_id)?.identity.name} · {slot.member_id.slice(0, 6)} · {t(`bookRoom.slot.${slot.status}`, { defaultValue: slot.status })}{slot.skip_reason && ` · ${t(`bookRoom.skip.${slot.skip_reason}`, { defaultValue: slot.skip_reason })}`}</li>)}</ul>}
      <Space style={{ marginTop: 8 }}>
        {(round.can_resume || round.status === 'failed') && <Button size="small" disabled={chat.busy || !available} onClick={() => chat.act('resume_round')}>{t('bookRoom.resume')}</Button>}
        {['queued', 'running'].includes(round.status) && <Button size="small" disabled={chat.busy} onClick={() => chat.act('pause_round')}>{t('bookRoom.pause')}</Button>}
        {active && <Button size="small" disabled={chat.busy} onClick={() => chat.act('cancel_round')}>{t('bookRoom.stop')}</Button>}
      </Space>
    </div>}
    <Input.TextArea aria-label={t('bookRoom.question')} placeholder={t('bookRoom.question')} value={draft} onChange={(event) => setDraft(event.target.value)} rows={3} maxLength={4000} disabled={!chat.room || chat.busy || active || !available} />
    <Space style={{ marginTop: 8 }}>
      <Button type="primary" loading={chat.busy} disabled={!draft.trim() || active || !canSend || !chat.modelKey} onClick={send}>{t('bookRoom.send')}</Button>
      <Button disabled={chat.busy} onClick={() => chat.refresh().catch((failure) => setEvidenceError(failure.message))}>{t('bookWorld.refreshBuild')}</Button>
    </Space>
    <Modal open={resetOpen} title={t('bookRoom.resetTitle')} onOk={resetMemory} onCancel={() => setResetOpen(false)} confirmLoading={chat.busy} okText={t('bookRoom.reset')} cancelText={t('bookRoom.keepMemory')}>
      <p>{t('bookRoom.resetHint')}</p>
    </Modal>
    <Modal open={memoryOpen && chat.memory !== null} title={t('bookRoom.memoryTitle')} onCancel={() => setMemoryOpen(false)} footer={null}>
      {(chat.memory?.items || []).map((item, index) => <article key={index} style={{ marginBottom: 12 }}>
        <strong>{item.speaker_type === 'user' ? t('bookRoom.you') : chat.room?.members.find((member) => member.id === item.speaker_member_id)?.identity.name}</strong>
        <p><Tag>{t(`bookRoom.origin.${item.origin}`)}</Tag>{item.text}</p>
        {item.source_message_ids.map((id) => {
          const source = chat.messages.find((message) => message.id === id);
          return source && <blockquote key={id} style={{ whiteSpace: 'pre-wrap' }}>{source.content}</blockquote>;
        })}
      </article>)}
    </Modal>
    <Modal open={evidence !== null} title={t('bookRoom.evidence')} onCancel={() => { evidenceRevision.current += 1; setEvidence(null); }} footer={null}>
      <Alert type="info" title={t('bookRoom.readerEvidence')} />
      {(evidence || []).map((item) => <article key={item.id} style={{ padding: '8px 0' }}>
        <Tag>{t(`bookRoom.origin.${item.origin}`)}</Tag><p>{item.assertion_text}</p>
        {item.origin === 'room_hearsay' ? <p>{t('bookRoom.heardSource', { id: item.heard_message_id?.slice(0, 8) })}</p> : <>
          <small>{item.title_snapshot} · {item.segment_id?.slice(0, 8)} · {item.local_start}–{item.local_end}</small>
          {item.source_available ? <blockquote style={{ whiteSpace: 'pre-wrap' }}>{item.quote_text}</blockquote> : <p>{t('bookRoom.sourceUnavailable')}</p>}
        </>}
      </article>)}
    </Modal>
  </Modal>;
}
