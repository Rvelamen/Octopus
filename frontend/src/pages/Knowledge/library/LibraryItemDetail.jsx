import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, FileText, ExternalLink, Calendar, Users, BookOpen, Hash, Sparkles, Link2, Copy, Trash2, Download, Edit2, Upload, FolderOpen, MessageSquare, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { Button, Tag, Popconfirm, Spin, message, Input, Modal } from 'antd';
import { useDistillTasks } from '@contexts/DistillTaskContext';
import LibraryAnnotationModal from './LibraryAnnotationModal';
import * as pdfjsLib from 'pdfjs-dist';

pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;

const LibraryItemDetail = ({ item, onClose, onDelete, onUpdateItem, onRefreshItem, sendWSMessage }) => {
  const [pdfContent, setPdfContent] = useState(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState(null);
  const [annotations, setAnnotations] = useState([]);
  const [noteFiles, setNoteFiles] = useState([]);
  const [noteGenerating, setNoteGenerating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [aiExtracting, setAiExtracting] = useState(false);
  const [annotationModalOpen, setAnnotationModalOpen] = useState(false);
  const thumbnailCanvasRef = useRef(null);
  const renderTaskRef = useRef(null);
  const pdfDocRef = useRef(null);
  const fileInputRef = useRef(null);
  const pdfLoadAbortRef = useRef(null);

  // 用原生 pdf.js 渲染缩略图，替代 react-pdf（避免 blob URL 兼容性问题）
  useEffect(() => {
    if (!pdfContent?.content || !thumbnailCanvasRef.current) return;
    let cancelled = false;

    const renderThumbnail = async () => {
      try {
        let bytes;
        if (pdfContent.encoding === 'hex') {
          const hex = pdfContent.content.replace(/\s/g, '');
          bytes = new Uint8Array(hex.match(/.{1,2}/g).map((b) => parseInt(b, 16)));
        } else {
          const binary = atob(pdfContent.content);
          bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        }

        const pdf = await pdfjsLib.getDocument({ data: bytes }).promise;
        if (cancelled) { pdf.destroy(); return; }
        pdfDocRef.current = pdf;

        const page = await pdf.getPage(1);
        if (cancelled) return;
        const viewport = page.getViewport({ scale: 1 });

        const canvas = thumbnailCanvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const width = 320;
        const scale = width / viewport.width;
        const scaledViewport = page.getViewport({ scale });

        canvas.width = scaledViewport.width * (window.devicePixelRatio || 1);
        canvas.height = scaledViewport.height * (window.devicePixelRatio || 1);
        canvas.style.width = `${scaledViewport.width}px`;
        canvas.style.height = `${scaledViewport.height}px`;
        ctx.setTransform(window.devicePixelRatio || 1, 0, 0, window.devicePixelRatio || 1, 0, 0);

        renderTaskRef.current = page.render({ canvasContext: ctx, viewport: scaledViewport });
        await renderTaskRef.current.promise;
      } catch (err) {
        if (!cancelled && err.name !== 'RenderingCancelledException') {
          console.error('Thumbnail render failed:', err);
        }
      }
    };

    renderThumbnail();
    return () => {
      cancelled = true;
      if (renderTaskRef.current) {
        try { renderTaskRef.current.cancel(); } catch {}
        renderTaskRef.current = null;
      }
      if (pdfDocRef.current) {
        try { pdfDocRef.current.destroy(); } catch {}
        pdfDocRef.current = null;
      }
    };
  }, [pdfContent]);

  // Load PDF content when item changes
  useEffect(() => {
    if (!item?.library_path) {
      setPdfContent(null);
      return;
    }

    // Cancel any in-flight PDF load from a previous item
    if (pdfLoadAbortRef.current) {
      pdfLoadAbortRef.current();
    }

    let isCancelled = false;
    pdfLoadAbortRef.current = () => { isCancelled = true; };

    const loadPdf = async () => {
      setPdfLoading(true);
      setPdfError(null);
      try {
        const pdfPath = `${item.library_path}/main.pdf`;
        const response = await sendWSMessage('workspace_read', { path: pdfPath }, 30000);
        if (isCancelled) return;
        if (response?.data?.content) {
          setPdfContent({
            content: response.data.content,
            encoding: response.data.encoding || 'hex',
          });
        } else {
          setPdfError('No PDF content');
        }
      } catch (e) {
        if (!isCancelled) {
          console.error('Failed to load PDF:', e);
          setPdfError('Failed to load PDF');
        }
      } finally {
        if (!isCancelled) {
          setPdfLoading(false);
        }
      }
    };

    loadPdf();
    return () => { isCancelled = true; };
  }, [item?.id, item?.library_path, sendWSMessage]);
  if (!item) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: 13,
          height: '100%',
        }}
      >
        Select a paper to view details
      </div>
    );
  }

  const handleOpenDoi = () => {
    if (item.doi) {
      window.open(`https://doi.org/${item.doi}`, '_blank');
    }
  };

  const handleOpenUrl = () => {
    if (item.url) {
      window.open(item.url, '_blank');
    }
  };

  // Auto-load annotations from SQLite
  const loadAnnotations = useCallback(async () => {
    if (!item?.id) return;
    try {
      const response = await sendWSMessage('library_annotations_load', { item_id: item.id }, 10000);
      if (response?.data?.annotations) {
        setAnnotations(response.data.annotations);
      }
    } catch {
      // Ignore error
    }
  }, [item?.id, sendWSMessage]);

  useEffect(() => {
    loadAnnotations();
  }, [loadAnnotations]);

  // Listen for annotation updates from PdfViewerWindow
  useEffect(() => {
    const handler = (e) => {
      if (e.detail?.item_id === item?.id) {
        loadAnnotations();
      }
    };
    window.addEventListener('library-annotations-updated', handler);
    return () => window.removeEventListener('library-annotations-updated', handler);
  }, [item?.id, loadAnnotations]);

  // Scan notes/ directory for generated AI notes
  useEffect(() => {
    if (!item?.library_path) return;
    let cancelled = false;
    const scanNotes = async () => {
      const notesDir = `${item.library_path}/notes`;
      try {
        // Ensure notes directory exists (creates if missing)
        try {
          await sendWSMessage('workspace_mkdir', { path: notesDir }, 5000);
        } catch {
          // Ignore mkdir errors
        }
        const response = await sendWSMessage('workspace_list', { path: notesDir }, 5000);
        if (response?.data?.items && !cancelled) {
          const mdFiles = response.data.items.filter((f) => f.name?.endsWith('.md'));
          setNoteFiles(mdFiles);
        }
      } catch {
        // Directory may not exist
        if (!cancelled) setNoteFiles([]);
      }
    };
    scanNotes();
    return () => { cancelled = true; };
  }, [item?.library_path, sendWSMessage]);

  const { addTask } = useDistillTasks();

  const doGenerateNote = async () => {
    if (!item?.id || !item.library_path) return;
    setNoteGenerating(true);
    try {
      const sourcePath = `${item.library_path}/main.pdf`;
      const outputPath = `${item.library_path}/notes/summary.md`;
      const taskId = `library-note-${item.id}-${Date.now()}`;
      const prompt = `Please read this academic paper and generate a comprehensive summary note in Markdown format with the following structure:

---
title: "${item.title || 'Untitled'}"
authors: [${(item.authors || []).map((a) => `"${a}"`).join(', ')}]
year: ${item.year || 'N/A'}
venue: "${item.venue || ''}"
tags: [${(item.tags || []).map((t) => `"${t}"`).join(', ')}]
---

## Summary
[A concise 2-3 paragraph summary of the paper's main contributions]

## Key Contributions
- [List the main contributions]

## Methodology
[Describe the methods/approaches used]

## Results
[Summarize the key findings and experimental results]

## Insights & Implications
[Your analysis of the paper's significance and potential impact]

## Related Work Connections
[How this work connects to other papers in the field, use [[wiki-links]] if relevant]

Please write in English, use academic tone, and include specific details from the paper.`;

      addTask({
        id: taskId,
        sourceFile: sourcePath,
        template: 'custom',
        prompt,
      });

      await sendWSMessage(
        'knowledge_distill',
        {
          source_path: sourcePath,
          prompt,
          target_path: outputPath,
          template: 'custom',
          vault: 'library',
          options: { task_id: taskId },
        },
        30000
      );
      message.success('AI note generation started. Check distill tasks for progress.');
    } catch (e) {
      message.error('Failed to start note generation');
    } finally {
      setNoteGenerating(false);
    }
  };

  const handleGenerateNote = () => {
    const hasSummary = noteFiles.some((f) => f.name === 'summary.md');
    if (hasSummary) {
      Modal.confirm({
        title: 'Regenerate AI Note?',
        content: 'A summary note (summary.md) already exists for this paper. Generating again will overwrite the existing file. Are you sure?',
        okText: 'Regenerate',
        okType: 'primary',
        cancelText: 'Cancel',
        onOk: doGenerateNote,
      });
    } else {
      doGenerateNote();
    }
  };

  const handleOpenAttachment = async (att) => {
    if (!item?.library_path || !att.rel_path) return;
    const filePath = `${item.library_path}/${att.rel_path}`;
    const ext = att.filename.split('.').pop()?.toLowerCase();

    // PDF → open in PdfViewerWindow (only for main.pdf)
    if (ext === 'pdf' && att.rel_path === 'main.pdf' && window.electronAPI?.openPdfWindow) {
      window.electronAPI.openPdfWindow(item.library_path, item.title, item.id);
      return;
    }

    // Markdown / Note → open in MarkdownEditorWindow
    if ((ext === 'md' || att.file_type === 'note') && window.electronAPI?.openMarkdownWindow) {
      window.electronAPI.openMarkdownWindow(filePath, att.filename);
      return;
    }

    // Others → download via blob
    try {
      const res = await sendWSMessage('workspace_read', { path: filePath }, 30000);
      if (res?.data?.content) {
        const enc = res.data.encoding || 'hex';
        if (enc === 'hex') {
          const hex = res.data.content.replace(/\s/g, '');
          const bytes = new Uint8Array(hex.match(/.{1,2}/g).map((b) => parseInt(b, 16)));
          const mimeMap = {
            pdf: 'application/pdf',
            md: 'text/markdown',
            txt: 'text/plain',
            png: 'image/png',
            jpg: 'image/jpeg',
            jpeg: 'image/jpeg',
            gif: 'image/gif',
            svg: 'image/svg+xml',
            xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            csv: 'text/csv',
            json: 'application/json',
            zip: 'application/zip',
          };
          const blob = new Blob([bytes], { type: mimeMap[ext] || 'application/octet-stream' });
          const url = URL.createObjectURL(blob);
          window.open(url, '_blank');
        } else {
          // utf-8 text content (e.g. markdown, txt, csv, json)
          const mimeMap = {
            md: 'text/markdown',
            txt: 'text/plain',
            csv: 'text/csv',
            json: 'application/json',
          };
          const blob = new Blob([res.data.content], { type: mimeMap[ext] || 'text/plain' });
          const url = URL.createObjectURL(blob);
          window.open(url, '_blank');
        }
      } else {
        message.error('Attachment content not found');
      }
    } catch (e) {
      message.error('Failed to open attachment');
    }
  };

  const handleUploadAttachment = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !item?.id) return;
    try {
      const arrayBuffer = await file.arrayBuffer();
      const bytes = new Uint8Array(arrayBuffer);
      const hex = Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
      const tempPath = `${item.library_path}/supplementary/_tmp_${Date.now()}_${file.name}`;
      await sendWSMessage('workspace_write', {
        path: tempPath,
        content: hex,
        encoding: 'hex',
      }, 30000);
      await sendWSMessage('library_add_attachment', {
        item_id: item.id,
        temp_path: tempPath,
        filename: file.name,
        file_type: 'supplementary',
      }, 30000);
      // Refresh item to show new attachment
      const res = await sendWSMessage('library_get', { item_id: item.id }, 30000);
      if (res?.data?.item && onRefreshItem) {
        onRefreshItem(res.data.item.id);
      }
      message.success('Attachment uploaded');
    } catch (err) {
      message.error('Failed to upload attachment');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };



  const handleCopyCitation = () => {
    // Generate APA-style citation
    const authors = item.authors || [];
    let authorStr = 'Unknown';
    if (authors.length === 1) {
      const parts = authors[0].split(' ');
      const lastName = parts.pop();
      authorStr = `${lastName}, ${parts.map((n) => n[0]).join('. ')}.`;
    } else if (authors.length === 2) {
      const a1 = authors[0].split(' ');
      const a2 = authors[1].split(' ');
      const l1 = a1.pop();
      const l2 = a2.pop();
      authorStr = `${l1}, ${a1.map((n) => n[0]).join('. ')}., & ${l2}, ${a2.map((n) => n[0]).join('. ')}.`;
    } else if (authors.length > 2) {
      const parts = authors[0].split(' ');
      const lastName = parts.pop();
      authorStr = `${lastName}, ${parts.map((n) => n[0]).join('. ')}. et al.`;
    }

    const year = item.year ? `(${item.year})` : '(n.d.)';
    const title = item.title || 'Untitled';
    const venue = item.venue ? `*${item.venue}*` : '';
    const doi = item.doi ? `https://doi.org/${item.doi}` : item.url || '';

    let citation = `${authorStr} ${year}. ${title}.`;
    if (venue) citation += ` ${venue}.`;
    if (doi) citation += ` ${doi}`;

    navigator.clipboard.writeText(citation);
    message.success('Citation copied to clipboard');
  };

  const startEditing = () => {
    setEditForm({
      title: item.title || '',
      authors: (item.authors || []).join(', '),
      year: item.year || '',
      venue: item.venue || '',
      doi: item.doi || '',
      url: item.url || '',
      abstract: item.abstract || '',
      tags: (item.tags || []).join(', '),
      citekey: item.citekey || '',
      item_type: item.item_type || 'journalArticle',
    });
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setEditForm({});
  };

  const handleAiExtract = async () => {
    if (!item?.id) return;
    setAiExtracting(true);
    try {
      const response = await sendWSMessage('library_ai_extract_meta', { item_id: item.id }, 120000);
      if (response?.data?.metadata) {
        const meta = response.data.metadata;
        setEditForm((prev) => ({
          ...prev,
          title: meta.title || prev.title,
          authors: (meta.authors || []).join(', '),
          year: meta.year || '',
          venue: meta.venue || '',
          doi: meta.doi || '',
          url: meta.url || '',
          abstract: meta.abstract || '',
          tags: (meta.tags || []).join(', '),
          citekey: meta.citekey || prev.citekey,
        }));
        message.success('AI extracted metadata filled in');
      } else {
        message.error('AI extraction returned no metadata');
      }
    } catch (e) {
      message.error('AI extraction failed');
    } finally {
      setAiExtracting(false);
    }
  };

  const handleSave = async () => {
    if (!onUpdateItem) return;
    setSaving(true);
    try {
      const metadata = {
        ...editForm,
        authors: editForm.authors
          ? editForm.authors.split(',').map((a) => a.trim()).filter(Boolean)
          : [],
        tags: editForm.tags
          ? editForm.tags.split(',').map((t) => t.trim()).filter(Boolean)
          : [],
        year: editForm.year ? parseInt(editForm.year, 10) || null : null,
      };
      await onUpdateItem(item.id, metadata);
      message.success('Metadata updated');
      setIsEditing(false);
    } catch (e) {
      message.error('Failed to update metadata');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field, value) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: 'var(--bg-elevated)',
        height: '100%',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
          Details
        </span>
        <span style={{ cursor: 'pointer', display: 'flex', color: 'var(--text-muted)' }} onClick={onClose}>
          <X size={16} />
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {/* PDF Preview - single page thumbnail */}
        <div
          style={{
            borderRadius: 8,
            background: 'var(--bg)',
            marginBottom: 16,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 160,
            width: '100%',
            boxSizing: 'border-box',
            padding: 8,
          }}
        >
          {pdfLoading ? (
            <Spin size="small" />
          ) : pdfError || !pdfContent ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, color: 'var(--text-muted)', padding: 24 }}>
              <FileText size={40} opacity={0.3} />
              <span style={{ fontSize: 12 }}>{pdfError || 'No PDF available'}</span>
            </div>
          ) : (
            <div style={{ maxWidth: '100%', overflow: 'hidden', lineHeight: 0 }}>
              <canvas ref={thumbnailCanvasRef} style={{ maxWidth: '100%', borderRadius: 4 }} />
            </div>
          )}
        </div>

        {/* Parse status */}
        {item.chunk_status && item.chunk_status !== 'completed' && (
          <div style={{ marginBottom: 8 }}>
            {item.chunk_status === 'pending' && (
              <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, background: 'var(--bg)', color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> PDF processing
              </span>
            )}
            {item.chunk_status === 'failed' && (
              <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, background: '#fff1f0', color: '#ff4d4f', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <XCircle size={12} /> PDF parsing failed
              </span>
            )}
            {item.chunk_status.startsWith('processing:') && (() => {
              const m = item.chunk_status.match(/processing:(\d+)\/(\d+)/);
              const current = m ? parseInt(m[1], 10) : 0;
              const total = m ? parseInt(m[2], 10) : 1;
              const pct = total > 0 ? Math.round((current / total) * 100) : 0;
              return (
                <span style={{ fontSize: 11, display: 'inline-flex', flexDirection: 'column', gap: 3, width: '100%' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--accent)' }}>
                    <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Parsing PDF {current}/{total} pages
                  </span>
                  <span style={{ height: 4, borderRadius: 2, background: 'var(--bg)', overflow: 'hidden', width: '100%' }}>
                    <span style={{ display: 'block', height: '100%', width: `${pct}%`, background: 'var(--accent)', borderRadius: 2, transition: 'width 0.3s ease' }} />
                  </span>
                </span>
              );
            })()}
          </div>
        )}

        {/* Title */}
        <div style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.5, marginBottom: 12, wordBreak: 'break-word' }}>
          {item.title || 'Untitled'}
        </div>

        {/* Meta fields */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
          {item.authors?.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <Users size={14} style={{ color: 'var(--text-muted)', marginTop: 2, flexShrink: 0 }} />
              <span style={{ fontSize: 13, wordBreak: 'break-word' }}>{item.authors.join(', ')}</span>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            {item.year && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Calendar size={14} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontSize: 13 }}>{item.year}</span>
              </div>
            )}
            {item.venue && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <BookOpen size={14} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontSize: 13 }}>{item.venue}</span>
              </div>
            )}
          </div>

          {item.citekey && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>CiteKey</span>
              <span style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--text)' }}>{item.citekey}</span>
            </div>
          )}

          {item.doi && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>DOI</span>
              <span
                style={{ fontSize: 12, color: 'var(--accent)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 2 }}
                onClick={handleOpenDoi}
              >
                {item.doi} <ExternalLink size={10} />
              </span>
            </div>
          )}

          {item.url && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>URL</span>
              <span
                style={{ fontSize: 12, color: 'var(--accent)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                onClick={handleOpenUrl}
              >
                {item.url} <ExternalLink size={10} />
              </span>
            </div>
          )}
        </div>

        {/* Tags */}
        {item.tags?.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Hash size={11} /> Tags
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {item.tags.map((tag) => (
                <Tag key={tag} size="small" color="processing">
                  {tag}
                </Tag>
              ))}
            </div>
          </div>
        )}

        {/* Collections */}
        {item.collections?.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>Collections</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {item.collections.map((c) => (
                <Tag key={c.id} size="small" color="default" style={{ borderColor: c.color, color: c.color }}>
                  {c.name}
                </Tag>
              ))}
            </div>
          </div>
        )}

        {/* Abstract */}
        {item.abstract && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600 }}>Abstract</div>
            <div style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text)', whiteSpace: 'pre-wrap' }}>
              {item.abstract}
            </div>
          </div>
        )}

        {/* Attachments */}
        <div style={{ marginBottom: 16 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 6,
            }}
          >
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>
              Attachments ({item.attachments?.length || 0})
            </span>
            <span
              style={{
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                color: 'var(--accent)',
                fontSize: 12,
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={12} />
              Upload
            </span>
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: 'none' }}
              onChange={handleUploadAttachment}
            />
          </div>
          {(item.attachments?.length > 0 || noteFiles.length > 0) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {item.attachments?.map((att) => (
                <div
                  key={att.id}
                  onClick={() => handleOpenAttachment(att)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 10px',
                    borderRadius: 4,
                    background: 'var(--bg)',
                    fontSize: 12,
                    cursor: 'pointer',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--accent-soft)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg)'; }}
                >
                  <FileText size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {att.filename}
                  </span>
                  {att.size && (
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>
                      {(att.size / 1024 / 1024).toFixed(2)} MB
                    </span>
                  )}
                  <span style={{ display: 'flex', color: 'var(--accent)', flexShrink: 0 }}>
                    <Download size={12} />
                  </span>
                </div>
              ))}
              {noteFiles.map((nf) => (
                <div
                  key={nf.name}
                  onClick={() => {
                    const filePath = `${item.library_path}/notes/${nf.name}`;
                    if (window.electronAPI?.openMarkdownWindow) {
                      window.electronAPI.openMarkdownWindow(filePath, nf.name);
                    }
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 10px',
                    borderRadius: 4,
                    background: 'var(--bg)',
                    fontSize: 12,
                    cursor: 'pointer',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--accent-soft)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg)'; }}
                >
                  <FileText size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {nf.name}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--accent)', flexShrink: 0, padding: '1px 6px', background: 'var(--accent-soft)', borderRadius: 3 }}>
                    note
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Annotations button */}
        <Button
          size="small"
          icon={<MessageSquare size={14} />}
          onClick={() => setAnnotationModalOpen(true)}
          style={{ marginBottom: 16 }}
        >
          Annotations {annotations.length > 0 && `(${annotations.length})`}
        </Button>

        <LibraryAnnotationModal
          open={annotationModalOpen}
          onClose={() => setAnnotationModalOpen(false)}
          annotations={annotations}
          onSave={async (updated) => {
            await sendWSMessage('library_annotations_save', {
              item_id: item.id,
              annotations: updated,
            }, 10000);
            setAnnotations(updated);
            window.dispatchEvent(
              new CustomEvent('library-annotations-updated', {
                detail: { item_id: item.id },
              })
            );
          }}
        />

        {/* Linked notes */}
        {item.linked_notes?.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600 }}>Linked Notes</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {item.linked_notes.map((ln) => (
                <div
                  key={ln.id}
                  style={{ fontSize: 12, color: 'var(--accent)', cursor: 'pointer' }}
                  onClick={() => {
                    if (window.electronAPI?.openMarkdownWindow) {
                      window.electronAPI.openMarkdownWindow(
                        ln.note_path,
                        ln.note_path.split('/').pop()
                      );
                    }
                  }}
                >
                  {ln.note_path}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
          {!isEditing && (
            <Button size="small" icon={<Edit2 size={14} />} onClick={startEditing}>
              Edit
            </Button>
          )}
          <Button
            size="small"
            icon={<FileText size={14} />}
            onClick={() => {
              if (window.electronAPI?.openPdfWindow) {
                window.electronAPI.openPdfWindow(item.library_path, item.title, item.id);
              } else {
                // Fallback: 浏览器环境直接在新标签页打开 blob
                const pdfPath = `${item.library_path}/main.pdf`;
                sendWSMessage('workspace_read', { path: pdfPath }, 30000).then((res) => {
                  if (res?.data?.content) {
                    let bytes;
                    const enc = res.data.encoding || 'hex';
                    if (enc === 'hex') {
                      const hex = res.data.content.replace(/\s/g, '');
                      bytes = new Uint8Array(hex.match(/.{1,2}/g).map((b) => parseInt(b, 16)));
                    } else {
                      const binary = atob(res.data.content);
                      bytes = new Uint8Array(binary.length);
                      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
                    }
                    const blob = new Blob([bytes], { type: 'application/pdf' });
                    const url = URL.createObjectURL(blob);
                    window.open(url, '_blank');
                  }
                });
              }
            }}
          >
            Open PDF
          </Button>
          <Button size="small" icon={<Sparkles size={14} />} loading={noteGenerating} onClick={handleGenerateNote}>
            AI Note
          </Button>
          <Button size="small" icon={<Copy size={14} />} onClick={handleCopyCitation}>
            Cite
          </Button>
          <Popconfirm
            title="Delete this paper?"
            onConfirm={onDelete}
            okText="Delete"
            cancelText="Cancel"
            okType="danger"
          >
            <Button size="small" danger icon={<Trash2 size={14} />}>
              Delete
            </Button>
          </Popconfirm>
        </div>
      </div>

      {/* Edit Modal */}
      <Modal
        title="Edit Paper Metadata"
        open={isEditing}
        onCancel={cancelEditing}
        footer={(
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Button
              icon={<Sparkles size={14} />}
              loading={aiExtracting}
              onClick={handleAiExtract}
            >
              AI Extract
            </Button>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={cancelEditing}>
                Cancel
              </Button>
              <Button type="primary" loading={saving} onClick={handleSave}>
                Save
              </Button>
            </div>
          </div>
        )}
        width={480}
        destroyOnHidden
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '8px 0' }}>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Title</label>
            <Input value={editForm.title} onChange={(e) => updateField('title', e.target.value)} placeholder="Paper title" />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Authors (comma separated)</label>
            <Input value={editForm.authors} onChange={(e) => updateField('authors', e.target.value)} placeholder="e.g. John Doe, Jane Smith" />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Year</label>
              <Input value={editForm.year} onChange={(e) => updateField('year', e.target.value)} placeholder="2024" />
            </div>
            <div style={{ flex: 2 }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Venue</label>
              <Input value={editForm.venue} onChange={(e) => updateField('venue', e.target.value)} placeholder="Journal or Conference" />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>DOI</label>
            <Input value={editForm.doi} onChange={(e) => updateField('doi', e.target.value)} placeholder="10.xxxx/xxxxx" />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>URL</label>
            <Input value={editForm.url} onChange={(e) => updateField('url', e.target.value)} placeholder="https://..." />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>CiteKey</label>
            <Input value={editForm.citekey} onChange={(e) => updateField('citekey', e.target.value)} placeholder="author2024title" />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Tags (comma separated)</label>
            <Input value={editForm.tags} onChange={(e) => updateField('tags', e.target.value)} placeholder="machine learning, nlp" />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, display: 'block' }}>Abstract</label>
            <Input.TextArea
              value={editForm.abstract}
              onChange={(e) => updateField('abstract', e.target.value)}
              placeholder="Paper abstract..."
              rows={5}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default LibraryItemDetail;
