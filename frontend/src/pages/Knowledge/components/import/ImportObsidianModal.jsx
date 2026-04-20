import React, { useState } from 'react';
import { Upload } from 'lucide-react';

export default function ImportObsidianModal({ visible, file, vaults = [], onCancel, onConfirm }) {
  const [selectedVault, setSelectedVault] = useState('');

  if (!visible) return null;

  const handleConfirm = () => {
    onConfirm(selectedVault || null);
    setSelectedVault('');
  };

  const handleCancel = () => {
    setSelectedVault('');
    onCancel();
  };

  return (
    <div className="dialog-overlay" onClick={handleCancel}>
      <div
        className="dialog-content"
        style={{ minWidth: 400, maxWidth: '90vw' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="dialog-header">
          <div className="dialog-header-left">
            <Upload size={16} style={{ color: 'var(--accent)' }} />
            <span style={{ fontWeight: 600 }}>Import Obsidian Vault</span>
          </div>
          <button
            onClick={handleCancel}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-2)',
              cursor: 'pointer',
              padding: 4,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>Selected file</div>
            <div style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500 }}>
              {file?.name} ({(file?.size / 1024 / 1024).toFixed(1)} MB)
            </div>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>
              Vault
            </label>
            <select
              value={selectedVault}
              onChange={(e) => setSelectedVault(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 10px',
                fontSize: 13,
                borderRadius: 'var(--r-sm)',
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                color: 'var(--text)',
                boxSizing: 'border-box',
                cursor: 'pointer',
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleConfirm()}
            >
              <option value="">Auto-generate vault name</option>
              {vaults.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>
              Notes will be placed under: <code>knowledge/notes/{selectedVault || '<auto>'}/</code>
            </div>
          </div>

          <div
            style={{
              padding: 10,
              borderRadius: 6,
              background: 'var(--surface-2)',
              fontSize: 12,
              color: 'var(--text-2)',
              lineHeight: 1.5,
            }}
          >
            <strong style={{ color: 'var(--text)' }}>Note:</strong> [[Wikilinks]] and #tags will be preserved and re-indexed automatically after import. The vault name becomes the top-level folder.
          </div>
        </div>

        <div className="dialog-footer" style={{ justifyContent: 'flex-end', gap: 10 }}>
          <button className="pixel-button secondary" onClick={handleCancel}>
            Cancel
          </button>
          <button
            className="pixel-button"
            onClick={handleConfirm}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Upload size={14} />
            Import
          </button>
        </div>
      </div>
    </div>
  );
}
