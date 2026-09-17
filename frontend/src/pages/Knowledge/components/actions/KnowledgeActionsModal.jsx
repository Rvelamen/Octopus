import React, { useEffect, useRef } from 'react';
import { Plus, Download, Upload, Library as LibraryIcon, X } from 'lucide-react';

const ACTIONS = [
  {
    key: 'new',
    icon: Plus,
    title: 'New Note',
    desc: 'Create a new Markdown note in the current vault',
    variant: 'accent',
  },
  {
    key: 'export',
    icon: Download,
    title: 'Export',
    desc: 'Download the knowledge vault as a zip',
  },
  {
    key: 'import',
    icon: Upload,
    title: 'Import',
    desc: 'Import a knowledge vault zip',
  },
  {
    key: 'importObsidian',
    icon: LibraryIcon,
    title: 'Import Obsidian Vault',
    desc: 'Import an Obsidian vault zip',
    variant: 'dashed',
  },
];

function Backdrop({ children, onClose }) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        backdropFilter: 'blur(2px)',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg, #fff)',
          borderRadius: 10,
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.25), 0 4px 12px rgba(0, 0, 0, 0.1)',
          width: 560,
          maxWidth: 'calc(100vw - 32px)',
          overflow: 'hidden',
        }}
      >
        {children}
      </div>
    </div>
  );
}

export default function KnowledgeActionsModal({
  open,
  onClose,
  onNewNote,
  onExport,
  onImport,
  onImportObsidian,
}) {
  const importZipRef = useRef(null);
  const importObsidianRef = useRef(null);

  if (!open) return null;

  const trigger = (key) => {
    switch (key) {
      case 'new':
        onNewNote?.();
        onClose();
        break;
      case 'export':
        onExport?.();
        onClose();
        break;
      case 'import':
        // File picker is async; don't close until user actually picks
        importZipRef.current?.click();
        break;
      case 'importObsidian':
        importObsidianRef.current?.click();
        break;
    }
  };

  const onImportZipChange = (e) => {
    const f = e.target.files?.[0];
    if (f) {
      onImport?.(f);
      onClose();
    }
    e.target.value = null;
  };
  const onImportObsidianChange = (e) => {
    const f = e.target.files?.[0];
    if (f) {
      onImportObsidian?.(f);
      onClose();
    }
    e.target.value = null;
  };

  return (
    <Backdrop onClose={onClose}>
      {/* Hidden file inputs for Import / Import Obsidian */}
      <input
        type="file"
        accept=".zip"
        ref={importZipRef}
        style={{ display: 'none' }}
        onChange={onImportZipChange}
      />
      <input
        type="file"
        accept=".zip"
        ref={importObsidianRef}
        style={{ display: 'none' }}
        onChange={onImportObsidianChange}
      />

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 18px',
          borderBottom: '1px solid var(--border, #e8e8e8)',
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary, #1a1a1a)' }}>
          Knowledge Actions
        </div>
        <button
          onClick={onClose}
          title="Close (Esc)"
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary, #666)',
            cursor: 'pointer',
            padding: 4,
            borderRadius: 4,
            display: 'flex',
            alignItems: 'center',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-secondary, #f5f5f5)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <X size={15} />
        </button>
      </div>

      {/* 2x2 action grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 12,
          padding: 16,
        }}
      >
        {ACTIONS.map((a) => {
          const Icon = a.icon;
          const isAccent = a.variant === 'accent';
          const isDashed = a.variant === 'dashed';
          return (
            <button
              key={a.key}
              onClick={() => trigger(a.key)}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12,
                padding: '14px 16px',
                borderRadius: 8,
                border: isAccent
                  ? '1px solid var(--accent, #B46A57)'
                  : isDashed
                    ? '1px dashed var(--accent, #B46A57)'
                    : '1px solid var(--border, #e8e8e8)',
                background: isAccent
                  ? 'var(--accent-soft, rgba(180, 106, 87, 0.10))'
                  : 'var(--surface, #fafafa)',
                color: isAccent ? 'var(--accent, #B46A57)' : 'var(--text-primary, #1a1a1a)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'transform 0.12s ease, box-shadow 0.12s ease, background 0.12s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-1px)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.06)';
                if (!isAccent) e.currentTarget.style.background = 'var(--bg-secondary, #f5f5f5)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = 'none';
                e.currentTarget.style.background = isAccent
                  ? 'var(--accent-soft, rgba(180, 106, 87, 0.10))'
                  : 'var(--surface, #fafafa)';
              }}
            >
              <Icon
                size={22}
                style={{
                  flexShrink: 0,
                  color: isAccent ? 'var(--accent, #B46A57)' : 'var(--text-secondary, #666)',
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{a.title}</div>
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--text-secondary, #888)',
                    lineHeight: 1.45,
                  }}
                >
                  {a.desc}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </Backdrop>
  );
}