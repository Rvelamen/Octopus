import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Space, Tag } from 'antd';
import { useTranslation } from 'react-i18next';

export default function AutoBookImportPanel({ item, sendWSMessage }) {
  const { t } = useTranslation();
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const revision = useRef(0);
  const request = useCallback(async (action, data = {}) => {
    const result = await sendWSMessage('book_world', { action, item_id: item.id, ...data }, 120000);
    if (result.type === 'error') throw new Error(result.data.error);
    return result.data.job;
  }, [item.id, sendWSMessage]);
  const load = useCallback(async () => {
    const current = generation.current;
    const sequence = ++revision.current;
    try {
      const value = await request('get_auto_import');
      if (current === generation.current && sequence === revision.current) setJob(value);
    } catch (failure) { if (current === generation.current && sequence === revision.current) setError(failure.message); }
  }, [request]);
  useEffect(() => {
    generation.current += 1;
    let stopped = false;
    let timer;
    const refresh = async () => { await load(); if (!stopped) timer = setTimeout(refresh, 3000); };
    Promise.resolve().then(refresh);
    return () => { stopped = true; clearTimeout(timer); generation.current += 1; revision.current += 1; };
  }, [load]);
  const act = async action => {
    if (!job) return;
    const current = generation.current;
    revision.current += 1;
    setBusy(true); setError('');
    try {
      const result = await request(action, { workspace_id: job.workspace_id, automatic_job_id: job.job_id });
      if (current === generation.current) { setJob(result); await load(); }
    } catch (failure) { if (current === generation.current) setError(failure.message); }
    finally { if (current === generation.current) setBusy(false); }
  };
  if (!job && !item.metadata?.book_world?.automatic) return null;
  return <section aria-label={t('bookAuto.title')} style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 8, marginBottom: 12 }}>
    <strong>{t('bookAuto.title')}</strong>
    {error && <Alert type="error" showIcon title={error} />}
    {!job ? <p>{t('bookAuto.waitingIntent')}</p> : <>
      <p><Tag>{t(`bookAuto.status.${job.status}`, { defaultValue: job.status })}</Tag>{t(`bookAuto.phase.${job.phase}`, { defaultValue: job.phase })}</p>
      <p>{t('bookAuto.calls', { count: job.actual_calls })}</p>
      {job.error_code && <Alert type="warning" showIcon title={t(`bookAuto.error.${job.error_code}`, { defaultValue: job.error_detail || job.error_code })} />}
      {job.canon_available && <p>{t('bookAuto.canonAvailable')} · <Tag>{t(`bookWorld.buildStatus.${job.canonical_status}`, { defaultValue: job.canonical_status })}</Tag>{job.persona_build_id.slice(0, 8)}</p>}
      {job.expression_sets.length > 0 && <p>{t('bookAuto.expressions', { count: job.expression_sets.length })}</p>}
      {job.expression_sets.length > 0 && <ul>{job.expression_sets.map(entry => <li key={entry.set_id}>{entry.name} · {t(`bookAuto.expressionStatus.${entry.status}`, { defaultValue: entry.status })} · {entry.accepted_materials === 0 ? t('bookAuto.noExpressionEvidence') : t('bookAuto.materials', { count: entry.accepted_materials })}</li>)}</ul>}
      <Space>
        {['queued', 'running', 'waiting_attachment', 'blocked_config', 'interrupted'].includes(job.status) && <Button size="small" disabled={busy} onClick={() => act('cancel_auto_import')}>{t('bookAuto.cancel')}</Button>}
        {['failed', 'cancelled', 'partial', 'interrupted', 'blocked_config', 'needs_ocr'].includes(job.status) && <Button size="small" disabled={busy} onClick={() => act('retry_auto_import')}>{t('bookAuto.retry')}</Button>}
        {['completed', 'failed', 'partial', 'cancelled', 'blocked_config', 'needs_ocr'].includes(job.status) && <Button size="small" disabled={busy} onClick={() => act('restart_auto_import')}>{t('bookAuto.newVersion')}</Button>}
        <Button size="small" disabled={busy} onClick={load}>{t('bookWorld.refreshBuild')}</Button>
      </Space>
    </>}
  </section>;
}
