import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { MessageSquare, FileText, Clock, Trash2 } from 'lucide-react';
import { Button, Input, Modal, Empty } from 'antd';
import { useTranslation } from 'react-i18next';

/**
 * Thread-style annotation comment modal.
 *
 * Each annotation now owns a `comments` array (provided by the backend's
 * LEFT JOIN on library_annotation_comments). Posting a new comment is an
 * immediate, granular RPC (no batched "Save" button); deleting one is the
 * inverse. The single `comment` text field is no longer edited from this UI —
 * legacy rows are still rendered as the first item in the thread (authored by
 * "You") courtesy of the migration in knowledge_migrations._migration_012.
 */
const LibraryAnnotationModal = ({
  open,
  onClose,
  annotations,
  sendWSMessage,
  itemId,
  onCommentAdded,
  onCommentDeleted,
}) => {
  const { t } = useTranslation();
  const [drafts, setDrafts] = useState({}); // { annotationId: string }
  const [busy, setBusy] = useState({}); // { annotationId: true }

  useEffect(() => {
    if (open) {
      setDrafts({});
      setBusy({});
    }
  }, [open]);

  const handlePost = useCallback(
    async (annotId) => {
      const text = (drafts[annotId] || '').trim();
      if (!text) return;
      setBusy((b) => ({ ...b, [annotId]: true }));
      try {
        const resp = await sendWSMessage(
          'library_annotation_comments_add',
          {
            annotation_id: annotId,
            content: text,
            author_name: t('annotation.authorYou'),
          },
          10000,
        );
        const newComment = resp?.data?.comment;
        if (newComment) {
          // Bubble up so parent can splice into its annotations state (best effort).
          if (onCommentAdded) {
            try {
              await onCommentAdded(annotId, newComment);
            } catch (e) {
              console.warn('onCommentAdded handler threw:', e);
            }
          }
          setDrafts((d) => ({ ...d, [annotId]: '' }));
        }
      } catch (e) {
        console.error('Failed to post comment:', e);
      } finally {
        setBusy((b) => ({ ...b, [annotId]: false }));
      }
    },
    [drafts, sendWSMessage, t, onCommentAdded],
  );

  const handleDelete = useCallback(
    async (annotId, commentId) => {
      setBusy((b) => ({ ...b, [annotId]: true }));
      try {
        await sendWSMessage(
          'library_annotation_comments_delete',
          { comment_id: commentId },
          10000,
        );
        if (onCommentDeleted) {
          try {
            await onCommentDeleted(annotId, commentId);
          } catch (e) {
            console.warn('onCommentDeleted handler threw:', e);
          }
        }
      } catch (e) {
        console.error('Failed to delete comment:', e);
      } finally {
        setBusy((b) => ({ ...b, [annotId]: false }));
      }
    },
    [sendWSMessage, onCommentDeleted],
  );

  const grouped = useMemo(() => {
    const acc = {};
    for (const a of annotations) {
      const page = a.page || 0;
      if (!acc[page]) acc[page] = [];
      acc[page].push(a);
    }
    return acc;
  }, [annotations]);

  const pages = useMemo(
    () => Object.keys(grouped).map(Number).sort((a, b) => a - b),
    [grouped],
  );

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
          {t('paper.btnAnnotations')} ({annotations.length})
        </span>
      }
      open={open}
      onCancel={onClose}
      width={720}
      footer={(
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button onClick={onClose}>{t('paper.btnCancel')}</Button>
        </div>
      )}
    >
      {annotations.length === 0 ? (
        <Empty description={t('annotation.chatEmpty')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
            maxHeight: '70vh',
            overflow: 'auto',
            paddingRight: 4,
          }}
        >
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
                <span style={{ color: 'var(--accent)', fontWeight: 700 }}>
                  {t('pdfViewer.pageLabel', { page })}
                </span>
                <span style={{ fontSize: 11 }}>
                  · {grouped[page].length} annotation
                  {grouped[page].length > 1 ? 's' : ''}
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {grouped[page].map((annot) => {
                  const comments = Array.isArray(annot.comments) ? annot.comments : [];
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
                          <span
                            style={{
                              fontSize: 11,
                              color: 'var(--text-muted)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            <Clock size={11} />
                            {formatTime(annot.created_at)}
                          </span>
                        )}
                        <span
                          style={{
                            marginLeft: 'auto',
                            fontSize: 11,
                            color: 'var(--text-muted)',
                          }}
                        >
                          {t('annotation.commentCount', { count: comments.length })}
                        </span>
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
                          <span style={{ color: 'var(--text-muted)', marginRight: 4 }}>
                            “
                          </span>
                          {annot.text}
                          <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>
                            ”
                          </span>
                        </div>
                      )}

                      {/* Existing thread (oldest first; UI is in chronological order) */}
                      {comments.length > 0 && (
                        <div
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 6,
                            marginBottom: 10,
                          }}
                        >
                          {comments.map((c) => (
                            <div
                              key={c.id}
                              style={{
                                display: 'flex',
                                gap: 8,
                                padding: '6px 8px',
                                background: 'var(--bg)',
                                borderRadius: 6,
                                border: '1px solid var(--border)',
                              }}
                            >
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 6,
                                    marginBottom: 2,
                                  }}
                                >
                                  <span
                                    style={{
                                      fontSize: 11,
                                      fontWeight: 600,
                                      color: 'var(--accent)',
                                    }}
                                  >
                                    {c.author_name || t('annotation.authorYou')}
                                  </span>
                                  {c.created_at && (
                                    <span
                                      style={{
                                        fontSize: 10,
                                        color: 'var(--text-muted)',
                                      }}
                                    >
                                      {formatTime(c.created_at)}
                                    </span>
                                  )}
                                </div>
                                <div
                                  style={{
                                    fontSize: 13,
                                    color: 'var(--text)',
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word',
                                  }}
                                >
                                  {c.content}
                                </div>
                              </div>
                              <button
                                onClick={() => handleDelete(annot.id, c.id)}
                                disabled={busy[annot.id]}
                                title={t('annotation.deleteComment')}
                                style={{
                                  background: 'transparent',
                                  border: 'none',
                                  color: 'var(--text-muted)',
                                  cursor: 'pointer',
                                  padding: 2,
                                  alignSelf: 'flex-start',
                                }}
                              >
                                <Trash2 size={11} />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Post a new comment */}
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                        <MessageSquare
                          size={14}
                          style={{ color: 'var(--text-muted)', marginTop: 6, flexShrink: 0 }}
                        />
                        <div style={{ flex: 1, display: 'flex', gap: 6 }}>
                          <Input.TextArea
                            value={drafts[annot.id] || ''}
                            onChange={(e) =>
                              setDrafts((d) => ({ ...d, [annot.id]: e.target.value }))
                            }
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                                e.preventDefault();
                                handlePost(annot.id);
                              }
                            }}
                            placeholder={t('annotation.addCommentPlaceholder')}
                            autoSize={{ minRows: 1, maxRows: 4 }}
                            disabled={busy[annot.id]}
                            style={{ fontSize: 13 }}
                          />
                          <Button
                            size="small"
                            type="primary"
                            loading={busy[annot.id]}
                            disabled={!(drafts[annot.id] || '').trim()}
                            onClick={() => handlePost(annot.id)}
                          >
                            {t('annotation.post')}
                          </Button>
                        </div>
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
