import React, { useState, useEffect, useCallback } from 'react';
import { Sparkles, Check, X, Folder, ChevronDown, ChevronRight } from 'lucide-react';
import { useDistillTasks } from '@contexts/DistillTaskContext';

const TEMPLATES = [
  { key: 'summary', label: 'Summary', desc: 'Concise summary with conclusions, methods, evidence and limitations' },
  { key: 'qa', label: 'Q&A', desc: 'Extract content into question-answer pairs' },
  { key: 'methodology', label: 'Methodology', desc: 'Extract approach, design, datasets, metrics and evaluation' },
  { key: 'mindmap', label: 'Mind Map', desc: 'Hierarchical bullet outline (max 4 levels)' },
  { key: 'custom', label: 'Custom', desc: 'Tell the AI exactly what to extract' },
];

function DirectoryTree({ treeItems, expandedPaths, selectedDir, onToggle, onSelect, loadDirectory, rootPath }) {
  useEffect(() => {
    if (!treeItems[rootPath]) {
      loadDirectory(rootPath);
    }
  }, [rootPath, treeItems, loadDirectory]);

  const renderNode = (path, level = 0) => {
    const items = treeItems[path] || [];
    const dirs = items.filter((i) => i.is_directory);
    const isExpanded = expandedPaths.has(path);
    const isSelected = selectedDir === path;

    return (
      <div key={path}>
        <button
          onClick={() => onSelect(path)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            width: '100%',
            padding: '5px 8px',
            paddingLeft: `${8 + level * 16}px`,
            border: 'none',
            borderRadius: 4,
            background: isSelected ? 'var(--accent-soft)' : 'transparent',
            color: isSelected ? 'var(--accent)' : 'var(--text)',
            cursor: 'pointer',
            fontSize: 12,
            textAlign: 'left',
          }}
        >
          {dirs.length > 0 && (
            <span
              onClick={(e) => { e.stopPropagation(); onToggle(path); }}
              style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
            >
              {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </span>
          )}
          {dirs.length === 0 && <span style={{ width: 14 }} />}
          <Folder size={13} style={{ color: isSelected ? 'var(--accent)' : '#FFBF2B' }} />
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {path === rootPath ? 'notes' : path.split('/').pop()}
          </span>
          {isSelected && <Check size={12} />}
        </button>
        {isExpanded && dirs.map((d) => renderNode(d.path, level + 1))}
      </div>
    );
  };

  return <div style={{ maxHeight: 220, overflowY: 'auto', padding: '4px 0' }}>{renderNode(rootPath)}</div>;
}

function slugify(name) {
  return name
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5\-]+/g, '_')
    .replace(/_+/g, '_')
    .slice(0, 60) || 'untitled';
}

export default function DistillDialog({
  visible,
  sourceFile,
  sourceTitle,
  onCancel,
  onStartDistill,
  sendWSMessage,
  vaults = [],
}) {
  const [template, setTemplate] = useState('summary');
  const [prompt, setPrompt] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const [selectedVault, setSelectedVault] = useState('');
  const [selectedDir, setSelectedDir] = useState('knowledge/notes');
  const [expandedPaths, setExpandedPaths] = useState(new Set(['knowledge/notes']));
  const [treeItems, setTreeItems] = useState({});
  const { addTask } = useDistillTasks();

  const rootPath = selectedVault ? `knowledge/notes/${selectedVault}` : 'knowledge/notes';

  const reset = () => {
    setTemplate('summary');
    setPrompt('');
    setIsStarting(false);
    setSelectedVault('');
    setSelectedDir(rootPath);
    setExpandedPaths(new Set([rootPath]));
  };

  const handleCancel = () => {
    reset();
    onCancel();
  };

  const loadDirectory = useCallback(
    async (path) => {
      try {
        const response = await sendWSMessage('knowledge_list', { path });
        if (response.data?.items) {
          setTreeItems((prev) => ({ ...prev, [path]: response.data.items }));
        }
      } catch (err) {
        console.error('Failed to load directory:', err);
      }
    },
    [sendWSMessage]
  );

  const handleToggle = (path) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
        if (!treeItems[path]) {
          loadDirectory(path);
        }
      }
      return next;
    });
  };

  const effectiveRoot = selectedVault && selectedVault !== 'default' ? `knowledge/notes/${selectedVault}` : 'knowledge/notes';

  const handleStart = async () => {
    if (!sourceFile) return;

    setIsStarting(true);

    try {
      const timestamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 19);
      const safe = slugify(sourceTitle || sourceFile.split('/').pop() || 'distilled');
      const targetPath = `${selectedDir}/${timestamp}_${safe}.md`;

      // 添加任务到全局任务列表
      const taskId = addTask({
        sourceFile,
        template,
        prompt,
      });

      // 调用 onStartDistill 发送任务到后台（包含 vault）
      const result = await onStartDistill({ prompt, template, taskId, targetPath, vault: selectedVault || 'default' });

      // 关闭 Modal
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
            <span style={{ fontWeight: 600 }}>Distill: {sourceFile?.split('/').pop() || ''}</span>
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
          {/* Vault selector */}
          {vaults.length > 0 && (
            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>
                Target Vault
              </label>
              <select
                value={selectedVault}
                onChange={(e) => {
                  const vault = e.target.value;
                  setSelectedVault(vault);
                  const newRoot = vault ? `knowledge/notes/${vault}` : 'knowledge/notes';
                  setSelectedDir(newRoot);
                  setExpandedPaths(new Set([newRoot]));
                }}
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
            </div>
          )}

          {/* Output location */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>
              Save to (click to select folder)
            </label>
            <div
              style={{
                border: '1px solid var(--border)',
                borderRadius: 'var(--r-sm)',
                background: 'var(--surface)',
                padding: '8px 10px',
              }}
            >
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 6 }}>
                Selected: <strong style={{ color: 'var(--text)' }}>{selectedDir}</strong>
              </div>
              <DirectoryTree
                treeItems={treeItems}
                expandedPaths={expandedPaths}
                selectedDir={selectedDir}
                onToggle={handleToggle}
                onSelect={setSelectedDir}
                loadDirectory={loadDirectory}
                rootPath={effectiveRoot}
              />
            </div>
          </div>

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
            {isStarting ? 'Starting...' : 'Start Distillation'}
          </button>
        </div>
      </div>
    </div>
  );
}
