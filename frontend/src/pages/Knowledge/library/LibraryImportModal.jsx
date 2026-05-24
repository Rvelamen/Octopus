import React, { useState, useRef } from 'react';
import { Upload, FileText, Globe, BookOpen } from 'lucide-react';
import { Modal, Tabs, Input, Button, TreeSelect, message } from 'antd';

const LibraryImportModal = ({ open, onClose, onImportPdf, onImportDoi, onImportArxiv, collections }) => {
  const [activeTab, setActiveTab] = useState('pdf');
  const [doi, setDoi] = useState('');
  const [arxivId, setArxivId] = useState('');
  const [selectedCollections, setSelectedCollections] = useState([]);
  const [importing, setImporting] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

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

  const handleFileDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handlePdfImport(files[0]);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      handlePdfImport(file);
    }
  };

  const handlePdfImport = async (file) => {
    if (!file.name.endsWith('.pdf')) {
      message.error('Please select a PDF file');
      return;
    }
    setImporting(true);
    try {
      await onImportPdf(file, {}, selectedCollections);
      message.success('PDF imported successfully');
      onClose();
    } catch (e) {
      message.error('Failed to import PDF');
    } finally {
      setImporting(false);
    }
  };

  const handleDoiImport = async () => {
    if (!doi.trim()) {
      message.error('Please enter a DOI');
      return;
    }
    setImporting(true);
    try {
      await onImportDoi(doi.trim(), selectedCollections);
      message.success('DOI imported successfully');
      onClose();
    } catch (e) {
      message.error('Failed to import DOI');
    } finally {
      setImporting(false);
    }
  };

  const handleArxivImport = async () => {
    if (!arxivId.trim()) {
      message.error('Please enter an arXiv ID');
      return;
    }
    setImporting(true);
    try {
      await onImportArxiv(arxivId.trim(), selectedCollections);
      message.success('arXiv imported successfully');
      onClose();
    } catch (e) {
      message.error('Failed to import arXiv');
    } finally {
      setImporting(false);
    }
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
            <div style={{ fontSize: 14, color: 'var(--text)' }}>Drop PDF here or click to select</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>Supports single PDF file</div>
            <input ref={fileInputRef} type="file" accept=".pdf" style={{ display: 'none' }} onChange={handleFileSelect} />
          </div>
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
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>DOI</label>
            <Input
              placeholder="10.48550/arXiv.1706.03762"
              value={doi}
              onChange={(e) => setDoi(e.target.value)}
            />
          </div>
          <Button type="primary" onClick={handleDoiImport} loading={importing} block>
            Import by DOI
          </Button>
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
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>arXiv ID or URL</label>
            <Input
              placeholder="1706.03762 or https://arxiv.org/abs/1706.03762"
              value={arxivId}
              onChange={(e) => setArxivId(e.target.value)}
            />
          </div>
          <Button type="primary" onClick={handleArxivImport} loading={importing} block>
            Import from arXiv
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Modal
      title="Import Paper"
      open={open}
      onCancel={onClose}
      footer={null}
      width={480}
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
        />
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </Modal>
  );
};

export default LibraryImportModal;
