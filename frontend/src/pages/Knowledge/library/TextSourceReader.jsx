import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Modal, Spin } from 'antd';
import { useTranslation } from 'react-i18next';

export default function TextSourceReader({ item, sendWSMessage, versionId, locator, onClose }) {
  const { t } = useTranslation();
  const [version, setVersion] = useState(versionId);
  const [windowData, setWindowData] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const revision = useRef(0);
  const request = async (action, values = {}) => {
    const result = await sendWSMessage('book_world', { action, item_id: item.id, ...values }, 120000);
    return result.data;
  };
  const load = async (sourceVersion, offset) => {
    const current = ++revision.current;
    setBusy(true);
    setError('');
    try {
      const data = await request('read_source', { source_version_id: sourceVersion, offset, text_limit: 12000 });
      if (current === revision.current) setWindowData(data);
    } catch (failure) {
      if (current === revision.current) setError(failure.message);
    } finally {
      if (current === revision.current) setBusy(false);
    }
  };
  useEffect(() => {
    let active = true;
    setWindowData(null);
    setBusy(true);
    setError('');
    const initialize = async () => {
      try {
        let selectedVersion = versionId;
        if (!selectedVersion) {
          let source = await request('get_source');
          if (!source.source_version_id) source = await request('prepare_source');
          selectedVersion = source.source_version_id;
        }
        if (!active) return;
        setVersion(selectedVersion);
        await load(selectedVersion, Math.max(0, (locator?.source_start || 0) - 500));
      } catch (failure) {
        if (active) { setError(failure.message); setBusy(false); }
      }
    };
    initialize();
    return () => { active = false; revision.current += 1; };
  }, [item.id, versionId, locator?.source_start, sendWSMessage]);
  const characters = Array.from(windowData?.text || '');
  const start = locator ? Math.max(0, locator.source_start - (windowData?.offset || 0)) : -1;
  const end = locator ? Math.min(characters.length, locator.source_end - (windowData?.offset || 0)) : -1;
  const marked = start >= 0 && start < characters.length && end > start;
  return <Modal open title={t('bookWorld.textReaderTitle', { title: item.title })} onCancel={onClose} width={900} footer={
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span>{windowData ? t('bookWorld.textPosition', { offset: windowData.offset, total: windowData.total_characters }) : ''}</span>
      <div style={{ display: 'flex', gap: 8 }}>
        <Button disabled={busy || !windowData || windowData.offset === 0} onClick={() => load(version, Math.max(0, windowData.offset - 12000))}>{t('bookWorld.previousText')}</Button>
        <Button disabled={busy || !windowData || windowData.next_offset === null} onClick={() => load(version, windowData.next_offset)}>{t('bookWorld.nextText')}</Button>
      </div>
    </div>
  }>
    {error && <Alert type="error" showIcon title={error} />}
    {busy ? <Spin /> : <div style={{ maxHeight: '65vh', overflowY: 'auto', whiteSpace: 'pre-wrap', lineHeight: 1.9, padding: 12 }}>
      {marked ? <>{characters.slice(0, start).join('')}<mark>{characters.slice(start, end).join('')}</mark>{characters.slice(end).join('')}</> : characters.join('')}
    </div>}
  </Modal>;
}
