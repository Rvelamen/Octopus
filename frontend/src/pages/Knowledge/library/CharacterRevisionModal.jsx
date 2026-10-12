import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Input, Modal, Select, Space } from 'antd';
import { useTranslation } from 'react-i18next';

export default function CharacterRevisionModal({ detail, context, request, onClose, onRevised }) {
  const { t } = useTranslation();
  const [operation, setOperation] = useState('add_alias');
  const [value, setValue] = useState('');
  const [target, setTarget] = useState();
  const [claimId, setClaimId] = useState();
  const [segments, setSegments] = useState([]);
  const [segmentId, setSegmentId] = useState();
  const [quote, setQuote] = useState('');
  const [next, setNext] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const generation = useRef(0);
  const pendingRequest = useRef(null);
  const needsTarget = ['merge', 'correct_owner'].includes(operation);
  const editable = context?.head_build_id === detail.build_id;

  const load = useCallback(async (cursor = -1) => {
    const current = generation.current;
    setLoading(true); setError('');
    try {
      const result = await request('list_segments', { source_version_id: context.source_version_id, after_ordinal: cursor, limit: 20 });
      if (current !== generation.current) return;
      setSegments(result.segments); setNext(result.next_ordinal); setSegmentId(undefined); setQuote('');
    } catch (failure) { if (current === generation.current) setError(failure.message); }
    finally { if (current === generation.current) setLoading(false); }
  }, [request, context.source_version_id]);

  useEffect(() => {
    const current = ++generation.current;
    Promise.resolve().then(() => { if (current === generation.current) return load(); });
    return () => { generation.current += 1; };
  }, [load]);

  const submit = async () => {
    const segment = segments.find((row) => row.id === segmentId);
    const start = segment?.text.indexOf(quote) ?? -1;
    if (!quote.trim() || start < 0 || segment.text.indexOf(quote, start + 1) >= 0) {
      setError(t('bookWorld.revisionUniqueQuote')); return;
    }
    const patch = { operation, character_id: detail.character_id, value: needsTarget ? '' : value.trim(),
      ...(needsTarget ? { target_character_id: target } : {}),
      ...(operation === 'correct_owner' ? { claim_id: claimId } : {}),
      evidence: { segment_id: segmentId, quote, local_start: start, local_end: start + quote.length } };
    const payload = { build_id: detail.build_id, expected_revision: context.revision, patches: [patch] };
    const fingerprint = JSON.stringify(payload);
    if (pendingRequest.current?.fingerprint !== fingerprint) pendingRequest.current = { fingerprint, id: crypto.randomUUID() };
    const current = generation.current;
    setBusy(true); setError('');
    try {
      const result = await request('create_revision', { ...payload, revision_request_id: pendingRequest.current.id }, 420000);
      if (current === generation.current) await onRevised(result.build_id);
    } catch (failure) { if (current === generation.current) setError(failure.message); }
    finally { if (current === generation.current) setBusy(false); }
  };

  return <Modal open title={t('bookWorld.revisionTitle', { name: detail.public.name })} width={780} onCancel={onClose}
    footer={<Space><Button onClick={onClose}>{t('bookWorld.closeArchive')}</Button><Button type="primary" loading={busy}
      disabled={!editable || loading || !segmentId || !quote.trim() || (needsTarget ? !target : !value.trim()) || (operation === 'correct_owner' && !claimId)} onClick={submit}>{t('bookWorld.submitRevision')}</Button></Space>}>
    <Alert type={editable ? 'info' : 'warning'} showIcon title={t(editable ? 'bookWorld.revisionHint' : 'bookWorld.revisionStale')} style={{ marginBottom: 12 }} />
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 12 }} />}
    <Space orientation="vertical" style={{ width: '100%' }}>
      <label>{t('bookWorld.revisionOperation')}</label>
      <Select aria-label={t('bookWorld.revisionOperation')} style={{ width: '100%' }} value={operation} onChange={setOperation}
        options={['rename', 'add_alias', 'remove_alias', 'merge', 'correct_owner'].map((op) => ({ value: op, label: t(`bookWorld.revisionOp.${op}`) }))} />
      {needsTarget ? <Select aria-label={t('bookWorld.revisionTarget')} placeholder={t('bookWorld.revisionTarget')} showSearch optionFilterProp="label" style={{ width: '100%' }} value={target} onChange={setTarget}
        options={context.characters.filter((person) => person.id !== detail.character_id).map((person) => ({ value: person.id, label: `${person.name} · ${person.id.slice(0, 6)}` }))} />
        : <Input aria-label={t('bookWorld.revisionName')} placeholder={t('bookWorld.revisionName')} value={value} maxLength={80} onChange={(event) => setValue(event.target.value)} />}
      {operation === 'correct_owner' && <Select aria-label={t('bookWorld.revisionClaim')} placeholder={t('bookWorld.revisionClaim')} style={{ width: '100%' }} value={claimId} onChange={setClaimId}
        options={detail.reader.claims.filter((claim) => claim.owner_character_id === detail.character_id && claim.kind !== 'fact').map((claim) => ({ value: claim.id, label: claim.proposition }))} />}
      <label>{t('bookWorld.revisionSegment')}</label>
      <Select aria-label={t('bookWorld.revisionSegment')} loading={loading} style={{ width: '100%' }} value={segmentId} onChange={(id) => { setSegmentId(id); setQuote(''); }}
        options={segments.map((segment) => ({ value: segment.id, label: `${segment.ordinal + 1} · ${segment.text.slice(0, 55)}` }))} />
      <Space><Button size="small" disabled={loading || busy} onClick={() => load()}>{t('bookWorld.revisionFirstSegments')}</Button>
        <Button size="small" disabled={next === null || loading || busy} onClick={() => load(next)}>{t('bookWorld.more')}</Button></Space>
      {segmentId && <blockquote style={{ margin: '4px 0', maxHeight: 170, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>{segments.find((segment) => segment.id === segmentId)?.text}</blockquote>}
      <Input.TextArea aria-label={t('bookWorld.revisionQuote')} placeholder={t('bookWorld.revisionQuote')} value={quote} maxLength={1400} rows={4} onChange={(event) => setQuote(event.target.value)} />
    </Space>
  </Modal>;
}
