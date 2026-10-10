import React, { useEffect, useState } from 'react';
import { Trash2, X, AlertTriangle, FileText, Folder, Loader2 } from 'lucide-react';

export default function ConfirmDeleteNoteModal({
  item,
  open,
  onClose,
  onConfirm,
}) {
  const [deleting, setDeleting] = useState(false);

  // 重置 loading 状态
  useEffect(() => {
    if (!open) setDeleting(false);
  }, [open]);

  // Esc 关闭
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape' && !deleting) onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, deleting, onClose]);

  if (!open || !item) return null;

  const isDir = !!item.is_directory;
  const name = item.name || item.path?.split('/').pop() || '';
  const path = item.path || '';

  const handleDelete = async () => {
    if (deleting) return;
    setDeleting(true);
    try {
      await onConfirm(item);
      // 成功：父组件会关闭弹窗（open → false → useEffect 重置 deleting）
    } catch {
      // 失败：父组件 message.error，重置按钮
      setDeleting(false);
    }
  };

  return (
    <>
      {/* Local keyframes (loader spin) */}
      <style>{`
        @keyframes confirm-delete-spin { to { transform: rotate(360deg); } }
        .confirm-delete-spinner { animation: confirm-delete-spin 0.9s linear infinite; }
        @keyframes confirm-delete-fade-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes confirm-delete-pop-in {
          from { opacity: 0; transform: scale(0.96) translateY(4px); }
          to   { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>

      <div
        onClick={() => !deleting && onClose()}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          backdropFilter: 'blur(3px)',
          WebkitBackdropFilter: 'blur(3px)',
          animation: 'confirm-delete-fade-in 0.18s ease-out',
        }}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            width: 460,
            maxWidth: 'calc(100vw - 32px)',
            background: 'var(--bg, #fff)',
            borderRadius: 12,
            boxShadow:
              '0 24px 64px rgba(0, 0, 0, 0.28), 0 6px 14px rgba(0, 0, 0, 0.10)',
            overflow: 'hidden',
            animation: 'confirm-delete-pop-in 0.22s cubic-bezier(0.2, 0.8, 0.3, 1)',
          }}
        >
          {/* ── Header ── */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '18px 20px',
              borderBottom: '1px solid var(--border, #ececec)',
            }}
          >
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 10,
                background: 'rgba(220, 38, 38, 0.10)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                boxShadow: 'inset 0 0 0 1px rgba(220, 38, 38, 0.18)',
              }}
            >
              <Trash2 size={18} color="#dc2626" />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 600,
                  color: 'var(--text-primary, #1a1a1a)',
                  letterSpacing: -0.2,
                  lineHeight: 1.3,
                }}
              >
                {isDir ? 'Delete folder?' : 'Delete note?'}
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--text-muted, #888)',
                  marginTop: 2,
                }}
              >
                This action cannot be undone.
              </div>
            </div>
            <button
              onClick={() => !deleting && onClose()}
              disabled={deleting}
              title="Close (Esc)"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-secondary, #666)',
                cursor: deleting ? 'not-allowed' : 'pointer',
                padding: 5,
                borderRadius: 6,
                display: 'flex',
                opacity: deleting ? 0.35 : 1,
                transition: 'background 0.12s ease',
              }}
              onMouseEnter={(e) => {
                if (!deleting)
                  e.currentTarget.style.background = 'var(--bg-secondary, #f5f5f5)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <X size={15} />
            </button>
          </div>

          {/* ── Body ── */}
          <div style={{ padding: '18px 22px 20px' }}>
            {/* Item card */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '12px 14px',
                borderRadius: 8,
                background: 'var(--bg-secondary, #f7f7f8)',
                border: '1px solid var(--border, #ececec)',
                marginBottom: 12,
              }}
            >
              <div style={{ marginTop: 1, flexShrink: 0, color: 'var(--text-secondary, #666)' }}>
                {isDir ? <Folder size={15} /> : <FileText size={15} />}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 500,
                    color: 'var(--text-primary, #1a1a1a)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={name}
                >
                  {name}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--text-muted, #888)',
                    marginTop: 3,
                    fontFamily: 'SF Mono, Monaco, Consolas, monospace',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={path}
                >
                  {path}
                </div>
              </div>
            </div>

            {/* Warning banner */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                padding: '10px 12px',
                borderRadius: 6,
                background: 'rgba(220, 38, 38, 0.06)',
                border: '1px solid rgba(220, 38, 38, 0.18)',
              }}
            >
              <AlertTriangle
                size={13}
                color="#dc2626"
                style={{ marginTop: 2, flexShrink: 0 }}
              />
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--text-secondary, #555)',
                  lineHeight: 1.5,
                }}
              >
                {isDir
                  ? 'All notes and subfolders inside this folder will be permanently deleted.'
                  : 'The note will be permanently removed from this vault. Any links from other notes will break.'}
              </div>
            </div>
          </div>

          {/* ── Footer ── */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 8,
              padding: '12px 20px 14px',
              borderTop: '1px solid var(--border, #ececec)',
              background: 'var(--bg-secondary, #fafafa)',
            }}
          >
            <button
              onClick={() => !deleting && onClose()}
              disabled={deleting}
              style={{
                padding: '7px 14px',
                borderRadius: 6,
                border: '1px solid var(--border, #d0d0d0)',
                background: 'var(--bg, #fff)',
                color: 'var(--text-primary, #333)',
                fontSize: 13,
                fontWeight: 500,
                cursor: deleting ? 'not-allowed' : 'pointer',
                opacity: deleting ? 0.5 : 1,
                transition: 'background 0.12s ease, transform 0.12s ease',
              }}
              onMouseEnter={(e) => {
                if (!deleting)
                  e.currentTarget.style.background = 'var(--bg-secondary, #f0f0f0)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--bg, #fff)';
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              style={{
                padding: '7px 16px',
                borderRadius: 6,
                border: 'none',
                background: 'linear-gradient(180deg, #ef4444 0%, #dc2626 100%)',
                color: '#fff',
                fontSize: 13,
                fontWeight: 600,
                cursor: deleting ? 'wait' : 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                boxShadow: '0 1px 3px rgba(220, 38, 38, 0.30), inset 0 1px 0 rgba(255,255,255,0.15)',
                transition: 'transform 0.12s ease, box-shadow 0.12s ease',
              }}
              onMouseEnter={(e) => {
                if (!deleting) {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow =
                    '0 4px 12px rgba(220, 38, 38, 0.40), inset 0 1px 0 rgba(255,255,255,0.15)';
                }
              }}
              onMouseLeave={(e) => {
                if (!deleting) {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow =
                    '0 1px 3px rgba(220, 38, 38, 0.30), inset 0 1px 0 rgba(255,255,255,0.15)';
                }
              }}
            >
              {deleting && (
                <Loader2
                  size={13}
                  className="confirm-delete-spinner"
                  color="#fff"
                />
              )}
              {deleting ? 'Deleting…' : isDir ? 'Delete folder' : 'Delete note'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
