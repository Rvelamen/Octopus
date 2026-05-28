import React, { useState, useEffect } from 'react';
import { MessageSquare, FileText, Clock } from 'lucide-react';
import { Button, Input, Modal, Empty } from 'antd';

const LibraryAnnotationModal = ({ open, onClose, annotations, onSave }) => {
  const [editing, setEditing] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setEditing({});
      setSaving(false);
    }
  }, [open]);

  const handleCommentChange = (annotId, comment) => {
    setEditing((prev) => ({ ...prev, [annotId]: comment }));
  };

  const handleSave = async () => {
    const hasChanges = Object.keys(editing).length > 0;
    if (!hasChanges) {
      onClose();
      return;
    }
    setSaving(true);
    try {
      const updated = annotations.map((a) => ({
        ...a,
        comment: editing[a.id] !== undefined ? editing[a.id] : a.comment,
      }));
      await onSave(updated);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const grouped = annotations.reduce((acc, a) => {
    const page = a.page || 0;
    if (!acc[page]) acc[page] = [];
    acc[page].push(a);
    return acc;
  }, {});

  const pages = Object.keys(grouped).map(Number).sort((a, b) => a - b);

  const formatTime = (ts) => {
    if (!ts) return '';
    const d = new Date(ts);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleString();
  };

  return (
    <Modal
      title={
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={16} />
          Annotations ({annotations.length})
        </span>
      }
      open={open}
      onCancel={onClose}
      width={720}
      footer={(
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="primary" loading={saving} onClick={handleSave}>
            Save
          </Button>
        </div>
      )}
    >
      {annotations.length === 0 ? (
        <Empty description="No annotations yet" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxHeight: '70vh', overflow: 'auto', paddingRight: 4 }}>
          {pages.map((page) => (
            <div key={page}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--text-muted)',
                  marginBottom: 10,
                  paddingBottom: 6,
                  borderBottom: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <span style={{ color: 'var(--accent)', fontWeight: 700 }}>Page {page}</span>
                <span style={{ fontSize: 11 }}>· {grouped[page].length} annotation{grouped[page].length > 1 ? 's' : ''}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {grouped[page].map((annot) => {
                  const isEdited = editing[annot.id] !== undefined;
                  const displayComment = isEdited ? editing[annot.id] : annot.comment;
                  return (
                    <div
                      key={annot.id}
                      style={{
                        padding: '12px 14px',
                        borderRadius: 8,
                        background: 'var(--surface)',
                        border: '1px solid var(--border)',
                        borderLeft: `4px solid ${annot.color || '#1890ff'}`,
                      }}
                    >
                      {/* Header: type badge + color swatch + time */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          marginBottom: 8,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 10,
                            padding: '2px 8px',
                            borderRadius: 4,
                            background: annot.color || '#1890ff',
                            color: '#fff',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px',
                          }}
                        >
                          {annot.type}
                        </span>
                        {annot.created_at && (
                          <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <Clock size={11} />
                            {formatTime(annot.created_at)}
                          </span>
                        )}
                      </div>

                      {/* Quoted text */}
                      {annot.text && (
                        <div
                          style={{
                            fontSize: 13,
                            color: 'var(--text)',
                            lineHeight: 1.6,
                            marginBottom: 10,
                            padding: '8px 10px',
                            background: 'var(--bg)',
                            borderRadius: 6,
                            borderLeft: '2px solid var(--border)',
                            wordBreak: 'break-word',
                          }}
                        >
                          <span style={{ color: 'var(--text-muted)', marginRight: 4 }}>“</span>
                          {annot.text}
                          <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>”</span>
                        </div>
                      )}

                      {/* Comment input */}
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                        <MessageSquare size={14} style={{ color: 'var(--text-muted)', marginTop: 6, flexShrink: 0 }} />
                        <Input.TextArea
                          value={displayComment || ''}
                          onChange={(e) => handleCommentChange(annot.id, e.target.value)}
                          placeholder="Add a comment..."
                          autoSize={{ minRows: 2, maxRows: 6 }}
                          style={{
                            fontSize: 13,
                            background: isEdited ? 'var(--accent-soft)' : 'var(--bg)',
                            borderColor: isEdited ? 'var(--accent)' : 'var(--border)',
                            transition: 'all 0.2s',
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
};

export default LibraryAnnotationModal;
