import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Modal, Spin, Tag } from 'antd';
import { useTranslation } from 'react-i18next';

export default function NarrativeSourcePanel({ item, sendWSMessage }) {
  const { t } = useTranslation();
  const [source, setSource] = useState(null);
  const [segments, setSegments] = useState([]);
  const [nextOrdinal, setNextOrdinal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [locator, setLocator] = useState(null);
  const generation = useRef(0);
  const sourceRequest = useRef(0);
  const segmentRequest = useRef(0);

  const request = useCallback(async (action, data = {}) => {
    const response = await sendWSMessage('book_world', { action, item_id: item.id, ...data }, 120000);
    return response.data;
  }, [item.id, sendWSMessage]);

  const loadSegments = useCallback(async (version, cursor = -1, append = false) => {
    const current = generation.current;
    const revision = ++segmentRequest.current;
    const data = await request('list_segments', { source_version_id: version, after_ordinal: cursor, limit: 25 });
    if (current !== generation.current || revision !== segmentRequest.current) return;
    setSegments((previous) => append ? [...previous, ...data.segments] : data.segments);
    setNextOrdinal(data.next_ordinal);
  }, [request]);

  useEffect(() => {
    const current = ++generation.current;
    const revision = ++sourceRequest.current;
    setSource(null);
    setSegments([]);
    setError('');
    setLocator(null);
    setNextOrdinal(null);
    setBusy(false);
    request('get_source').then(async (data) => {
      if (generation.current !== current || sourceRequest.current !== revision) return;
      setSource(data);
      if (data.source_version_id) await loadSegments(data.source_version_id);
    }).catch((failure) => {
      if (generation.current === current && sourceRequest.current === revision) setError(failure.message);
    });
    return () => { generation.current += 1; };
  }, [request, loadSegments, item.pdf_sha256]);

  const prepare = async () => {
    const current = generation.current;
    const revision = ++sourceRequest.current;
    segmentRequest.current += 1;
    setBusy(true);
    setError('');
    setLocator(null);
    try {
      const data = await request('prepare_source', { expected_attachment_sha256: item.pdf_sha256 });
      if (generation.current !== current || sourceRequest.current !== revision) return;
      setSource(data);
      await loadSegments(data.source_version_id);
    } catch (failure) {
      if (generation.current === current) setError(failure.message);
    } finally {
      if (generation.current === current) setBusy(false);
    }
  };

  const locate = async (segment) => {
    const current = generation.current;
    try {
      const data = await request('resolve_evidence', { source_version_id: source.source_version_id, segment_id: segment.id });
      if (generation.current === current) setLocator(data);
    } catch (failure) {
      if (generation.current === current) setError(failure.message);
    }
  };

  const openOriginal = () => {
    const folder = locator.asset_path.slice(0, locator.asset_path.lastIndexOf('/'));
    if (window.electronAPI?.openPdfWindow) {
      window.electronAPI.openPdfWindow(folder, item.title, undefined, { page: locator.page });
    } else {
      window.open(`/pdf-viewer#?path=${encodeURIComponent(folder)}&title=${encodeURIComponent(item.title || '')}&page=${locator.page}`, '_blank');
    }
  };

  return <section aria-label={t('bookWorld.sourceTitle')} style={{ marginBottom: 18, padding: 12, border: '1px solid var(--border)', borderRadius: 8 }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
      <strong style={{ fontSize: 13 }}>{t('bookWorld.sourceTitle')}</strong>
      <Button size="small" loading={busy} disabled={!item.pdf_sha256} onClick={prepare}>{t('bookWorld.prepare')}</Button>
    </div>
    <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '8px 0' }}>{t('bookWorld.sourceHint')}</p>
    {!item.pdf_sha256 && <span style={{ fontSize: 12 }}>{t('bookWorld.waitAttachment')}</span>}
    {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 8 }} />}
    {busy && <div role="status"><Spin size="small" /> {t('bookWorld.preparing')}</div>}
    {source?.source_version_id && <>
      <Tag color={source.status === 'ready' ? 'green' : 'orange'}>{t(`bookWorld.${source.status}`)}</Tag>
      <span style={{ fontSize: 12 }}>{t('bookWorld.coverage', { pages: source.quality.pages_processed, total: source.quality.pages_total, segments: source.segment_count })}</span>
      {source.status === 'needs_ocr' && <Alert type="warning" showIcon title={t('bookWorld.ocrHint')} style={{ margin: '8px 0' }} />}
      {source.quality.empty_pages?.length > 0 && <div style={{ fontSize: 12, marginTop: 6 }}>{t('bookWorld.emptyPages', { pages: source.quality.empty_pages.join(', ') })}</div>}
      <details style={{ marginTop: 10 }}>
        <summary style={{ cursor: 'pointer', fontSize: 12 }}>{t('bookWorld.browse')}</summary>
        <ol style={{ paddingLeft: 20, maxHeight: 280, overflowY: 'auto', marginBottom: 8 }}>
          {segments.map((segment) => <li key={segment.id} style={{ fontSize: 12, margin: '10px 0', whiteSpace: 'pre-wrap' }}>
            {segment.text}
            <Button type="link" size="small" onClick={() => locate(segment)}>{t('bookWorld.locatePage', { page: segment.page })}</Button>
          </li>)}
        </ol>
        {nextOrdinal !== null && <Button size="small" onClick={() => loadSegments(source.source_version_id, nextOrdinal, true).catch((failure) => setError(failure.message))}>{t('bookWorld.more')}</Button>}
      </details>
    </>}
    <Modal open={Boolean(locator)} title={t('bookWorld.original')} onCancel={() => setLocator(null)} footer={locator ? <Button onClick={openOriginal}>{t('bookWorld.openPdf', { page: locator.page })}</Button> : null}>
      {locator && <><p>{t('bookWorld.locatePage', { page: locator.page })} · {locator.source_version_id.slice(0, 8)}</p><blockquote style={{ whiteSpace: 'pre-wrap' }}>{locator.quote}</blockquote></>}
    </Modal>
  </section>;
}
