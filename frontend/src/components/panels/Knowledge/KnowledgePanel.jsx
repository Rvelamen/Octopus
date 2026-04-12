import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Sparkles, X, FileText, StickyNote, GitGraph } from 'lucide-react';
import { message, Modal } from 'antd';
import WindowDots from '../../WindowDots';
import TaskIndicator from '../../TaskIndicator';
import { useDistillTasks } from '../../../contexts/DistillTaskContext';
import KnowledgeGraphTab from './KnowledgeGraphTab';
import DistillDialog from './DistillDialog';
import SimpleFileTree from './SimpleFileTree';
import SimpleEditor from './SimpleEditor';
import UploadDropzone from './UploadDropzone';
import NewNoteModal from './NewNoteModal';
import DocumentGridView from './DocumentGridView';
import TaskDetailModal from '../../TaskIndicator/TaskDetailModal';

const TABS = [
  { key: 'documents', label: 'DOCUMENTS', icon: FileText },
  { key: 'notes', label: 'NOTES', icon: StickyNote },
  { key: 'graph', label: 'GRAPH', icon: GitGraph },
];

export default function KnowledgePanel({ sendWSMessage }) {
  const { registerSyncTasks, syncTasksFromBackend } = useDistillTasks();
  const [activeTab, setActiveTab] = useState('documents');
  const [treeItems, setTreeItems] = useState({});
  const [expandedPaths, setExpandedPaths] = useState(new Set());
  const [distillDialogVisible, setDistillDialogVisible] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isNewNoteModalOpen, setIsNewNoteModalOpen] = useState(false);
  const [newNoteTitle, setNewNoteTitle] = useState('');
  const [graphTagFilter, setGraphTagFilter] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);
  const [taskDetailModalVisible, setTaskDetailModalVisible] = useState(false);
  const [currentDocPath, setCurrentDocPath] = useState('knowledge/raw');
  const [selectedDocItem, setSelectedDocItem] = useState(null);
  const [docPreviewFile, setDocPreviewFile] = useState(null);

  // 当前打开的文件（单文件模式）
  const [currentFile, setCurrentFile] = useState(null);

  // Sidebar 宽度状态
  const [sidebarWidth, setSidebarWidth] = useState(240);
  const isResizingRef = useRef(false);
  const sidebarRef = useRef(null);

  const rootPath = activeTab === 'documents' ? 'knowledge/raw' : 'knowledge/notes';

  // Sidebar 拖拽调整宽度
  const startXRef = useRef(0);
  const startWidthRef = useRef(240);

  const handleResizeStart = useCallback((e) => {
    e.preventDefault();
    isResizingRef.current = true;
    startXRef.current = e.clientX;
    startWidthRef.current = sidebarWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [sidebarWidth]);

  const handleResizeMove = useCallback((e) => {
    if (!isResizingRef.current) return;
    const delta = e.clientX - startXRef.current;
    const newWidth = Math.max(150, Math.min(400, startWidthRef.current + delta));
    setSidebarWidth(newWidth);
  }, []);

  const handleResizeEnd = useCallback(() => {
    isResizingRef.current = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

  useEffect(() => {
    window.addEventListener('mousemove', handleResizeMove);
    window.addEventListener('mouseup', handleResizeEnd);
    return () => {
      window.removeEventListener('mousemove', handleResizeMove);
      window.removeEventListener('mouseup', handleResizeEnd);
    };
  }, [handleResizeMove, handleResizeEnd]);

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
        const content = response.data?.content || '';
        return { content, encoding, path };
      } catch (err) {
        message.error('Failed to read file: ' + err.message);
        return null;
      }
    },
    [sendWSMessage]
  );

  const writeFile = useCallback(
    async (path, content) => {
      try {
        await sendWSMessage('knowledge_write', { path, content });
        message.success('Saved successfully');
      } catch (err) {
        message.error('Failed to save file: ' + err.message);
        throw err;
      }
    },
    [sendWSMessage]
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

  // 打开文件
  const handleOpenFile = useCallback(
    async (item) => {
      if (item.is_directory) {
        handleToggle(item.path);
        return;
      }

      const fileData = await readFile(item.path);
      if (fileData) {
        setCurrentFile({
          path: item.path,
          name: item.name,
          content: fileData.content,
          encoding: fileData.encoding,
        });
      }
    },
    [readFile, handleToggle]
  );

  // 关闭文件
  const handleCloseFile = useCallback(() => {
    setCurrentFile(null);
  }, []);

  // 创建文件
  const handleCreateFile = useCallback(
    async (dirPath) => {
      Modal.confirm({
        title: 'New File',
        content: (
          <input
            id="new-file-input"
            placeholder="File name"
            defaultValue="untitled.md"
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
          const input = document.getElementById('new-file-input');
          const name = input?.value?.trim();
          if (!name) return Promise.reject();
          const safeName = name.replace(/[^a-zA-Z0-9一-龥_\- .]/g, '');
          if (!safeName) return Promise.reject();
          const newPath = `${dirPath}/${safeName}`;
          try {
            await sendWSMessage('knowledge_write', { path: newPath, content: '' });
            message.success(`Created file: ${safeName}`);
            await loadDirectory(dirPath);
            handleOpenFile({ path: newPath, name: safeName, is_directory: false });
          } catch (err) {
            message.error('Failed to create file: ' + (err.message || String(err)));
            return Promise.reject();
          }
        },
      });
    },
    [loadDirectory, sendWSMessage, handleOpenFile]
  );

  // 创建文件夹
  const handleCreateFolder = useCallback(
    async (dirPath) => {
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
          const name = input?.value?.trim();
          if (!name) return Promise.reject();
          const safeName = name.replace(/[^a-zA-Z0-9一-龥_\- .]/g, '');
          if (!safeName) return Promise.reject();
          const newPath = `${dirPath}/${safeName}`;
          try {
            await sendWSMessage('workspace_mkdir', { path: newPath });
            message.success(`Created folder: ${safeName}`);
            await loadDirectory(dirPath);
          } catch (err) {
            message.error('Failed to create folder: ' + (err.message || String(err)));
            return Promise.reject();
          }
        },
      });
    },
    [loadDirectory, sendWSMessage]
  );

  // 重命名
  const handleRename = useCallback(
    async (item) => {
      Modal.confirm({
        title: 'Rename',
        content: (
          <input
            id="rename-input"
            placeholder="New name"
            defaultValue={item.name}
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
        okText: 'Rename',
        cancelText: 'Cancel',
        onOk: async () => {
          const input = document.getElementById('rename-input');
          const newName = input?.value?.trim();
          if (!newName || newName === item.name) return Promise.reject();
          const safeName = newName.replace(/[^a-zA-Z0-9一-龥_\- .]/g, '');
          if (!safeName) return Promise.reject();

          const dir = item.path.substring(0, item.path.lastIndexOf('/'));
          const newPath = `${dir}/${safeName}`;
          try {
            await sendWSMessage('workspace_rename', { old_path: item.path, new_path: newPath });
            message.success(`Renamed to: ${safeName}`);
            await loadDirectory(dir);

            // 更新当前打开的文件
            if (currentFile?.path === item.path) {
              setCurrentFile((prev) =>
                prev ? { ...prev, path: newPath, name: safeName } : null
              );
            }
          } catch (err) {
            message.error('Failed to rename: ' + (err.message || String(err)));
            return Promise.reject();
          }
        },
      });
    },
    [loadDirectory, sendWSMessage, currentFile]
  );

  // 删除
  const handleDelete = useCallback(
    async (item) => {
      const confirmed = window.confirm(`Delete "${item.name}"? This cannot be undone.`);
      if (!confirmed) return;
      try {
        await sendWSMessage('knowledge_delete', { path: item.path });
        message.success(`Deleted: ${item.name}`);

        // 关闭已打开的文件
        if (currentFile?.path === item.path) {
          setCurrentFile(null);
        }

        const dir = item.path.substring(0, item.path.lastIndexOf('/'));
        await loadDirectory(dir);
      } catch (err) {
        message.error('Failed to delete: ' + (err.message || String(err)));
      }
    },
    [sendWSMessage, loadDirectory, currentFile]
  );

  // 移动文件/文件夹
  const handleMove = useCallback(
    async (sourcePath, targetDirPath) => {
      try {
        const fileName = sourcePath.split('/').pop();
        const targetPath = `${targetDirPath}/${fileName}`;
        
        // 检查目标是否已存在
        const targetDirItems = treeItems[targetDirPath] || [];
        const exists = targetDirItems.some(item => item.name === fileName);
        if (exists) {
          message.error(`A file or folder named "${fileName}" already exists in the target directory.`);
          return;
        }

        await sendWSMessage('workspace_rename', { 
          old_path: sourcePath, 
          new_path: targetPath 
        });
        message.success(`Moved to: ${targetDirPath}`);
        
        // 刷新源目录和目标目录
        const sourceDir = sourcePath.substring(0, sourcePath.lastIndexOf('/'));
        await loadDirectory(sourceDir);
        await loadDirectory(targetDirPath);
        
        // 如果移动的是当前打开的文件，更新路径
        if (currentFile?.path === sourcePath) {
          setCurrentFile(prev => prev ? { ...prev, path: targetPath } : null);
        }
      } catch (err) {
        message.error('Failed to move: ' + (err.message || String(err)));
      }
    },
    [sendWSMessage, loadDirectory, currentFile, treeItems]
  );

  const handleDocNavigate = useCallback((path) => {
    setCurrentDocPath(path);
    setSelectedDocItem(null);
    setDocPreviewFile(null);
  }, []);

  const handleDocSelect = useCallback((item) => {
    setSelectedDocItem(item);
  }, []);

  const handleDocFileOpen = useCallback(
    async (item) => {
      if (item.is_directory) return;
      setDocPreviewFile(item);
      await handleOpenFile(item);
    },
    [handleOpenFile]
  );

  useEffect(() => {
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
      const tasks = resp.data?.tasks || [];
      // 同步到 DistillTaskContext
      syncTasksFromBackend(tasks);
    } catch {
      // ignore
    }
  }, [sendWSMessage, syncTasksFromBackend]);

  const handleViewTaskDetail = useCallback(
    (task) => {
      setSelectedTask(task);
      setTaskDetailModalVisible(true);
    },
    []
  );

  useEffect(() => {
    loadDistillTasks();
    const timer = setInterval(loadDistillTasks, 5000);
    return () => clearInterval(timer);
  }, [loadDistillTasks]);

  // 注册同步函数到 DistillTaskContext
  useEffect(() => {
    registerSyncTasks(loadDistillTasks);
  }, [registerSyncTasks, loadDistillTasks]);

  useEffect(() => {
    const handler = (e) => {
      const { stage, message: msg, output_path } = e.detail;
      if (stage === 'completed' && output_path) {
        message.success('Distillation complete!');
        setActiveTab('notes');
        handleOpenFile({ path: output_path, name: output_path.split('/').pop(), is_directory: false });
        loadDistillTasks();
      } else if (stage === 'failed') {
        message.error('Distillation failed: ' + msg);
        loadDistillTasks();
      }
    };
    window.addEventListener('knowledge-distill-progress', handler);
    return () => window.removeEventListener('knowledge-distill-progress', handler);
  }, [handleOpenFile, loadDistillTasks]);

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

  const handleDocUpload = useCallback(
    async (file) => {
      await uploadFile(file, currentDocPath);
    },
    [uploadFile, currentDocPath]
  );

  // 处理右键菜单上传文件 - 弹出文件选择框
  const handleUploadFileFromMenu = useCallback(
    (targetDir) => {
      // 创建隐藏的文件输入元素
      const input = document.createElement('input');
      input.type = 'file';
      input.style.display = 'none';
      input.onchange = async (e) => {
        const file = e.target.files?.[0];
        if (file) {
          await uploadFile(file, targetDir);
        }
        document.body.removeChild(input);
      };
      document.body.appendChild(input);
      input.click();
    },
    [uploadFile]
  );

  const handleStartDistill = async ({ prompt, template, taskId }) => {
    const source = effectiveSelectedPath;
    if (!source) return '';
    try {
      const response = await sendWSMessage('knowledge_distill', {
        source_path: source,
        prompt,
        template,
        task_id: taskId,
      });
      return response.data || {};
    } catch (err) {
      message.error('Failed to start distillation: ' + (err.message || String(err)));
      throw err;
    }
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
      handleOpenFile({ path, name: `${safeName}.md`, is_directory: false });
    } catch (err) {
      message.error('Failed to create note: ' + (err.message || String(err)));
    }
  };

  const ALLOWED_DISTILL_EXTENSIONS = ['ppt', 'pptx', 'pdf', 'html', 'htm', 'doc', 'docx', 'md', 'txt'];

  const canDistill = (() => {
    const path = activeTab === 'documents' ? selectedDocItem?.path : currentFile?.path;
    if (!path) return false;
    if (path.endsWith('/')) return false;
    const ext = path.split('.').pop()?.toLowerCase() || '';
    return ALLOWED_DISTILL_EXTENSIONS.includes(ext);
  })();

  const effectiveSelectedPath = activeTab === 'documents' ? (selectedDocItem?.path || null) : currentFile?.path;

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
      {/* Header */}
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
        <div style={{ flex: 1 }} />
        <TaskIndicator onViewTaskDetail={handleViewTaskDetail} />
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
        {activeTab === 'documents' ? (
          docPreviewFile ? (
            <>
              {/* Documents Sidebar - narrower */}
              <div
                style={{
                  width: 200,
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
                  onUploadFile={handleUploadFileFromMenu}
                  onRenameFile={handleRename}
                  onDeleteFile={handleDelete}
                  treeItems={treeItems}
                />
              </div>
              {/* Editor Area */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg)' }}>
                <SimpleEditor
                  file={currentFile}
                  onSave={writeFile}
                  sendWSMessage={sendWSMessage}
                  onViewInGraph={() => setActiveTab('graph')}
                />
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
                onUploadFile={handleUploadFileFromMenu}
                onRenameFile={handleRename}
                onDeleteFile={handleDelete}
                treeItems={treeItems}
              />
            </div>
          )
        ) : activeTab === 'graph' ? (
          /* Graph Tab - Full screen, no sidebar, global graph */
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg)' }}>
            <KnowledgeGraphTab
              sendWSMessage={sendWSMessage}
              centerPath={null}
              filterTag={graphTagFilter}
              onNodeNavigate={(path) => {
                handleOpenFile({ path, name: path.split('/').pop(), is_directory: false });
              }}
            />
          </div>
        ) : (
          <>
            {/* Sidebar - resizable */}
            <div
              ref={sidebarRef}
              style={{
                width: sidebarWidth,
                flexShrink: 0,
                display: 'flex',
                flexDirection: 'column',
                background: 'var(--surface-2)',
                borderRight: '1px solid var(--border)',
                position: 'relative',
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
              <div style={{ flex: 1, overflow: 'auto' }}>
                <SimpleFileTree
                  rootPath={rootPath}
                  treeItems={treeItems}
                  selectedPath={currentFile?.path}
                  expandedPaths={expandedPaths}
                  onSelect={handleOpenFile}
                  onToggle={handleToggle}
                  onCreateFile={handleCreateFile}
                  onCreateFolder={handleCreateFolder}
                  onRename={handleRename}
                  onDelete={handleDelete}
                  onRefresh={loadDirectory}
                  onMove={handleMove}
                />
              </div>
              {activeTab === 'documents' && (
                <div style={{ padding: 8, borderTop: '1px solid var(--border)' }}>
                  <button
                    disabled={!canDistill}
                    onClick={() => canDistill && setDistillDialogVisible(true)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: 4,
                      border: 'none',
                      background: canDistill ? 'var(--accent)' : 'var(--surface)',
                      color: canDistill ? 'var(--text-invert)' : 'var(--text-3)',
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: canDistill ? 'pointer' : 'not-allowed',
                      opacity: canDistill ? 1 : 0.5,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 4,
                    }}
                  >
                    <Sparkles size={12} />
                    <span>Distill</span>
                  </button>
                </div>
              )}
              {/* Resize handle */}
              <div
                onMouseDown={handleResizeStart}
                className="sidebar-resize-handle"
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 0,
                  bottom: 0,
                  width: 4,
                  cursor: 'col-resize',
                  background: 'transparent',
                  transition: 'background 0.15s',
                  zIndex: 10,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--accent)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              />
            </div>

            {/* Main Editor Area */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg)' }}>
              <SimpleEditor
                file={currentFile}
                onSave={writeFile}
                sendWSMessage={sendWSMessage}
                onViewInGraph={() => setActiveTab('graph')}
              />
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
              padding: '8px 12px',
              borderTop: '1px solid var(--border)',
              background: 'var(--surface-2)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
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
                padding: '8px 14px',
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
                whiteSpace: 'nowrap',
              }}
            >
              <Sparkles size={15} />
              <span>Distill</span>
            </button>
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
        onStartDistill={handleStartDistill}
      />

      <TaskDetailModal
        task={selectedTask}
        visible={taskDetailModalVisible}
        onClose={() => setTaskDetailModalVisible(false)}
        sendWSMessage={sendWSMessage}
      />
    </div>
  );
}
