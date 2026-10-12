import React, { useState } from 'react';
import { Alert, Button, Empty, Input, Modal, Space, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import CharacterKnowledgePanel from './CharacterKnowledgePanel';

export default function CharacterPersonaModal({ detail, request, onClose, onLocate, onCorrect, onSaveExtension }) {
  const { t } = useTranslation();
  const [extension, setExtension] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const saveExtension = async () => {
    setSaving(true); setError('');
    try { await onSaveExtension(extension); setExtension(''); }
    catch (failure) { setError(failure.message); }
    finally { setSaving(false); }
  };
  const baseline = Object.entries(detail?.reader?.baseline || {});
  const claims = detail?.reader?.claims || [];
  return <Modal open={Boolean(detail)} title={`${detail?.public?.name || ''} · ${t('bookWorld.personaTitle')}`} width={760} onCancel={onClose} footer={<Button onClick={onClose}>{t('bookWorld.closeArchive')}</Button>}>
    <Alert type="info" showIcon title={t('bookWorld.readerArchiveHint')} style={{ marginBottom: 12 }} />
    {detail.published && <Button size="small" onClick={onCorrect}>{t('bookWorld.correctPersona')}</Button>}
    {detail.published && ['ready', 'sparse'].includes(detail.agent_status) && <CharacterKnowledgePanel key={`${detail.build_id}:${detail.character_id}`} detail={detail} request={request} onLocate={onLocate} />}
    <h4>{t('bookWorld.baselineTitle')}</h4>
    {baseline.length ? <ul>{baseline.map(([slot, entry]) => <li key={slot}>{entry.proposition}</li>)}</ul> : <p>{t('bookWorld.baselineUnknown')}</p>}
    <h4>{t('bookWorld.claimsTitle')}</h4>
    <div style={{ maxHeight: 420, overflowY: 'auto' }}>
      {!claims.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('bookWorld.noClaims')} />}
      {claims.map((claim) => <article key={claim.id} style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
        <Tag>{t(`bookWorld.claimKind.${claim.kind}`)}</Tag>
        <Tag color={claim.support_state === 'accepted' ? 'green' : 'orange'}>{t(`bookWorld.supportState.${claim.support_state}`)}</Tag>
        {claim.kind === 'belief' && <Tag>{t('bookWorld.beliefTruth', { truth: t(`bookWorld.truthState.${claim.truth_state}`) })}</Tag>}
        <p style={{ margin: '6px 0' }}>{claim.proposition}</p>
        {claim.supersedes_claim_id && <div style={{ fontSize: 12 }}>{t('bookWorld.correctedBelief')}</div>}
        {claim.access.map((access) => <div key={access.character_id} style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t(`bookWorld.accessRoute.${access.route}`)} · {t(access.access_state === 'accepted' ? 'bookWorld.accessAllowed' : 'bookWorld.accessDenied')}</div>)}
        {claim.evidence.map((evidence, index) => <div key={`${evidence.segment_id}:${index}`} style={{ marginTop: 6, fontSize: 12, whiteSpace: 'pre-wrap' }}>
          <blockquote style={{ margin: '4px 0', paddingLeft: 10, borderLeft: '2px solid var(--border)' }}>{evidence.quote_text}</blockquote>
          <Button size="small" type="link" onClick={() => onLocate(evidence)}>{t('bookWorld.candidateEvidence')}</Button>
        </div>)}
      </article>)}
    </div>
    <h4>{t('bookWorld.extensionTitle')}</h4>
    <p>{t('bookWorld.extensionHint')}</p>
    {(detail.reader.extensions || []).map((entry) => <blockquote key={entry.id} style={{ whiteSpace: 'pre-wrap' }}>{entry.text}</blockquote>)}
    {error && <Alert type="error" title={error} />}
    <Space orientation="vertical" style={{ width: '100%' }}>
      <Input.TextArea aria-label={t('bookWorld.extensionTitle')} value={extension} maxLength={4000} rows={2} onChange={(event) => setExtension(event.target.value)} />
      <Button size="small" disabled={!extension.trim()} loading={saving} onClick={saveExtension}>{t('bookWorld.saveExtension')}</Button>
    </Space>
  </Modal>;
}
