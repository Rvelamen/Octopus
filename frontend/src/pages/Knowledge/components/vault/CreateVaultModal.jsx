import React, { useState } from 'react';
import { FolderPlus } from 'lucide-react';

export default function CreateVaultModal({ visible, onCancel, onConfirm }) {
  const [vaultName, setVaultName] = useState('');

  if (!visible) return null;

  const isValid = vaultName.trim().length > 0 && !vaultName.includes('/') && !vaultName.includes('\\');

  const handleConfirm = () => {
    if (!isValid) return;
    onConfirm(vaultName.trim());
    setVaultName('');
  };

  const handleCancel = () => {
    setVaultName('');
    onCancel();
  };

  return (
    <div className="dialog-overlay" onClick={handleCancel}>
      <div
        className="dialog-content"
        style={{ minWidth: 360 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="dialog-header">
          <div className="dialog-header-left">
            <FolderPlus size={16} style={{ color: 'var(--accent)' }} />
            <span style={{ fontWeight: 600 }}>Create Vault</span>
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

        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>
              Vault Name
            </label>
            <input
              type="text"
              value={vaultName}
              onChange={(e) => setVaultName(e.target.value)}
              placeholder="e.g. research, daily_notes, project_x"
              style={{
                width: '100%',
                padding: '8px 10px',
                fontSize: 13,
                borderRadius: 'var(--r-sm)',
                border: `1px solid ${!isValid && vaultName.length > 0 ? 'var(--error)' : 'var(--border)'}`,
                background: 'var(--surface)',
                color: 'var(--text)',
                boxSizing: 'border-box',
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleConfirm()}
              autoFocus
            />
            {!isValid && vaultName.length > 0 && (
              <div style={{ fontSize: 11, color: 'var(--error)', marginTop: 4 }}>
                Vault name cannot contain / or \
              </div>
            )}
            <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>
              Will create: <code>knowledge/notes/{vaultName || '...'}/</code>
            </div>
          </div>
        </div>

        <div className="dialog-footer" style={{ justifyContent: 'flex-end', gap: 10 }}>
          <button className="pixel-button secondary" onClick={handleCancel}>
            Cancel
          </button>
          <button
            className="pixel-button"
            onClick={handleConfirm}
            disabled={!isValid}
            style={{ opacity: isValid ? 1 : 0.5 }}
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}
