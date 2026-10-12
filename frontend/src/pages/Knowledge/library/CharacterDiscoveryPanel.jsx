import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Progress, Tag } from 'antd';
import { useTranslation } from 'react-i18next';

export default function CharacterDiscoveryPanel({ source, request, onLocate }) {
  const { t } = useTranslation();
  const [build, setBuild] = useState(null);
  const [characters, setCharacters] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const generation = useRef(0);
  const revision = useRef(0);
  const version = source?.source_version_id;
  const active = build?.stage === 'character_discovery' && ['queued', 'running'].includes(build?.status);

  const refresh = useCallback(async (buildId, page = 0) => {
    const current = generation.current;
    const sequence = ++revision.current;
    const data = await request('get_build', { source_version_id: version, ...(buildId ? { build_id: buildId } : {}) });
    const catalog = data.build_id ? await request('list_characters', { build_id: data.build_id, offset: page, limit: 25 }) : null;
    if (current !== generation.current || sequence !== revision.current) return;
    setBuild(data); setCharacters(catalog?.characters || []); setTotal(catalog?.total || 0); setOffset(page); setError('');
  }, [request, version]);

  useEffect(() => {
    const current = ++generation.current;
    revision.current += 1;
    setBuild(null); setCharacters([]); setTotal(0); setOffset(0); setBusy(false); setError('');
    if (version) refresh().catch((failure) => { if (current === generation.current) setError(failure.message); });
    return () => { generation.current += 1; };
  }, [refresh, version]);

  useEffect(() => {
    if (!active || busy) return undefined;
    let stopped = false;
    let timer;
    const poll = async () => {
      try { await refresh(build.build_id, offset); }
      catch (failure) { if (!stopped) setError(failure.message); }
      if (!stopped) timer = setTimeout(poll, 2000);
    };
    timer = setTimeout(poll, 2000);
    return () => { stopped = true; clearTimeout(timer); revision.current += 1; };
  }, [active, busy, build?.build_id, refresh, offset]);

  const act = async (action) => {
    const current = generation.current;
    revision.current += 1;
    setBusy(true); setError('');
    try {
      const data = await request(action, { source_version_id: version, ...(action === 'start_discovery' ? {} : { build_id: build.build_id }) });
      if (current !== generation.current) return;
      await refresh(data.build_id);
    } catch (failure) { if (current === generation.current) setError(failure.message); }
    finally { if (current === generation.current) setBusy(false); }
  };

  return <details style={{ marginTop: 12 }}>
    <summary style={{ cursor: 'pointer', fontSize: 13 }}>{t('bookWorld.characterTitle')}</summary>
    <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t('bookWorld.candidateHint')}</p>
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
      <Button size="small" disabled={source?.status !== 'ready' || active || busy} onClick={() => act('start_discovery')}>{t('bookWorld.discover')}</Button>
      {active && <Button size="small" disabled={busy} onClick={() => act('cancel_build')}>{t('bookWorld.cancelBuild')}</Button>}
      {['failed', 'cancelled'].includes(build?.status) && <Button size="small" disabled={busy} onClick={() => act('retry_build')}>{t('bookWorld.retryBuild')}</Button>}
      {build?.can_resume && <Button size="small" disabled={busy} onClick={() => act('resume_build')}>{t('bookWorld.resumeBuild')}</Button>}
      {build?.build_id && <Button size="small" disabled={busy} onClick={() => refresh(build.build_id, offset).catch((failure) => setError(failure.message))}>{t('bookWorld.refreshBuild')}</Button>}
    </div>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 8 }} />}
    {build?.build_id && <>
      <Tag color={build.stage === 'discovery_complete' ? 'green' : build.status === 'failed' ? 'red' : 'blue'}>{build.stage === 'discovery_complete' ? t('bookWorld.discoveryComplete') : t(`bookWorld.buildStatus.${build.status}`)}</Tag>
      <span style={{ fontSize: 12 }}>{t('bookWorld.buildProgress', { completed: build.completed_units, total: build.total_units, processed: build.processed_segments, segments: build.total_segments })}</span>
      <Progress size="small" percent={build.total_units ? Math.round(100 * build.completed_units / build.total_units) : 0} status={build.status === 'failed' ? 'exception' : active ? 'active' : 'normal'} />
      {build.error_detail && <Alert type="warning" showIcon title={build.error_detail} style={{ marginBottom: 8 }} />}
      <p style={{ fontSize: 12 }}>{t('bookWorld.candidateCount', { count: total })}</p>
      <ul style={{ listStyle: 'none', padding: 0, maxHeight: 360, overflowY: 'auto' }}>
        {characters.map((character) => <li key={character.id} style={{ borderBottom: '1px solid var(--border)', padding: '8px 0', fontSize: 12 }}>
          <strong>{character.name}</strong> <Tag color={character.agent_status === 'needs_review' ? 'orange' : 'default'}>{t(`bookWorld.characterStatus.${character.agent_status}`)}</Tag>
          <div>{character.aliases.map((alias) => <span key={alias.alias} style={{ marginRight: 8 }}>
            {alias.alias}{alias.review_state === 'ambiguous' ? ` · ${t('bookWorld.ambiguousAlias')}` : ''}
            <Button size="small" type="link" onClick={() => onLocate(alias.evidence)}>{t('bookWorld.candidateEvidence')}</Button>
          </span>)}</div>
          <span style={{ color: 'var(--text-muted)' }}>{[...new Set(character.appearances.map((appearance) => t(`bookWorld.presence.${appearance.presence}`)))].join(' / ')}</span>
        </li>)}
      </ul>
      <div style={{ display: 'flex', gap: 8 }}>
        <Button size="small" disabled={offset === 0} onClick={() => refresh(build.build_id, Math.max(0, offset - 25)).catch((failure) => setError(failure.message))}>{t('bookWorld.previousCharacters')}</Button>
        <Button size="small" disabled={offset + characters.length >= total} onClick={() => refresh(build.build_id, offset + 25).catch((failure) => setError(failure.message))}>{t('bookWorld.nextCharacters')}</Button>
      </div>
    </>}
  </details>;
}
