import React, { useState } from 'react';
import { Sparkles, X } from 'lucide-react';
import { useDistillTasks } from '@contexts/DistillTaskContext';

const TEMPLATES = [
  { key: 'summary', label: 'Summary', desc: 'Concise summary with conclusions, methods, evidence and limitations' },
  { key: 'qa', label: 'Q&A', desc: 'Extract content into question-answer pairs' },
  { key: 'methodology', label: 'Methodology', desc: 'Extract approach, design, datasets, metrics and evaluation' },
  { key: 'mindmap', label: 'Mind Map', desc: 'Hierarchical bullet outline (max 4 levels)' },
  { key: 'custom', label: 'Custom', desc: 'Tell the AI exactly what to extract' },
];

export default function DistillDialog({
  visible,
  sourceFile,
  sourceFiles,
  onCancel,
  onStartDistill,
  vaults = [],
}) {
  const [template, setTemplate] = useState('summary');
  const [prompt, setPrompt] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const [selectedVault, setSelectedVault] = useState('');
  const { addTask } = useDistillTasks();

  const allSources = sourceFiles && sourceFiles.length > 0 ? sourceFiles : (sourceFile ? [sourceFile] : []);
  const isBatch = allSources.length > 1;

  const vaultRootPath = `knowledge/notes/${selectedVault || 'default'}`;

  const reset = () => {
    setTemplate('summary');
    setPrompt('');
    setIsStarting(false);
    setSelectedVault('');
  };

  const handleCancel = () => {
    reset();
    onCancel();
  };

  const handleStart = async () => {
    if (allSources.length === 0) return;

    setIsStarting(true);

    try {
      addTask({
        sourceFile: allSources[0],
        template,
        prompt,
        batch: isBatch,
        batchCount: allSources.length,
      });

      await onStartDistill({
        prompt,
        template,
        taskId: undefined,
        targetPath: vaultRootPath,
        vault: selectedVault || 'default',
        sources: allSources,
      });

      reset();
      onCancel();
    } catch (err) {
      console.error('Failed to start distillation:', err);
      setIsStarting(false);
    }
  };

  if (!visible) return null;

  return (
    <div className="dialog-overlay" onClick={handleCancel}>
      <div
        className="dialog-content"
        style={{
          minWidth: 560,
          maxWidth: '92vw',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="dialog-header">
          <div className="dialog-header-left">
            <Sparkles size={16} style={{ color: 'var(--accent)' }} />
            <span style={{ fontWeight: 600 }}>
              {isBatch ? `Distill ${allSources.length} files` : `Distill: ${sourceFile?.split('/').pop() || ''}`}
            </span>
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
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: '16px 20px', overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {isBatch && (
            <div style={{
              maxHeight: 120,
              overflowY: 'auto',
              border: '1px solid var(--border)',
              borderRadius: 'var(--r-sm)',
              background: 'var(--surface-2)',
              padding: '8px 10px',
              fontSize: 12,
              color: 'var(--text-2)',
            }}>
              {allSources.map((src, i) => (
                <div key={i} style={{ padding: '2px 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {src.split('/').pop()}
                </div>
              ))}
            </div>
          )}

          {/* Vault selector */}
          {vaults.length > 0 && (
            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>
                Target Vault
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
                }}
              >
                <option value="">default</option>
                {vaults.map((v) => (
                  <option key={v.name} value={v.name}>{v.name}</option>
                ))}
              </select>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 6 }}>
                Distilled output will be saved to <code style={{ fontFamily: 'var(--font-mono)' }}>{vaultRootPath}/</code>
              </div>
            </div>
          )}

          {/* Template selector */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>
              Template
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {TEMPLATES.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTemplate(t.key)}
                  title={t.desc}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 'var(--r-sm)',
                    border: '1px solid',
                    borderColor: template === t.key ? 'var(--accent)' : 'var(--border)',
                    background: template === t.key ? 'var(--accent-soft)' : 'var(--surface)',
                    color: template === t.key ? 'var(--accent)' : 'var(--text)',
                    fontSize: 12,
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Prompt input */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>
              {template === 'custom' ? 'Instructions' : 'Additional instructions (optional)'}
            </label>
            <textarea
              rows={4}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={
                template === 'custom'
                  ? 'e.g. Extract all figures and tables as markdown'
                  : 'e.g. Focus on experimental design and limitations'
              }
              style={{
                width: '100%',
                padding: 10,
                fontSize: 13,
                fontFamily: 'var(--font-sans)',
                borderRadius: 'var(--r-sm)',
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                color: 'var(--text)',
                resize: 'vertical',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Info text */}
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
            <strong style={{ color: 'var(--text)' }}>How it works:</strong>
            <br />
            Click "Start Distillation" to send the task to background. You can monitor progress in the task indicator at the top right.
          </div>
        </div>

        <div className="dialog-footer" style={{ justifyContent: 'flex-end', gap: 10 }}>
          <button className="pixel-button secondary" onClick={handleCancel} disabled={isStarting}>
            Cancel
          </button>
          <button
            className={`pixel-button ${isStarting ? 'loading' : ''}`}
            onClick={handleStart}
            disabled={isStarting}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Sparkles size={14} />
            {isStarting ? 'Starting...' : isBatch ? `Distill ${allSources.length} files` : 'Start Distillation'}
          </button>
        </div>
      </div>
    </div>
  );
}
