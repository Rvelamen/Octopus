import React, { useState } from 'react';
import { message } from 'antd';
import { Sparkles, RotateCcw, Check, X, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
  onConfirm,
  onPreview,
}) {
  const [template, setTemplate] = useState('summary');
  const [prompt, setPrompt] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewMarkdown, setPreviewMarkdown] = useState('');
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [previewJobId, setPreviewJobId] = useState(null);
  const [previewStatus, setPreviewStatus] = useState(null);

  const reset = () => {
    setTemplate('summary');
    setPrompt('');
    setPreviewMarkdown('');
    setPreviewLoading(false);
    setConfirmLoading(false);
    setPreviewJobId(null);
    setPreviewStatus(null);
  };

  const handleCancel = () => {
    reset();
    onCancel();
  };

  const handlePreview = async () => {
    setPreviewLoading(true);
    setPreviewStatus({ stage: 'queued', message: 'Queued...', progress: 0 });
    try {
      const result = await onPreview({ prompt, template });
      
      // 检查是否是队列模式
      if (result && result.job_id) {
        setPreviewJobId(result.job_id);
        setPreviewStatus({ 
          stage: 'queued', 
          message: result.message || 'Task queued, waiting...', 
          progress: 0 
        });
        // 不设置 previewLoading=false，等待进度事件
      } else {
        // 同步模式，直接返回 markdown
        setPreviewMarkdown(result?.markdown || '');
        setPreviewLoading(false);
      }
    } catch (err) {
      setPreviewLoading(false);
      setPreviewStatus(null);
    }
  };

  // 暴露更新进度的方法（供父组件调用）
  React.useImperativeHandle(null, () => ({
    updateProgress: (data) => {
      setPreviewStatus({
        stage: data.stage,
        message: data.message,
        progress: data.progress,
      });

      if (data.stage === 'completed') {
        // Preview 完成：优先使用 markdown，其次使用 output_path
        setPreviewLoading(false);
        setPreviewStatus(null);
        if (data.markdown) {
          setPreviewMarkdown(data.markdown);
        }
        message.success('Preview complete!');
      } else if (data.stage === 'failed') {
        setPreviewLoading(false);
        setPreviewStatus(null);
        message.error('Preview failed: ' + data.message);
      }
    },
  }));

  const handleConfirm = async () => {
    // 如果有 previewMarkdown，直接使用；否则让后端重新生成
    setConfirmLoading(true);
    try {
      await onConfirm({ prompt, template, previewMarkdown });
      reset();
    } finally {
      setConfirmLoading(false);
    }
  };

  // 监听预览进度事件
  React.useEffect(() => {
    const handler = async (e) => {
      const { stage, message: msg, progress, output_path } = e.detail;
      
      setPreviewStatus({
        stage,
        message: msg,
        progress,
      });
      
      if (stage === 'completed') {
        // 预览完成，直接使用后端推送的 markdown
        setPreviewStatus(null);
        setPreviewLoading(false);
        if (e.detail.markdown) {
          setPreviewMarkdown(e.detail.markdown);
        }
        message.success('Preview complete!');
      } else if (stage === 'failed') {
        setPreviewStatus(null);
        setPreviewLoading(false);
        message.error('Preview failed: ' + msg);
      }
    };
    
    window.addEventListener('knowledge-distill-preview-progress', handler);
    return () => window.removeEventListener('knowledge-distill-preview-progress', handler);
  }, [message, onPreview, prompt, template]);

  if (!visible) return null;

  const showPromptBox = template === 'custom' || true; // allow extra prompt for all templates

  return (
    <div className="dialog-overlay" onClick={handleCancel}>
      <div
        className="dialog-content"
        style={{
          minWidth: previewMarkdown ? 840 : 520,
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
            <span style={{ fontWeight: 600 }}>Distill: {sourceFile}</span>
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
                  onClick={() => {
                    setTemplate(t.key);
                    setPreviewMarkdown('');
                  }}
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
          {showPromptBox && (
            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>
                {template === 'custom' ? 'Instructions' : 'Additional instructions (optional)'}
              </label>
              <textarea
                rows={3}
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
          )}

          {/* Preview result */}
          {(previewMarkdown || previewStatus) && (
            <div style={{ display: 'flex', gap: 12, minHeight: 0, flex: 1 }}>
              <div
                style={{
                  flex: 1,
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  background: 'var(--surface)',
                  overflow: 'auto',
                  maxHeight: '48vh',
                }}
              >
                <div
                  style={{
                    position: 'sticky',
                    top: 0,
                    background: 'var(--surface-2)',
                    padding: '8px 12px',
                    borderBottom: '1px solid var(--border)',
                    fontSize: 12,
                    fontWeight: 600,
                    color: 'var(--text)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <FileText size={14} />
                    Preview
                  </div>
                  {previewStatus && (
                    <div style={{ fontSize: 11, color: 'var(--text-2)' }}>
                      {previewStatus.message} ({Math.round(previewStatus.progress * 100)}%)
                    </div>
                  )}
                </div>
                
                {previewStatus && !previewMarkdown && (
                  <div style={{ padding: 20, textAlign: 'center' }}>
                    <div style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 12 }}>
                      {previewStatus.message}
                    </div>
                    {/* Progress bar */}
                    <div style={{
                      width: '100%',
                      height: 4,
                      background: 'var(--border)',
                      borderRadius: 2,
                      overflow: 'hidden',
                    }}>
                      <div style={{
                        width: `${previewStatus.progress * 100}%`,
                        height: '100%',
                        background: 'var(--accent)',
                        transition: 'width 0.3s ease',
                      }} />
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 8 }}>
                      Stage: {previewStatus.stage}
                    </div>
                  </div>
                )}
                
                {previewMarkdown && (
                  <div style={{ padding: 14, fontSize: 13, lineHeight: 1.6 }} className="markdown-preview">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{previewMarkdown}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="dialog-footer" style={{ justifyContent: previewMarkdown ? 'space-between' : 'flex-end', gap: 10 }}>
          {previewMarkdown ? (
            <>
              <button
                className="pixel-button secondary"
                onClick={handlePreview}
                disabled={previewLoading || confirmLoading}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <RotateCcw size={14} />
                {previewLoading ? 'Generating...' : 'Regenerate'}
              </button>
              <div style={{ display: 'flex', gap: 10 }}>
                <button className="pixel-button secondary" onClick={handleCancel} disabled={confirmLoading}>
                  Cancel
                </button>
                <button
                  className={`pixel-button ${confirmLoading ? 'loading' : ''}`}
                  onClick={handleConfirm}
                  disabled={confirmLoading}
                  style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  <Check size={14} />
                  {confirmLoading ? '' : 'Confirm & Distill'}
                </button>
              </div>
            </>
          ) : (
            <>
              <button className="pixel-button secondary" onClick={handleCancel} disabled={previewLoading}>
                Cancel
              </button>
              <button
                className={`pixel-button ${previewLoading ? 'loading' : ''}`}
                onClick={handlePreview}
                disabled={previewLoading}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <Sparkles size={14} />
                {previewLoading ? 'Generating...' : 'Preview'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
