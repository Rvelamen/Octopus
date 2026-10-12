import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Progress, Select, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import CharacterPersonaModal from './CharacterPersonaModal';
import CharacterRevisionModal from './CharacterRevisionModal';

export default function CharacterDiscoveryPanel({ source, request, onLocate }) {
  const { t } = useTranslation();
  const [build, setBuild] = useState(null);
  const [characters, setCharacters] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [detail, setDetail] = useState(null);
  const [context, setContext] = useState(null);
  const [correcting, setCorrecting] = useState(false);
  const generation = useRef(0);
  const revision = useRef(0);
  const detailRevision = useRef(0);
  const displayedBuild = useRef(null);
  const version = source?.source_version_id;
  const active = ['character_discovery', 'persona_extract'].includes(build?.stage) && ['queued', 'running'].includes(build?.status);

  const refresh = useCallback(async (buildId, page = 0) => {
    const current = generation.current;
    const sequence = ++revision.current;
    const data = await request('get_build', { source_version_id: version, ...(buildId ? { build_id: buildId } : {}) });
    const catalog = data.build_id ? await request('list_characters', { build_id: data.build_id, offset: page, limit: 25 }) : null;
    let history = null;
    if (data.stage === 'persona_published' && ['published', 'partial_published'].includes(data.status)) history = await request('get_revision_context', { build_id: data.build_id });
    else if (data.stage === 'persona_extract' && data.parent_build_id) {
      const parent = await request('get_build', { build_id: data.parent_build_id });
      if (['published', 'partial_published'].includes(parent.status)) history = await request('get_revision_context', { build_id: parent.build_id });
    }
    if (current !== generation.current || sequence !== revision.current) return;
    if (displayedBuild.current !== data.build_id) {
      displayedBuild.current = data.build_id;
      detailRevision.current += 1; setDetail(null); setCorrecting(false);
    }
    setContext(history);
    setBuild(data); setCharacters(catalog?.characters || []); setTotal(catalog?.total || 0); setOffset(page); setError('');
  }, [request, version]);

  useEffect(() => {
    const current = ++generation.current;
    revision.current += 1;
    detailRevision.current += 1;
    displayedBuild.current = null;
    Promise.resolve().then(() => {
      if (current !== generation.current) return;
      setBuild(null); setCharacters([]); setTotal(0); setOffset(0); setBusy(false); setError(''); setDetail(null); setContext(null); setCorrecting(false);
      if (version) refresh().catch((failure) => { if (current === generation.current) setError(failure.message); });
    });
    return () => { generation.current += 1; detailRevision.current += 1; };
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
    detailRevision.current += 1; setDetail(null);
    setBusy(true); setError('');
    try {
      const data = await request(action, { source_version_id: version, ...(action === 'start_discovery' ? {} : { build_id: action === 'start_persona' ? (build.parent_build_id || build.build_id) : build.build_id }) });
      if (current !== generation.current) return;
      await refresh(data.build_id);
    } catch (failure) { if (current === generation.current) setError(failure.message); }
    finally { if (current === generation.current) setBusy(false); }
  };

  const openDetails = async (character) => {
    const current = generation.current;
    const sequence = ++detailRevision.current;
    try {
      const data = await request('get_character', { build_id: build.build_id, character_id: character.id });
      if (current === generation.current && sequence === detailRevision.current) setDetail(data);
    } catch (failure) { if (current === generation.current && sequence === detailRevision.current) setError(failure.message); }
  };

  return <details style={{ marginTop: 12 }}>
    <summary style={{ cursor: 'pointer', fontSize: 13 }}>{t('bookWorld.characterTitle')}</summary>
    <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t('bookWorld.candidateHint')}</p>
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
      <Button size="small" disabled={source?.status !== 'ready' || active || busy} onClick={() => act('start_discovery')}>{t('bookWorld.discover')}</Button>
      {(build?.stage === 'discovery_complete' || (build?.parent_build_id && ['failed', 'cancelled'].includes(build.status))) && <Button size="small" disabled={active || busy || !total} onClick={() => act('start_persona')}>{t('bookWorld.buildPersona')}</Button>}
      {active && <Button size="small" disabled={busy} onClick={() => act('cancel_build')}>{t('bookWorld.cancelBuild')}</Button>}
      {['failed', 'cancelled'].includes(build?.status) && <Button size="small" disabled={busy} onClick={() => act('retry_build')}>{t('bookWorld.retryBuild')}</Button>}
      {build?.can_resume && <Button size="small" disabled={busy} onClick={() => act('resume_build')}>{t('bookWorld.resumeBuild')}</Button>}
      {build?.build_id && <Button size="small" disabled={busy} onClick={() => refresh(build.build_id, offset).catch((failure) => setError(failure.message))}>{t('bookWorld.refreshBuild')}</Button>}
    </div>
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 8 }} />}
    {context && <div style={{ marginBottom: 8 }}>
      <Select aria-label={t('bookWorld.buildHistory')} style={{ width: '100%' }} value={build?.build_id} disabled={busy}
        onChange={(id) => { detailRevision.current += 1; setDetail(null); setCorrecting(false); refresh(id).catch((failure) => setError(failure.message)); }}
        options={context.versions.map((entry) => ({ value: entry.id, label: `${entry.id.slice(0, 8)} · ${t(`bookWorld.buildStatus.${entry.status}`)} · ${entry.created_at}` }))} />
      {context.changes.length > 0 && <details><summary>{t('bookWorld.revisionChanges')}</summary>
        <ul>{context.changes.map((change, index) => <li key={index}>{change.original_name} · {t(`bookWorld.revisionOp.${change.operation}`)} → {change.target_name || change.value}
          <blockquote>{change.evidence.quote}</blockquote></li>)}</ul></details>}
    </div>}
    {build?.build_id && <>
      <Tag color={build.stage === 'discovery_complete' ? 'green' : build.status === 'failed' ? 'red' : 'blue'}>{build.stage === 'discovery_complete' ? t('bookWorld.discoveryComplete') : t(`bookWorld.buildStatus.${build.status}`)}</Tag>
      <span style={{ fontSize: 12 }}>{t('bookWorld.buildProgress', { completed: build.completed_units, total: build.total_units, processed: build.processed_segments, segments: build.total_segments })}</span>
      {build.stage === 'persona_extract' && <div style={{ fontSize: 12 }}>{t('bookWorld.personaExtracting')}</div>}
      {build.publication_report && <Alert type={build.status === 'partial_published' ? 'warning' : 'success'} showIcon title={t('bookWorld.publicationCoverage', { published: build.publication_report.published_characters, unresolved: build.publication_report.unresolved_characters, failed: build.publication_report.failed_units.length, conflicts: build.publication_report.baseline_conflicts })} style={{ marginTop: 8 }} />}
      <Progress size="small" percent={build.total_units ? Math.round(100 * build.completed_units / build.total_units) : 0} status={build.status === 'failed' ? 'exception' : active ? 'active' : 'normal'} />
      {build.error_detail && <Alert type="warning" showIcon title={build.error_detail} style={{ marginBottom: 8 }} />}
      <p style={{ fontSize: 12 }}>{t('bookWorld.candidateCount', { count: total })}</p>
      <ul style={{ listStyle: 'none', padding: 0, maxHeight: 360, overflowY: 'auto' }}>
        {characters.map((character) => <li key={character.id} style={{ borderBottom: '1px solid var(--border)', padding: '8px 0', fontSize: 12 }}>
          <strong>{character.name}</strong> <Tag color={character.agent_status === 'needs_review' ? 'orange' : 'default'}>{t(`bookWorld.characterStatus.${character.agent_status}`)}</Tag>
          {build.parent_build_id && <Button type="link" size="small" onClick={() => openDetails(character)}>{t('bookWorld.viewPersona')}</Button>}
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
    {detail && <CharacterPersonaModal key={`${detail.build_id}:${detail.character_id}`} detail={detail}
      onCorrect={() => setCorrecting(true)}
      onSaveExtension={async (text) => {
        const current = generation.current; const sequence = ++detailRevision.current;
        await request('save_extension', { build_id: detail.build_id, character_id: detail.character_id, extension_text: text });
        const data = await request('get_character', { build_id: detail.build_id, character_id: detail.character_id });
        if (current === generation.current && sequence === detailRevision.current) setDetail(data);
      }}
      onClose={() => { detailRevision.current += 1; setDetail(null); setCorrecting(false); }}
      onLocate={(evidence) => { detailRevision.current += 1; setDetail(null); setCorrecting(false); onLocate(evidence); }} />}
    {correcting && detail && context && <CharacterRevisionModal key={`${detail.build_id}:${detail.character_id}`} detail={detail} context={context} request={request}
      onClose={() => setCorrecting(false)} onRevised={async (id) => { detailRevision.current += 1; setDetail(null); setCorrecting(false); await refresh(id); }} />}
  </details>;
}
