import React, { useState, useRef } from 'react';
import { Upload, FileText, Globe, BookOpen, X, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { Modal, Tabs, Input, Button, TreeSelect, message, Progress } from 'antd';

const LibraryImportModal = ({ open, onClose, onImportPdf, onImportDoi, onImportArxiv, collections }) => {
  const [activeTab, setActiveTab] = useState('pdf');
  const [doi, setDoi] = useState('');
  const [arxivId, setArxivId] = useState('');
  const [selectedCollections, setSelectedCollections] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [importingType, setImportingType] = useState(null); // 'doi' | 'arxiv' | null
  const fileInputRef = useRef(null);

  // File upload states: array of { file, status: 'uploading'|'done'|'error', progress: 0-1, error?: string }
  const [uploads, setUploads] = useState([]);

  // Batch import states for DOI / arXiv
  const [doiImports, setDoiImports] = useState([]);
  const [arxivImports, setArxivImports] = useState([]);

  const collectionOptions = collections
    .filter((c) => c.id !== 1)
    .map((c) => ({
      value: c.id,
      title: c.name,
      children: c.children?.map((child) => ({
        value: child.id,
        title: child.name,
      })),
    }));

  const isUploading = uploads.some((u) => u.status === 'uploading');
  const isImporting = !!importingType || isUploading;

  const updateUpload = (file, updates) => {
    setUploads((prev) =>
      prev.map((u) => (u.file === file ? { ...u, ...updates } : u))
    );
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const files = Array.from(e.dataTransfer.files).filter((f) => f.name.endsWith('.pdf'));
    if (files.length > 0) {
      handlePdfImports(files);
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files).filter((f) => f.name.endsWith('.pdf'));
    if (files.length > 0) {
      handlePdfImports(files);
    }
  };

  const handlePdfImports = async (files) => {
    const newUploads = files.map((file) => ({ file, status: 'uploading', progress: 0 }));
    setUploads((prev) => [...prev, ...newUploads]);

    let successCount = 0;
    let failCount = 0;

    for (const upload of newUploads) {
      const { file } = upload;
      try {
        await onImportPdf(
          file,
          {},
          selectedCollections,
          (progress) => updateUpload(file, { progress })
        );
        updateUpload(file, { status: 'done', progress: 1 });
        successCount++;
      } catch (e) {
        updateUpload(file, { status: 'error', progress: 0, error: e.message || 'Failed' });
        failCount++;
      }
    }

    // Show summary toast
    if (failCount === 0) {
      message.success(`${successCount} PDF(s) imported successfully`);
      setTimeout(() => {
        setUploads([]);
        onClose();
      }, 800);
    } else if (successCount > 0) {
      message.warning(`${successCount} succeeded, ${failCount} failed`);
    } else {
      message.error(`All ${failCount} upload(s) failed`);
    }
  };

  const parseBatchLines = (text) => {
    return text
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
  };

  const handleDoiImport = async () => {
    const lines = parseBatchLines(doi);
    if (lines.length === 0) {
      message.error('Please enter at least one DOI');
      return;
    }
    const items = lines.map((line, idx) => ({ id: idx, value: line, status: 'importing', error: null }));
    setDoiImports(items);
    setImportingType('doi');

    let successCount = 0;
    let failCount = 0;

    for (const item of items) {
      try {
        await onImportDoi(item.value, selectedCollections);
        successCount++;
        setDoiImports((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: 'done' } : i)));
      } catch (e) {
        failCount++;
        setDoiImports((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: 'error', error: e.message || 'Failed' } : i)));
      }
    }

    if (failCount === 0) {
      message.success(`${successCount} DOI(s) imported successfully`);
      setDoi('');
      setDoiImports([]);
      setTimeout(() => onClose(), 800);
    } else if (successCount > 0) {
      message.warning(`${successCount} succeeded, ${failCount} failed`);
    } else {
      message.error(`All ${failCount} DOI import(s) failed`);
    }
    setImportingType(null);
  };

  const handleArxivImport = async () => {
    const lines = parseBatchLines(arxivId);
    if (lines.length === 0) {
      message.error('Please enter at least one arXiv ID or URL');
      return;
    }
    const items = lines.map((line, idx) => ({ id: idx, value: line, status: 'importing', error: null }));
    setArxivImports(items);
    setImportingType('arxiv');

    let successCount = 0;
    let failCount = 0;

    for (const item of items) {
      try {
        await onImportArxiv(item.value, selectedCollections);
        successCount++;
        setArxivImports((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: 'done' } : i)));
      } catch (e) {
        failCount++;
        setArxivImports((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: 'error', error: e.message || 'Failed' } : i)));
      }
    }

    if (failCount === 0) {
      message.success(`${successCount} arXiv paper(s) imported successfully`);
      setArxivId('');
      setArxivImports([]);
      setTimeout(() => onClose(), 800);
    } else if (successCount > 0) {
      message.warning(`${successCount} succeeded, ${failCount} failed`);
    } else {
      message.error(`All ${failCount} arXiv import(s) failed`);
    }
    setImportingType(null);
  };

  const handleRetryDoi = async (itemId) => {
    const item = doiImports.find((i) => i.id === itemId);
    if (!item) return;
    setDoiImports((prev) => prev.map((i) => (i.id === itemId ? { ...i, status: 'importing', error: null } : i)));
    try {
      await onImportDoi(item.value, selectedCollections);
      setDoiImports((prev) => prev.map((i) => (i.id === itemId ? { ...i, status: 'done', error: null } : i)));
      message.success(`Retried DOI imported: ${item.value}`);
    } catch (e) {
      setDoiImports((prev) => prev.map((i) => (i.id === itemId ? { ...i, status: 'error', error: e.message || 'Failed' } : i)));
      message.error(`Retry failed: ${item.value}`);
    }
  };

  const handleRetryArxiv = async (itemId) => {
    const item = arxivImports.find((i) => i.id === itemId);
    if (!item) return;
    setArxivImports((prev) => prev.map((i) => (i.id === itemId ? { ...i, status: 'importing', error: null } : i)));
    try {
      await onImportArxiv(item.value, selectedCollections);
      setArxivImports((prev) => prev.map((i) => (i.id === itemId ? { ...i, status: 'done', error: null } : i)));
      message.success(`Retried arXiv imported: ${item.value}`);
    } catch (e) {
      setArxivImports((prev) => prev.map((i) => (i.id === itemId ? { ...i, status: 'error', error: e.message || 'Failed' } : i)));
      message.error(`Retry failed: ${item.value}`);
    }
  };

  const removeUpload = (file) => {
    setUploads((prev) => prev.filter((u) => u.file !== file));
  };

  const formatBytes = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const renderImportList = (items, onRetry) => {
    if (items.length === 0) return null;
    return (
      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.map((item) => (
          <div
            key={item.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 10px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: 'var(--surface)',
              fontSize: 12,
            }}
          >
            {item.status === 'importing' && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent)', flexShrink: 0 }} />}
            {item.status === 'done' && <CheckCircle2 size={14} style={{ color: 'var(--accent-green)', flexShrink: 0 }} />}
            {item.status === 'error' && <AlertCircle size={14} style={{ color: 'var(--accent-red)', flexShrink: 0 }} />}
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={item.value}>
              {item.value}
            </span>
            {item.error && <span style={{ color: 'var(--accent-red)', fontSize: 11, flexShrink: 0 }}>{item.error}</span>}
            {item.status === 'error' && onRetry && (
              <Button
                size="small"
                type="link"
                onClick={() => onRetry(item.id)}
                style={{ padding: 0, fontSize: 11, height: 'auto', lineHeight: 'inherit' }}
              >
                Retry
              </Button>
            )}
          </div>
        ))}
      </div>
    );
  };

  const tabItems = [
    {
      key: 'pdf',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <FileText size={14} /> PDF
        </span>
      ),
      children: (
        <div style={{ padding: '8px 0' }}>
          {/* Drop zone */}
          <div
            onDragEnter={() => setDragActive(true)}
            onDragLeave={() => setDragActive(false)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleFileDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `2px dashed ${dragActive ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 8,
              padding: 40,
              textAlign: 'center',
              cursor: 'pointer',
              background: dragActive ? 'var(--accent-soft)' : 'transparent',
              transition: 'all 0.2s',
            }}
          >
            <Upload size={32} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
            <div style={{ fontSize: 14, color: 'var(--text)' }}>Drop PDF(s) here or click to select</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
              Supports multiple PDF files
            </div>
            <input ref={fileInputRef} type="file" accept=".pdf" multiple style={{ display: 'none' }} onChange={handleFileSelect} />
          </div>

          {/* Upload list */}
          {uploads.length > 0 && (
            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {uploads.map((u) => (
                <div
                  key={u.file.name}
                  style={{
                    padding: 10,
                    borderRadius: 6,
                    border: '1px solid var(--border)',
                    background: 'var(--surface)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                      {u.status === 'uploading' && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent)', flexShrink: 0 }} />}
                      {u.status === 'done' && <CheckCircle2 size={14} style={{ color: 'var(--accent-green)', flexShrink: 0 }} />}
                      {u.status === 'error' && <AlertCircle size={14} style={{ color: 'var(--accent-red)', flexShrink: 0 }} />}
                      <span style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={u.file.name}>
                        {u.file.name}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>
                        {formatBytes(u.file.size)}
                      </span>
                    </div>
                    <button
                      onClick={() => removeUpload(u.file)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2, display: 'flex' }}
                    >
                      <X size={12} />
                    </button>
                  </div>
                  {u.status === 'uploading' && (
                    <Progress percent={Math.round(u.progress * 100)} size="small" strokeColor="var(--accent)" showInfo={false} />
                  )}
                  {u.status === 'error' && (
                    <div style={{ fontSize: 11, color: 'var(--accent-red)' }}>{u.error}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'doi',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Globe size={14} /> DOI
        </span>
      ),
      children: (
        <div style={{ padding: '8px 0' }}>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
              DOI (one per line)
            </label>
            <Input.TextArea
              placeholder="10.48550/arXiv.1706.03762&#10;10.1038/s41586-020-2649-2"
              value={doi}
              onChange={(e) => setDoi(e.target.value)}
              rows={4}
              disabled={importingType === 'doi'}
            />
          </div>
          <Button
            type="primary"
            onClick={handleDoiImport}
            loading={importingType === 'doi'}
            disabled={importingType === 'doi'}
            block
          >
            {importingType === 'doi'
              ? 'Importing...'
              : `Import ${parseBatchLines(doi).length > 0 ? parseBatchLines(doi).length + ' ' : ''}DOI`}
          </Button>
          {renderImportList(doiImports, handleRetryDoi)}
        </div>
      ),
    },
    {
      key: 'arxiv',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <BookOpen size={14} /> arXiv
        </span>
      ),
      children: (
        <div style={{ padding: '8px 0' }}>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
              arXiv ID or URL (one per line)
            </label>
            <Input.TextArea
              placeholder="1706.03762&#10;https://arxiv.org/abs/2603.12644"
              value={arxivId}
              onChange={(e) => setArxivId(e.target.value)}
              rows={4}
              disabled={importingType === 'arxiv'}
            />
          </div>
          <Button
            type="primary"
            onClick={handleArxivImport}
            loading={importingType === 'arxiv'}
            disabled={importingType === 'arxiv'}
            block
          >
            {importingType === 'arxiv'
              ? 'Importing...'
              : `Import ${parseBatchLines(arxivId).length > 0 ? parseBatchLines(arxivId).length + ' ' : ''}arXiv`}
          </Button>
          {renderImportList(arxivImports, handleRetryArxiv)}
        </div>
      ),
    },
  ];

  return (
    <Modal
      title="Import Paper"
      open={open}
      onCancel={() => {
        if (!isImporting) {
          setUploads([]);
          setDoiImports([]);
          setArxivImports([]);
          onClose();
        }
      }}
      footer={null}
      width={520}
      closable={!isImporting}
      mask={{ closable: !isImporting }}
    >
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Target Collection (optional)</label>
        <TreeSelect
          style={{ width: '100%' }}
          treeData={collectionOptions}
          placeholder="Select collections..."
          treeCheckable
          showCheckedStrategy={TreeSelect.SHOW_PARENT}
          value={selectedCollections}
          onChange={setSelectedCollections}
          allowClear
          disabled={isImporting}
        />
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </Modal>
  );
};

export default LibraryImportModal;
