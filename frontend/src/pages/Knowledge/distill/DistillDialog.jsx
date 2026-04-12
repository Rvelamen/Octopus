import React, { useState } from 'react';
import { Sparkles, Check, X } from 'lucide-react';
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
  onCancel,
  onStartDistill,
}) {
  const [template, setTemplate] = useState('summary');
  const [prompt, setPrompt] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const { addTask } = useDistillTasks();

  const reset = () => {
    setTemplate('summary');
    setPrompt('');
    setIsStarting(false);
  };

  const handleCancel = () => {
    reset();
    onCancel();
  };

  const handleStart = async () => {
    if (!sourceFile) return;

    setIsStarting(true);

    try {
      // 添加任务到全局任务列表
      const taskId = addTask({
        sourceFile,
        template,
        prompt,
      });

      // 调用 onStartDistill 发送任务到后台
      const result = await onStartDistill({ prompt, template, taskId });

      // 如果后端返回了 job_id，更新任务 ID
      if (result?.job_id) {
        // 任务已在 addTask 时创建，这里可以更新 job_id 映射
        // 实际更新会通过 WebSocket 事件处理
      }

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
          minWidth: 520,
          maxWidth: '90vw',
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
