import React, { useState, useEffect, useCallback } from 'react';
import { File, Sparkles, X, FileText, StickyNote, GitGraph, ListTodo } from 'lucide-react';
import { message, Modal } from 'antd';
import WindowDots from '../../WindowDots';
import KnowledgeGraphTab from './KnowledgeGraphTab';
import DistillDialog from './DistillDialog';
import KnowledgeTree from './KnowledgeTree';
import NoteEditor from './NoteEditor';
import UploadDropzone from './UploadDropzone';
import DistillTaskList from './DistillTaskList';
import NewNoteModal from './NewNoteModal';
import KnowledgeBinaryPreview from './KnowledgeBinaryPreview';
import DocumentGridView from './DocumentGridView';

const TABS = [
  { key: 'documents', label: 'DOCUMENTS', icon: FileText },
  { key: 'notes', label: 'NOTES', icon: StickyNote },
  { key: 'graph', label: 'GRAPH', icon: GitGraph },
  { key: 'distill-tasks', label: 'DISTILL TASKS', icon: ListTodo },
];

export default function KnowledgePanel({ sendWSMessage }) {
  const [activeTab, setActiveTab] = useState('documents');
  const [treeItems, setTreeItems] = useState({});
  const [selectedPath, setSelectedPath] = useState(null);
  const [content, setContent] = useState('');
  const [expandedPaths, setExpandedPaths] = useState(new Set());
  const [distillDialogVisible, setDistillDialogVisible] = useState(false);
  const [distillProgress, setDistillProgress] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isNewNoteModalOpen, setIsNewNoteModalOpen] = useState(false);
  const [newNoteTitle, setNewNoteTitle] = useState('');
  const [fileEncoding, setFileEncoding] = useState('utf-8');
  const [noteTags, setNoteTags] = useState([]);
  const [graphTagFilter, setGraphTagFilter] = useState(null);
  const [distillTasks, setDistillTasks] = useState([]);
  const [expandedDistillTask, setExpandedDistillTask] = useState(null);
  const [taskDetailResult, setTaskDetailResult] = useState(null);
  const [currentDocPath, setCurrentDocPath] = useState('knowledge/raw');
  const [selectedDocItem, setSelectedDocItem] = useState(null);
  const [docPreviewFile, setDocPreviewFile] = useState(null);

  const rootPath = activeTab === 'documents' ? 'knowledge/raw' : 'knowledge/notes';

  const loadDirectory = useCallback(
    async (path) => {
      try {
        const response = await sendWSMessage('knowledge_list', { path });
        if (response.data?.items) {
          setTreeItems((prev) => ({ ...prev, [path]: response.data.items }));
          return response.data.items;
        }
        return [];
      } catch (err) {
        message.error('Failed to load directory: ' + err.message);
        return [];
      }
    },
    [sendWSMessage]
  );

  const readFile = useCallback(
    async (path) => {
      try {
        const response = await sendWSMessage('knowledge_read', { path });
        const encoding = response.data?.encoding || 'utf-8';
        setFileEncoding(encoding);
        setContent(response.data?.content || '');
        setSelectedPath(path);
        if (path.endsWith('.md')) {
          try {
            const tagResp = await sendWSMessage('knowledge_get_tags', {});
            const allTags = tagResp.data?.tags || [];
            const text = response.data?.content || '';
            const found = new Set();
            const matches = text.match(/(?<!\w)#([\w\u4e00-\u9fa5\-]+)/g);
            if (matches) {
              matches.forEach((m) => {
                const t = m.replace(/^#/, '').toLowerCase();
                if (t) found.add(t);
              });
            }
            setNoteTags(Array.from(found));
          } catch {
            setNoteTags([]);
          }
        } else {
          setNoteTags([]);
        }
      } catch (err) {
        message.error('Failed to read file: ' + err.message);
      }
    },
    [sendWSMessage]
  );

  const writeFile = useCallback(
    async (newContent) => {
      if (!selectedPath) return;
      try {
        await sendWSMessage('knowledge_write', { path: selectedPath, content: newContent });
        message.success('Saved successfully');
      } catch (err) {
        message.error('Failed to save file: ' + err.message);
        throw err;
      }
    },
    [sendWSMessage, selectedPath]
  );

  const handleToggle = useCallback(
    async (path) => {
      const isExpanded = expandedPaths.has(path);
      setExpandedPaths((prev) => {
        const next = new Set(prev);
        if (isExpanded) {
          next.delete(path);
        } else {
          next.add(path);
        }
        return next;
      });
      if (!isExpanded && !treeItems[path]) {
        await loadDirectory(path);
      }
    },
    [expandedPaths, treeItems, loadDirectory]
  );

  const handleSelect = useCallback(
    (item) => {
      setSelectedPath(item.path);
      if (item.is_directory) {
        setExpandedPaths((prev) => {
          if (!prev.has(item.path)) {
            const next = new Set(prev);
            next.add(item.path);
            if (!treeItems[item.path]) {
              loadDirectory(item.path);
            }
            return next;
          }
          return prev;
        });
      } else {
        readFile(item.path);
      }
    },
    [readFile, treeItems, loadDirectory]
  );

  const handleDocNavigate = useCallback((path) => {
    setCurrentDocPath(path);
    setSelectedDocItem(null);
    setDocPreviewFile(null);
  }, []);

  const handleDocSelect = useCallback((item) => {
    setSelectedDocItem(item);
  }, []);

  const handleDocFileOpen = useCallback((item) => {
    if (item.is_directory) return;
    setDocPreviewFile(item);
    setSelectedPath(item.path);
    readFile(item.path);
  }, [readFile]);

  const handleCreateFolder = useCallback(async () => {
    Modal.confirm({
      title: 'New Folder',
      content: (
        <input
          id="new-folder-input"
          placeholder="Folder name"
          defaultValue="New Folder"
          style={{
            width: '100%',
            padding: '8px 12px',
            borderRadius: 6,
            border: '1px solid var(--border)',
            background: 'var(--bg)',
            color: 'var(--text)',
            fontSize: 14,
          }}
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              const btn = document.querySelector('.ant-modal-confirm-btns .ant-btn-primary');
              if (btn) btn.click();
            }
          }}
        />
      ),
      okText: 'Create',
      cancelText: 'Cancel',
      onOk: async () => {
        const input = document.getElementById('new-folder-input');
        const name = input?.value;
        if (!name || !name.trim()) return Promise.reject();
        const safeName = name.replace(/[^a-zA-Z0-9一-龥_\- .]/g, '').trim();
        if (!safeName) return Promise.reject();
        const newPath = `${currentDocPath}/${safeName}`;
        try {
          await sendWSMessage('workspace_mkdir', { path: newPath });
          message.success(`Created folder: ${safeName}`);
          await loadDirectory(currentDocPath);
        } catch (err) {
          message.error('Failed to create folder: ' + (err.message || String(err)));
          return Promise.reject();
        }
      },
    });
  }, [currentDocPath, loadDirectory, sendWSMessage]);

  useEffect(() => {
    setSelectedPath(null);
    setContent('');
    if (activeTab === 'documents') {
      setCurrentDocPath('knowledge/raw');
      setSelectedDocItem(null);
      setDocPreviewFile(null);
    }
    loadDirectory(rootPath);
    setExpandedPaths(new Set([rootPath]));
  }, [rootPath, loadDirectory, activeTab]);

  const loadDistillTasks = useCallback(async () => {
    try {
      const resp = await sendWSMessage('knowledge_distill_list', { limit: 50 });
      setDistillTasks(resp.data?.tasks || []);
    } catch {
      // ignore
    }
  }, [sendWSMessage]);

  const handleExpandDistillTask = useCallback(async (taskId) => {
    if (expandedDistillTask === taskId) {
      setExpandedDistillTask(null);
      setTaskDetailResult(null);
      return;
    }
    setExpandedDistillTask(taskId);
    try {
      const resp = await sendWSMessage('knowledge_distill_detail', { task_id: taskId });
      setTaskDetailResult(resp.data?.result || null);
    } catch {
      setTaskDetailResult(null);
    }
  }, [expandedDistillTask, sendWSMessage]);

  useEffect(() => {
    loadDistillTasks();
    const timer = setInterval(loadDistillTasks, 5000);
    return () => clearInterval(timer);
  }, [loadDistillTasks]);

  useEffect(() => {
    const handler = (e) => {
      const { stage, message: msg, progress, output_path, request_id } = e.detail;
      setDistillProgress({ stage, message: msg, progress });
      if (stage === 'completed' && output_path) {
        message.success('Distillation complete!');
        setActiveTab('notes');
        readFile(output_path);
        setDistillProgress(null);
        loadDistillTasks();
      } else if (stage === 'failed') {
        message.error('Distillation failed: ' + msg);
        setDistillProgress(null);
        loadDistillTasks();
      }
      window.dispatchEvent(new CustomEvent('knowledge-distill-preview-progress', {
        detail: { request_id, stage, message: msg, progress, output_path, markdown: e.detail.markdown }
      }));
    };
    window.addEventListener('knowledge-distill-progress', handler);
    return () => window.removeEventListener('knowledge-distill-progress', handler);
  }, [readFile, loadDistillTasks]);

  useEffect(() => {
    let timer = null;
    const checkTasks = async () => {
      try {
        const resp = await sendWSMessage('knowledge_distill_list', { limit: 5 });
        const tasks = resp.data?.tasks || [];
        const running = tasks.find((t) => t.status === 'running');
        if (running) {
          setDistillProgress({
            stage: running.stage,
            message: running.message,
            progress: running.progress,
          });
        } else {
          setDistillProgress(null);
        }
      } catch {
        // ignore
      }
    };
    checkTasks();
    timer = setInterval(checkTasks, 5000);
    return () => clearInterval(timer);
  }, [sendWSMessage]);

  const uploadFile = async (file, targetDir = null) => {
    if (!file) return;
    const MAX_SIZE = 20 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      message.error('File too large (max 20MB)');
      return;
    }
    setIsUploading(true);
    setUploadProgress(0);
    try {
      const uploadDir = targetDir || rootPath;
      const targetPath = `${uploadDir}/${file.name}`;
      const textExts = ['txt', 'md', 'csv', 'json', 'yaml', 'yml', 'xml', 'js', 'ts', 'py', 'html', 'css'];
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      const isText = textExts.includes(ext);
      const FAST_PATH_LIMIT = 2 * 1024 * 1024;

      if (isText && file.size <= FAST_PATH_LIMIT) {
        const text = await file.text();
        await sendWSMessage('workspace_write', {
          path: targetPath,
          content: text,
          encoding: 'utf-8',
        });
      } else if (file.size <= FAST_PATH_LIMIT) {
        const arrayBuffer = await file.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        const hex = Array.from(bytes)
          .map((b) => b.toString(16).padStart(2, '0'))
          .join('');
        await sendWSMessage(
          'workspace_write',
          {
            path: targetPath,
            content: hex,
            encoding: 'hex',
          },
          60000
        );
      } else {
        const arrayBuffer = await file.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        const CHUNK_SIZE = 256 * 1024;
        const totalChunks = Math.ceil(bytes.length / CHUNK_SIZE);
        const uploadId = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}_${Math.random()}`;

        for (let i = 0; i < totalChunks; i++) {
          const start = i * CHUNK_SIZE;
          const end = Math.min(start + CHUNK_SIZE, bytes.length);
          const slice = bytes.subarray(start, end);
          const hex = Array.from(slice)
            .map((b) => b.toString(16).padStart(2, '0'))
            .join('');
          await sendWSMessage(
            'workspace_write_chunk',
            {
              upload_id: uploadId,
              path: targetPath,
              chunk_index: i,
              total_chunks: totalChunks,
              content: hex,
              encoding: 'hex',
            },
            30000
          );
          setUploadProgress(Math.round(((i + 1) / totalChunks) * 100));
        }
      }
      message.success(`Uploaded ${file.name}`);
      const refreshDir = targetDir || rootPath;
      await loadDirectory(refreshDir);
      if (activeTab === 'documents') {
        await loadDirectory(currentDocPath);
      }
      setExpandedPaths((prev) => {
        const next = new Set(prev);
        next.add(refreshDir);
        return next;
      });
    } catch (err) {
      message.error('Upload failed: ' + (err.message || String(err)));
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDocUpload = useCallback(async (file) => {
    await uploadFile(file, currentDocPath);
  }, [uploadFile, currentDocPath]);

  const handleRenameFile = useCallback(async (item, newName, targetDir = null) => {
    const dir = targetDir || item.path.substring(0, item.path.lastIndexOf('/'));
    const newPath = `${dir}/${newName}`;
    await sendWSMessage('workspace_rename', { old_path: item.path, new_path: newPath });
    // 不在这里显示消息，让调用方处理
  }, [sendWSMessage]);

  const handleDeleteFile = useCallback(async (item) => {
    const confirmed = window.confirm(`Delete "${item.name}"? This cannot be undone.`);
    if (!confirmed) return;
    try {
      await sendWSMessage('knowledge_delete', { path: item.path });
      message.success(`Deleted: ${item.name}`);
      if (selectedDocItem?.path === item.path) {
        setSelectedDocItem(null);
      }
      await loadDirectory(currentDocPath);
    } catch (err) {
      message.error('Failed to delete: ' + (err.message || String(err)));
    }
  }, [sendWSMessage, loadDirectory, currentDocPath, selectedDocItem]);

  const handlePreview = async ({ prompt, template }) => {
    const source = effectiveSelectedPath;
    if (!source) return '';
    try {
      const response = await sendWSMessage('knowledge_distill_preview', {
        source_path: source,
        prompt,
        template,
      });
      return response.data?.markdown || '';
    } catch (err) {
      message.error('Preview failed: ' + (err.message || String(err)));
      throw err;
    }
  };

  const startDistill = async ({ prompt, template, previewMarkdown }) => {
    const source = effectiveSelectedPath;
    if (!source) return;

    // 如果有 previewMarkdown，直接写入文件（复用预览结果）
    if (previewMarkdown) {
      try {
        const sourceName = source.split('/').pop()?.replace(/\.[^.]+$/, '') || 'extracted';
        const outputPath = `knowledge/notes/${sourceName}_extracted.md`;
        // 添加 frontmatter（如果没有的话）
        let contentToSave = previewMarkdown;
        if (!previewMarkdown.startsWith('---')) {
          const frontmatter = `---
source: ${source}
extracted_at: ${new Date().toISOString()}
extraction_prompt: |
  ${prompt}
---

`;
          contentToSave = frontmatter + previewMarkdown;
        }
        // 确保目录存在
        await sendWSMessage('workspace_mkdir', { path: 'knowledge/notes' }).catch(() => {});
        // 写入文件（后端会自动更新索引）
        await sendWSMessage('knowledge_write', { path: outputPath, content: contentToSave });
        message.success('Distillation saved successfully!');
        setActiveTab('notes');
        readFile(outputPath);
        loadDistillTasks();
      } catch (err) {
        message.error('Failed to save distillation: ' + (err.message || String(err)));
      }
      setDistillDialogVisible(false);
      return;
    }

    // 没有 previewMarkdown，回退到原来的队列模式
    try {
      await sendWSMessage('knowledge_distill', {
        source_path: source,
        prompt,
        template,
      });
      setDistillProgress({
        stage: 'queued',
        message: 'Queued, waiting to start...',
        progress: 0,
      });
    } catch (err) {
      message.error('Failed to queue distillation: ' + (err.message || String(err)));
    }
    setDistillDialogVisible(false);
  };

  const createNewNote = async () => {
    const title = newNoteTitle.trim();
    if (!title) {
      message.error('Title is required');
      return;
    }
    const safeName = title.replace(/[^a-zA-Z0-9一-龥_\- ]/g, '').replace(/\s+/g, '_') || 'note';
    const path = `knowledge/notes/${safeName}.md`;
    const noteContent = `# ${title}\n\n`;
    try {
      await sendWSMessage('knowledge_write', { path, content: noteContent });
      message.success('Note created');
      setIsNewNoteModalOpen(false);
      setNewNoteTitle('');
      await loadDirectory(rootPath);
      setExpandedPaths((prev) => {
        const next = new Set(prev);
        next.add(rootPath);
        return next;
      });
      readFile(path);
    } catch (err) {
      message.error('Failed to create note: ' + (err.message || String(err)));
    }
  };

  const ALLOWED_DISTILL_EXTENSIONS = ['ppt', 'pptx', 'pdf', 'html', 'htm', 'doc', 'docx', 'md', 'txt'];

  const canDistill = (() => {
    const path = activeTab === 'documents' ? selectedDocItem?.path : selectedPath;
    if (!path) return false;
    if (path.endsWith('/')) return false;
    const ext = path.split('.').pop()?.toLowerCase() || '';
    return ALLOWED_DISTILL_EXTENSIONS.includes(ext);
  })();

  const effectiveSelectedPath = activeTab === 'documents' ? (selectedDocItem?.path || null) : selectedPath;

  const handleExport = async () => {
    try {
      const response = await sendWSMessage('knowledge_export', {});
      const { filename, data } = response.data || {};
      if (!data) {
        message.error('Export returned empty data');
        return;
      }
      const byteCharacters = atob(data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'application/zip' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'knowledge_export.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success('Exported successfully');
    } catch (err) {
      message.error('Export failed: ' + (err.message || String(err)));
    }
  };

  const handleImport = async (file) => {
    if (!file) return;
    if (!file.name.endsWith('.zip')) {
      message.error('Please select a .zip file');
      return;
    }
    const targetPath = `knowledge/.import_${Date.now()}.zip`;
    try {
      setIsUploading(true);
      setUploadProgress(0);
      const arrayBuffer = await file.arrayBuffer();
      const bytes = new Uint8Array(arrayBuffer);
      const hex = Array.from(bytes)
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('');
      await sendWSMessage(
        'workspace_write',
        { path: targetPath, content: hex, encoding: 'hex' },
        60000
      );
      await sendWSMessage('knowledge_import', { zip_path: targetPath });
      message.success('Imported successfully');
      await loadDirectory(rootPath);
      setExpandedPaths((prev) => {
        const next = new Set(prev);
        next.add(rootPath);
        return next;
      });
    } catch (err) {
      message.error('Import failed: ' + (err.message || String(err)));
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface)',
        color: 'var(--text)',
        overflow: 'hidden',
        border: '1px solid var(--board)',
        borderRadius: 'var(--r-lg)',
        position: 'relative',
      }}
    >
      <div
        className="window-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '10px 16px',
          borderBottom: '1px solid var(--board)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <WindowDots />
          <span style={{ fontSize: 12, fontWeight: 600 }}>KNOWLEDGE BASE</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {TABS.map((tab) => {
            const IconComponent = tab.icon;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                title={tab.label}
                style={{
                  padding: '6px 10px',
                  borderRadius: 4,
                  border: 'none',
                  background: activeTab === tab.key ? 'var(--accent-soft)' : 'transparent',
                  color: activeTab === tab.key ? 'var(--accent)' : 'var(--text-2)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <IconComponent size={16} />
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
        {activeTab === 'documents' ? (
          docPreviewFile ? (
            <>
              <div
                style={{
                  width: 280,
                  flexShrink: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  background: 'var(--surface-2)',
                  borderRight: '1px solid var(--border)',
                }}
              >
              <DocumentGridView
                  items={treeItems[currentDocPath] || []}
                  currentPath={currentDocPath}
                  rootPath="knowledge/raw"
                  selectedItem={selectedDocItem}
                  loadDirectory={loadDirectory}
                  onSelect={handleDocSelect}
                  onNavigate={handleDocNavigate}
                  onFileOpen={handleDocFileOpen}
                  onCreateFolder={handleCreateFolder}
                  onUploadFile={handleDocUpload}
                  onRenameFile={handleRenameFile}
                  onDeleteFile={handleDeleteFile}
                  treeItems={treeItems}
                />
              </div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg)' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 16px',
                    borderBottom: '1px solid var(--border)',
                    background: 'var(--surface-2)',
                    gap: 12,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, overflow: 'hidden' }}>
                    <span
                      style={{
                        fontSize: 12,
                        color: 'var(--text-2)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {selectedPath || ''}
                    </span>
                    {noteTags.length > 0 && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        {noteTags.map((t) => (
                          <button
                            key={t}
                            onClick={() => {
                              setGraphTagFilter(t);
                              setActiveTab('graph');
                            }}
                            style={{
                              padding: '2px 8px',
                              borderRadius: 4,
                              border: '1px solid var(--accent)',
                              background: 'var(--accent-soft)',
                              color: 'var(--accent)',
                              fontSize: 11,
                              cursor: 'pointer',
                            }}
                          >
                            #{t}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <button
                      onClick={() => {
                        setDocPreviewFile(null);
                        setSelectedPath(null);
                        setContent('');
                        setNoteTags([]);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                        padding: '4px 10px',
                        borderRadius: 4,
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--text-2)',
                        cursor: 'pointer',
                        fontSize: 12,
                      }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>

                <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
                  {fileEncoding === 'hex' ? (
                    <KnowledgeBinaryPreview
                      fileName={selectedPath?.split('/').pop()}
                      content={content}
                      encoding={fileEncoding}
                    />
                  ) : (
                    <NoteEditor
                      fileName={selectedPath?.split('/').pop()}
                      content={content}
                      onSave={writeFile}
                      sendWSMessage={sendWSMessage}
                      onViewInGraph={() => setActiveTab('graph')}
                    />
                  )}
                </div>
              </div>
            </>
          ) : (
            <div style={{ flex: 1, display: 'flex', minWidth: 0, overflow: 'hidden' }}>
              <DocumentGridView
                items={treeItems[currentDocPath] || []}
                currentPath={currentDocPath}
                rootPath="knowledge/raw"
                selectedItem={selectedDocItem}
                loadDirectory={loadDirectory}
                onSelect={handleDocSelect}
                onNavigate={handleDocNavigate}
                onFileOpen={handleDocFileOpen}
                onCreateFolder={handleCreateFolder}
                onUploadFile={handleDocUpload}
                onRenameFile={handleRenameFile}
                onDeleteFile={handleDeleteFile}
                treeItems={treeItems}
              />
            </div>
          )
        ) : (
        <>
        <div
          style={{
            width: 220,
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--surface-2)',
            borderRight: '1px solid var(--border)',
          }}
        >
          <UploadDropzone
            activeTab={activeTab}
            isUploading={isUploading}
            uploadProgress={uploadProgress}
            onFileSelect={uploadFile}
            onNewNoteClick={() => setIsNewNoteModalOpen(true)}
            onExport={handleExport}
            onImport={handleImport}
          />
          <KnowledgeTree
            rootPath={rootPath}
            treeItems={treeItems}
            selectedPath={selectedPath}
            expandedPaths={expandedPaths}
            onSelect={handleSelect}
            onToggle={handleToggle}
          />
          <div style={{ padding: 12, borderTop: '1px solid var(--border)' }}>
            <button
              disabled={!canDistill}
              onClick={() => canDistill && setDistillDialogVisible(true)}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 6,
                border: 'none',
                background: 'var(--accent)',
                color: 'var(--text-invert)',
                fontSize: 12,
                fontWeight: 600,
                cursor: canDistill ? 'pointer' : 'not-allowed',
                opacity: canDistill ? 1 : 0.5,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
              }}
            >
              <Sparkles size={14} />
              <span>Distill with AI</span>
            </button>
            {distillProgress && (
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-2)' }}>
                {distillProgress.message} ({Math.round(distillProgress.progress * 100)}%)
              </div>
            )}
          </div>
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg)' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 16px',
              borderBottom: '1px solid var(--border)',
              background: 'var(--surface-2)',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, overflow: 'hidden' }}>
              <span
                style={{
                  fontSize: 12,
                  color: 'var(--text-2)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {selectedPath || rootPath}
              </span>
              {noteTags.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  {noteTags.map((t) => (
                    <button
                      key={t}
                      onClick={() => {
                        setGraphTagFilter(t);
                        setActiveTab('graph');
                      }}
                      style={{
                        padding: '2px 8px',
                        borderRadius: 4,
                        border: '1px solid var(--accent)',
                        background: 'var(--accent-soft)',
                        color: 'var(--accent)',
                        fontSize: 11,
                        cursor: 'pointer',
                      }}
                    >
                      #{t}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {selectedPath && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  onClick={() => {
                    setSelectedPath(null);
                    setContent('');
                    setNoteTags([]);
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: '4px 10px',
                    borderRadius: 4,
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--text-2)',
                    cursor: 'pointer',
                    fontSize: 12,
                  }}
                >
                  <X size={14} />
                </button>
              </div>
            )}
          </div>

          <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
            {activeTab === 'distill-tasks' ? (
              <DistillTaskList
                tasks={distillTasks}
                expandedTaskId={expandedDistillTask}
                taskDetailResult={taskDetailResult}
                onExpandTask={handleExpandDistillTask}
                sendWSMessage={sendWSMessage}
              />
            ) : activeTab === 'graph' ? (
              <KnowledgeGraphTab
                sendWSMessage={sendWSMessage}
                centerPath={selectedPath}
                filterTag={graphTagFilter}
                onNodeNavigate={(path) => {
                  setSelectedPath(path);
                  setActiveTab('notes');
                  readFile(path);
                }}
              />
            ) : selectedPath ? (
              fileEncoding === 'hex' ? (
                <KnowledgeBinaryPreview
                  fileName={selectedPath.split('/').pop()}
                  content={content}
                  encoding={fileEncoding}
                />
              ) : (
                <NoteEditor
                  fileName={selectedPath.split('/').pop()}
                  content={content}
                  onSave={writeFile}
                  sendWSMessage={sendWSMessage}
                  onViewInGraph={() => setActiveTab('graph')}
                />
              )
            ) : (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-2)',
                  fontSize: 14,
                  flexDirection: 'column',
                  gap: 12,
                }}
              >
                <File size={48} style={{ opacity: 0.3 }} />
                <span>Select a file from the sidebar to preview or edit</span>
              </div>
            )}
          </div>
        </div>
        </>
        )}

        {activeTab === 'documents' && !docPreviewFile && (
          <div
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              padding: '12px 16px',
              borderTop: '1px solid var(--border)',
              background: 'var(--surface-2)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <UploadDropzone
              activeTab={activeTab}
              isUploading={isUploading}
              uploadProgress={uploadProgress}
              onFileSelect={handleDocUpload}
              compact
            />
            <button
              disabled={!canDistill}
              onClick={() => canDistill && setDistillDialogVisible(true)}
              style={{
                padding: '8px 16px',
                borderRadius: 6,
                border: 'none',
                background: canDistill ? 'var(--accent)' : 'var(--surface)',
                color: canDistill ? 'var(--text-invert)' : 'var(--text-3)',
                fontSize: 12,
                fontWeight: 600,
                cursor: canDistill ? 'pointer' : 'not-allowed',
                opacity: canDistill ? 1 : 0.5,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Sparkles size={14} />
              <span>Distill</span>
            </button>
            {distillProgress && (
              <span style={{ fontSize: 11, color: 'var(--text-2)', flex: 1 }}>
                {distillProgress.message} ({Math.round(distillProgress.progress * 100)}%)
              </span>
            )}
          </div>
        )}
      </div>

      <NewNoteModal
        visible={isNewNoteModalOpen}
        title={newNoteTitle}
        onTitleChange={setNewNoteTitle}
        onCreate={createNewNote}
        onCancel={() => {
          setIsNewNoteModalOpen(false);
          setNewNoteTitle('');
        }}
      />

      <DistillDialog
        visible={distillDialogVisible}
        sourceFile={effectiveSelectedPath || ''}
        onCancel={() => setDistillDialogVisible(false)}
        onConfirm={startDistill}
        onPreview={handlePreview}
      />
    </div>
  );
}
