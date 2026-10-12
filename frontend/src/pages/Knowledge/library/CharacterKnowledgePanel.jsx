import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Checkbox, Empty, Input, Progress, Select, Space, Tag } from 'antd';
import { useTranslation } from 'react-i18next';

export default function CharacterKnowledgePanel({ detail, request, onLocate }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [action, setAction] = useState('other');
  const [retrospective, setRetrospective] = useState(false);
  const [preview, setPreview] = useState(null);
  const [job, setJob] = useState(null);
  const [materials, setMaterials] = useState([]);
  const [nextOffset, setNextOffset] = useState(null);
  const [busy, setBusy] = useState(false);
  const [queryBusy, setQueryBusy] = useState(false);
  const [error, setError] = useState('');
  const generation = useRef(0);
  const jobRevision = useRef(0);
  const previewRevision = useRef(0);
  const identity = { build_id: detail.build_id, character_id: detail.character_id };

  const refreshJob = useCallback(async () => {
    const current = generation.current;
    const revision = ++jobRevision.current;
    const result = await request('get_expression_set', { build_id: detail.build_id, character_id: detail.character_id });
    const catalog = result.set_id ? await request('list_expression_materials', { build_id: detail.build_id, character_id: detail.character_id, expression_set_id: result.set_id, limit: 50 }) : null;
    if (current !== generation.current || revision !== jobRevision.current) return;
    setJob(result); setMaterials(catalog?.materials || []); setNextOffset(catalog?.next_offset ?? null);
  }, [request, detail.build_id, detail.character_id]);

  useEffect(() => {
    const current = ++generation.current;
    Promise.resolve().then(() => { if (current === generation.current) return refreshJob(); }).catch((failure) => { if (current === generation.current) setError(failure.message); });
    return () => { generation.current += 1; };
  }, [refreshJob]);

  useEffect(() => {
    if (busy || !['queued', 'running'].includes(job?.status)) return undefined;
    let stopped = false;
    let timer;
    const poll = async () => {
      try { await refreshJob(); }
      catch (failure) { if (!stopped) setError(failure.message); }
      if (!stopped) timer = setTimeout(poll, 2000);
    };
    timer = setTimeout(poll, 2000);
    return () => { stopped = true; clearTimeout(timer); };
  }, [busy, job?.status, refreshJob]);

  const search = async () => {
    const current = generation.current;
    const revision = ++previewRevision.current;
    setQueryBusy(true); setError('');
    try {
      const result = await request('preview_knowledge', { ...identity, query: query.trim(), retrospective, dialogue_action: action });
      if (current === generation.current && revision === previewRevision.current) setPreview(result);
    } catch (failure) { if (current === generation.current && revision === previewRevision.current) setError(failure.message); }
    finally { if (current === generation.current && revision === previewRevision.current) setQueryBusy(false); }
  };

  const act = async (operation) => {
    const current = generation.current;
    jobRevision.current += 1;
    setBusy(true); setError('');
    try {
      await request(operation, { ...identity, ...(operation === 'start_expression_set' ? {} : { expression_set_id: job.set_id }) });
      if (current === generation.current) await refreshJob();
    } catch (failure) { if (current === generation.current) setError(failure.message); }
    finally { if (current === generation.current) setBusy(false); }
  };

  const changeQuery = (value) => {
    previewRevision.current += 1; setQueryBusy(false); setPreview(null); setQuery(value);
  };
  const moreMaterials = async () => {
    const current = generation.current;
    const revision = ++jobRevision.current;
    try {
      const result = await request('list_expression_materials', { ...identity, expression_set_id: job.set_id, offset: nextOffset, limit: 50 });
      if (current === generation.current && revision === jobRevision.current) {
        setMaterials((old) => [...old, ...result.materials]); setNextOffset(result.next_offset);
      }
    } catch (failure) { if (current === generation.current) setError(failure.message); }
  };

  return <section aria-label={t('bookWorld.knowledgeTitle')} style={{ margin: '14px 0', padding: 12, border: '1px solid var(--border)', borderRadius: 8 }}>
    <h4 style={{ marginTop: 0 }}>{t('bookWorld.knowledgeTitle')}</h4>
    <p style={{ fontSize: 12 }}>{t('bookWorld.knowledgeHint')}</p>
    {error && <Alert type="error" showIcon title={error} />}
    <Input.Search aria-label={t('bookWorld.knowledgeQuery')} placeholder={t('bookWorld.knowledgeQuery')} value={query}
      onChange={(event) => changeQuery(event.target.value)} maxLength={1000} loading={queryBusy} enterButton={t('bookWorld.previewKnowledge')} onSearch={search} />
    <Space style={{ marginTop: 8, marginBottom: 8 }} wrap>
      <Checkbox checked={retrospective} onChange={(event) => { previewRevision.current += 1; setPreview(null); setQueryBusy(false); setRetrospective(event.target.checked); }}>{t('bookWorld.retrospective')}</Checkbox>
      <Select aria-label={t('bookWorld.expressionAction')} style={{ minWidth: 150 }} value={action} onChange={(value) => { previewRevision.current += 1; setPreview(null); setQueryBusy(false); setAction(value); }}
        options={['other', 'answer', 'ask', 'challenge', 'comfort', 'avoid', 'greet', 'disagree', 'express_unknown'].map((value) => ({ value, label: t(`bookWorld.expressionActionType.${value}`) }))} />
    </Space>
    {preview && <>
      <Alert type={preview.knowledge.items.length ? 'success' : 'info'} showIcon title={t(preview.knowledge.items.length ? 'bookWorld.knowledgeMatched' : 'bookWorld.knowledgeUnknown')} />
      {preview.knowledge.items.map((item) => <article key={`${item.claim_id}:${item.evidence_id}`} style={{ padding: '8px 0' }}>
        <Tag>{t(`bookWorld.claimKind.${item.kind}`)}</Tag><Tag>{t(`bookWorld.knowledgeTime.${item.temporal_state}`)}</Tag>
        <p style={{ margin: '4px 0' }}>{item.proposition}</p>{item.approved_excerpt ? <blockquote style={{ whiteSpace: 'pre-wrap' }}>{item.approved_excerpt}</blockquote> : <p style={{ fontSize: 12 }}>{t('bookWorld.propositionOnly')}</p>}
        <Button type="link" size="small" onClick={() => onLocate(item)}>{t('bookWorld.candidateEvidence')}</Button>
      </article>)}
      <h5>{t('bookWorld.selectedExpression')}</h5>
      {![...preview.expression.rules, ...preview.expression.examples].length && <p>{t('bookWorld.noExpression')}</p>}
      {[...preview.expression.rules, ...preview.expression.examples].map((item) => <blockquote key={item.material_id} style={{ whiteSpace: 'pre-wrap' }}>{item.text}</blockquote>)}
    </>}
    <h5>{t('bookWorld.expressionMaterials')}</h5>
    <Space wrap>
      <Button size="small" disabled={busy || ['queued', 'running'].includes(job?.status)} loading={busy} onClick={() => act('start_expression_set')}>{t('bookWorld.prepareExpressions')}</Button>
      {['queued', 'running', 'paused'].includes(job?.status) && <Button size="small" disabled={busy} onClick={() => act('cancel_expression_set')}>{t('bookWorld.cancelBuild')}</Button>}
      {(job?.can_resume || ['failed', 'cancelled'].includes(job?.status)) && <Button size="small" disabled={busy} onClick={() => act(job.can_resume ? 'resume_expression_set' : 'retry_expression_set')}>{t('bookWorld.resumeExpressions')}</Button>}
      <Button size="small" disabled={busy} onClick={() => refreshJob().catch((failure) => setError(failure.message))}>{t('bookWorld.refreshBuild')}</Button>
    </Space>
    {job && <div style={{ marginTop: 8 }}>
      <Tag>{t(`bookWorld.expressionStatus.${job.status}`)}</Tag>
      {job.set_id && <><span style={{ fontSize: 12 }}>{t('bookWorld.expressionProgress', { completed: job.completed_units, total: job.total_units, accepted: job.accepted_materials })}</span>
        <Progress size="small" percent={job.total_units ? Math.round(100 * job.completed_units / job.total_units) : 100} />
        {job.error_detail && <Alert type="warning" showIcon title={job.error_detail} />}</>}
      {['ready', 'partial'].includes(job.status) && !job.accepted_materials && <p style={{ fontSize: 12 }}>{t('bookWorld.expressionRebuildHint')}</p>}
    </div>}
    {!materials.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('bookWorld.noExpression')} />}
    <div style={{ maxHeight: 250, overflowY: 'auto' }}>
      {materials.map((material) => <article key={material.id} style={{ borderBottom: '1px solid var(--border)', padding: '8px 0' }}>
        <Tag>{t(`bookWorld.expressionKind.${material.kind}`)}</Tag><Tag color={material.review_state === 'accepted' ? 'green' : 'orange'}>{t(`bookWorld.supportState.${material.review_state}`)}</Tag>
        <p style={{ whiteSpace: 'pre-wrap', margin: '4px 0' }}>{material.text}</p>
        {material.review.reason && <p style={{ fontSize: 12 }}>{material.review.reason}</p>}
        {material.refs.map((ref) => <Button key={`${ref.claim_id}:${ref.evidence_id}:${ref.purpose}`} type="link" size="small" onClick={() => onLocate(ref)}>{t('bookWorld.candidateEvidence')}</Button>)}
      </article>)}
    </div>
    {nextOffset !== null && <Button size="small" onClick={moreMaterials}>{t('bookWorld.more')}</Button>}
  </section>;
}
