import React, { useState, useEffect, useLayoutEffect, useCallback, useRef, useMemo } from 'react';
import {
  Folder, File, ChevronRight, ChevronDown, Home,
  RefreshCw, Plus, Trash2, Edit3, Save, X, FolderPlus,
  FilePlus, ArrowLeft, Search, FileText, Image, Code,
  MoreVertical, Download, Upload, Eye
} from 'lucide-react';
import { Modal, Input, Button, Dropdown, Menu, message } from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Editor from '@monaco-editor/react';
import WindowDots from '../WindowDots';
import {
  ImageViewer,
  PdfViewer,
  XlsxViewer,
  DocxViewer,
  PptxViewer,
  BinaryViewer,
  HtmlViewer,
  getLanguage,
} from './FileViewers';

/**
 * File Icon Component - Returns appropriate icon based on file type
 */
const FileIcon = ({ name, type, size = 16 }) => {
  if (type === 'directory') {
    return <Folder size={size} className="file-icon folder" />;
  }

  const ext = name.split('.').pop()?.toLowerCase();

  // Image files
  if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(ext)) {
    return <Image size={size} className="file-icon image" />;
  }

  // Code files
  if (['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'cpp', 'c', 'h', 'go', 'rs', 'php', 'rb'].includes(ext)) {
    return <Code size={size} className="file-icon code" />;
  }

  // Text files
  if (['txt', 'md', 'json', 'xml', 'yaml', 'yml', 'csv', 'log'].includes(ext)) {
    return <FileText size={size} className="file-icon text" />;
  }

  return <File size={size} className="file-icon" />;
};

/**
 * Format file size
 */
/**
 * Format date
 */
const formatDate = (timestamp) => {
  if (!timestamp) return '-';
  return new Date(timestamp * 1000).toLocaleString();
};

/**
 * Tree Node Component
 */
const TreeNode = ({
  item,
  level = 0,
  selectedPath,
  expandedPaths,
  onSelect,
  onToggle,
  onContextMenu,
  treeItems
}) => {
  const isExpanded = expandedPaths.has(item.path);
  const isSelected = selectedPath === item.path;
  // 获取所有子项（文件和目录）
  const allChildren = treeItems?.[item.path] || [];
  const hasChildren = item.type === 'directory' && allChildren.length > 0;

  // 如果是文件，直接渲染文件节点
  if (item.type === 'file') {
    return (
      <div className="tree-node-container">
        <div
          className={`tree-node ${isSelected ? 'selected' : ''}`}
          style={{ paddingLeft: `${level * 16 + 8}px` }}
          onClick={() => onSelect(item)}
          onContextMenu={(e) => onContextMenu(e, item)}
        >
          <span className="tree-toggle" />
          <FileIcon name={item.name} type={item.type} size={16} />
          <span className="tree-node-name" title={item.name}>{item.name}</span>
        </div>
      </div>
    );
  }

  // 目录节点
  return (
    <div className="tree-node-container">
      <div
        className={`tree-node ${isSelected ? 'selected' : ''}`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={() => onSelect(item)}
        onContextMenu={(e) => onContextMenu(e, item)}
      >
        <span
          className="tree-toggle"
          onClick={(e) => {
            e.stopPropagation();
            onToggle(item.path);
          }}
        >
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <FileIcon name={item.name} type={item.type} size={16} />
        <span className="tree-node-name" title={item.name}>{item.name}</span>
      </div>
      {isExpanded && hasChildren && (
        <div className="tree-children">
          {allChildren.map((child) => (
            <TreeNode
              key={child.path}
              item={child}
              level={level + 1}
              selectedPath={selectedPath}
              expandedPaths={expandedPaths}
              onSelect={onSelect}
              onToggle={onToggle}
              onContextMenu={onContextMenu}
              treeItems={treeItems}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * Convert hex string to base64
 */
/**
 * Image Viewer Component
 */
/**
 * XLSX Viewer Component
 */
/** MIME type for workspace image preview (Blob) from file path extension */
const mimeFromImagePath = (p) => {
  const ext = (p.split('.').pop() || '').toLowerCase().split('?')[0];
  const map = {
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    gif: 'image/gif',
    webp: 'image/webp',
    bmp: 'image/bmp',
    svg: 'image/svg+xml',
    ico: 'image/x-icon',
  };
  return map[ext] || 'application/octet-stream';
};

/** workspace_read returns binary as hex — must parse pairs, not atob (base64) */
const workspaceHexToBlob = (hexContent, mimeType) => {
  const hexString = (hexContent || '').replace(/\s/g, '');
  if (!hexString || hexString.length % 2 !== 0) return null;
  const pairs = hexString.match(/.{1,2}/g);
  if (!pairs) return null;
  const byteArray = new Uint8Array(pairs.map((b) => parseInt(b, 16)));
  return new Blob([byteArray], { type: mimeType });
};

/**
 * Markdown Viewer Component
 */
const MarkdownViewer = ({ content, file, sendWSMessage }) => {
  const [loadingImages, setLoadingImages] = useState(new Set());
  // blob URLs stored in a ref so img closures always read the latest values
  const imageUrlsRef = useRef({});
  const inFlightRef = useRef(new Set());
  const cleanupRef = useRef([]);

  const filePath = file?.path || '';
  const fileDir = filePath.includes('/')
    ? filePath.substring(0, filePath.lastIndexOf('/'))
    : '';

  // Clean up all blob URLs and reset state whenever the file changes
  useEffect(() => {
    // Revoke any lingering blob URLs from the previous file
    cleanupRef.current.forEach((url) => URL.revokeObjectURL(url));
    cleanupRef.current = [];
    imageUrlsRef.current = {};
    inFlightRef.current.clear();
    setLoadingImages(new Set());
  }, [file?.path]);

  // Load images: only re-runs when content/file/sendWSMessage/dir actually change
  useEffect(() => {
    const loadImages = async () => {
      if (!content || !sendWSMessage) return;

      const imgRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
      const pathsToLoad = [];

      let match;
      while ((match = imgRegex.exec(content)) !== null) {
        let imgSrc = (match[2] || '').trim();
        if (imgSrc.startsWith('<') || imgSrc.includes(' ')) continue;
        imgSrc = imgSrc.replace(/^\.\//, '');

        if (imgSrc && !imgSrc.startsWith('http') && !imgSrc.startsWith('data:')) {
          const fullPath = fileDir
            ? `${fileDir}/${imgSrc}`.replace(/\/+/g, '/')
            : imgSrc;

          if (
            !imageUrlsRef.current[fullPath] &&
            !inFlightRef.current.has(fullPath)
          ) {
            pathsToLoad.push(fullPath);
          }
        }
      }

      if (pathsToLoad.length === 0) return;

      pathsToLoad.forEach((p) => inFlightRef.current.add(p));
      setLoadingImages((prev) => new Set([...prev, ...pathsToLoad]));

      for (const imgPath of pathsToLoad) {
        try {
          const response = await sendWSMessage('workspace_read', { path: imgPath });
          const enc = response.data?.encoding;
          const raw = response.data?.content;
          if (raw == null || !enc) continue;

          let blobUrl = null;
          const mime = mimeFromImagePath(imgPath);

          if (enc === 'hex') {
            const blob = workspaceHexToBlob(raw, mime);
            if (blob) blobUrl = URL.createObjectURL(blob);
          } else if (enc === 'base64') {
            blobUrl = `data:${mime};base64,${raw}`;
          } else {
            const te = new TextEncoder().encode(String(raw));
            blobUrl = URL.createObjectURL(new Blob([te], { type: mime }));
          }

          if (blobUrl) {
            imageUrlsRef.current = { ...imageUrlsRef.current, [imgPath]: blobUrl };
            cleanupRef.current.push(blobUrl);
            // Force a re-render so <img> closures pick up the new value
            setLoadingImages((prev) => {
              const next = new Set(prev);
              next.delete(imgPath);
              return next;
            });
          }
        } catch (err) {
          console.error('Failed to load image:', imgPath, err);
        } finally {
          inFlightRef.current.delete(imgPath);
          setLoadingImages((prev) => {
            const next = new Set(prev);
            next.delete(imgPath);
            return next;
          });
        }
      }
    };

    loadImages();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content, file?.path, sendWSMessage, fileDir]);

  // On unmount, revoke all blob URLs
  useEffect(() => {
    return () => {
      cleanupRef.current.forEach((url) => URL.revokeObjectURL(url));
      cleanupRef.current = [];
    };
  }, []);

  if (!content) {
    return (
      <div className="markdown-preview empty">
        <p>No content to preview</p>
      </div>
    );
  }

  return (
    <div className="markdown-preview">
      <ReactMarkdown 
        remarkPlugins={[remarkGfm]}
        components={{
          img: ({ src, alt, ...props }) => {
            let normalized = (src || '').trim().replace(/^\.\//, '');
            if (
              normalized &&
              !normalized.startsWith('http') &&
              !normalized.startsWith('data:')
            ) {
              const fullPath = fileDir
                ? `${fileDir}/${normalized}`.replace(/\/+/g, '/')
                : normalized;

              // Read from ref so this closure always gets the latest URL
              const imgSrc = imageUrlsRef.current[fullPath] || src;
              
              return (
                <img 
                  src={imgSrc} 
                  alt={alt} 
                  {...props} 
                  style={{ 
                    maxWidth: '100%', 
                    height: 'auto',
                    opacity: loadingImages.has(fullPath) ? 0.5 : 1,
                    transition: 'opacity 0.3s'
                  }} 
                />
              );
            }
            return <img src={src} alt={alt} {...props} />;
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

/**
 * PPTX: decode entities and escape for safe HTML
 */
/**
 * File Editor Component with Monaco Editor
 */
const FileEditor = ({ file, content, onSave, onClose, isSaving, readOnly = false, sendWSMessage }) => {
  // 确保 content 是字符串
  const safeContent = content ?? '';
  const [editedContent, setEditedContent] = useState(safeContent);
  const [isDirty, setIsDirty] = useState(false);
  const [isPreviewMode, setIsPreviewMode] = useState(false);
  const editorRef = useRef(null);

  // 监听 content 变化，更新 editedContent
  useEffect(() => {
    setEditedContent(safeContent);
    setIsDirty(false);
    setIsPreviewMode(false);
  }, [safeContent, file?.path]);

  const handleSave = () => {
    onSave(file.path, editedContent);
    setIsDirty(false);
  };

  const handleEditorChange = (value) => {
    setEditedContent(value);
    setIsDirty(true);
  };

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;

    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      if (!readOnly && isDirty && !isSaving) {
        handleSave();
      }
    });
  };

  if (!file || !file.name) {
    return null;
  }

  const isBinary = file.encoding === 'hex';
  const fileExt = file.name.split('.').pop()?.toLowerCase() || '';
  const isImage = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(fileExt);
  const isPptx = ['pptx', 'ppt'].includes(fileExt);
  const isDocx = ['docx', 'doc'].includes(fileExt);
  const isHtml = ['html', 'htm'].includes(fileExt);
  const isMarkdown = ['md'].includes(fileExt);
  const language = getLanguage(file.name);

  return (
    <div className="file-editor">
      <div className="file-editor-header">
        <WindowDots />
        <span className="editor-filename">{file.name}</span>
        <div className="editor-actions">
          {(isHtml || isMarkdown) && !isImage && (
            <button
              className={`editor-btn ${isPreviewMode ? 'active' : ''}`}
              onClick={() => setIsPreviewMode((p) => !p)}
              title={isPreviewMode ? '切换到编辑' : '预览'}
            >
              {isPreviewMode ? <Edit3 size={14} /> : <Eye size={14} />}
            </button>
          )}
          {!readOnly && !isBinary && !isImage && (
            <button
              className="editor-btn"
              onClick={handleSave}
              disabled={!isDirty || isSaving}
            >
              {isSaving ? <RefreshCw size={14} className="spin" /> : <Save size={14} />}
              {isDirty && <span className="dirty-indicator">*</span>}
            </button>
          )}
          <button className="editor-btn" onClick={onClose}>
            <X size={14} />
          </button>
        </div>
      </div>
      <div className="file-editor-content">
        {isImage ? (
          <ImageViewer file={file} content={safeContent} fileExt={fileExt} />
        ) : fileExt === 'pdf' ? (
          <PdfViewer file={file} content={safeContent} />
        ) : ['xlsx', 'xls'].includes(fileExt) ? (
          <XlsxViewer file={file} content={safeContent} />
        ) : isPptx ? (
          <PptxViewer file={file} content={safeContent} />
        ) : isDocx ? (
          <DocxViewer file={file} content={safeContent} />
        ) : isBinary ? (
          <BinaryViewer file={file} content={safeContent} />
        ) : (isHtml || isMarkdown) && isPreviewMode ? (
          isMarkdown ? (
            <MarkdownViewer content={editedContent} file={file} sendWSMessage={sendWSMessage} />
          ) : (
            <HtmlViewer content={editedContent} />
          )
        ) : (
          <Editor
            height="100%"
            language={language}
            value={editedContent}
            onChange={readOnly ? undefined : handleEditorChange}
            onMount={handleEditorDidMount}
            options={{
              minimap: { enabled: true },
              fontSize: 14,
              fontFamily: 'var(--font-mono)',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 2,
              insertSpaces: true,
              wordWrap: 'on',
              lineNumbers: 'on',
              renderWhitespace: 'selection',
              folding: true,
              bracketPairColorization: { enabled: true },
              formatOnPaste: !readOnly,
              formatOnType: !readOnly,
              suggestOnTriggerCharacters: !readOnly,
              quickSuggestions: !readOnly,
              snippetSuggestions: 'inline',
              readOnly: readOnly,
            }}
            theme="vs-dark"
          />
        )}
      </div>
    </div>
  );
};

/**
 * Breadcrumb Component
 */
const Breadcrumb = ({ path, onNavigate, rootName = 'workspace' }) => {
  const parts = path === '.' ? [] : path.split('/').filter(Boolean);

  return (
    <div className="breadcrumb">
      <button
        className="breadcrumb-item root"
        onClick={() => onNavigate('.')}
      >
        <Home size={14} />
        {rootName}
      </button>
      {parts.map((part, index) => {
        const currentPath = parts.slice(0, index + 1).join('/');
        return (
          <React.Fragment key={index}>
            <ChevronRight size={14} className="breadcrumb-separator" />
            <button
              className="breadcrumb-item"
              onClick={() => onNavigate(currentPath)}
            >
              {part}
            </button>
          </React.Fragment>
        );
      })}
    </div>
  );
};

/**
 * Workspace Panel Component
 */
const WorkspacePanel = ({ sendWSMessage }) => {
  const [rootPath, setRootPath] = useState('');
  const [currentPath, setCurrentPath] = useState('.');
  const [items, setItems] = useState([]);
  const [treeData, setTreeData] = useState([]);
  const [selectedPath, setSelectedPath] = useState(null);
  const [expandedPaths, setExpandedPaths] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Tree data state - must be defined before functions that use it
  const [treeItems, setTreeItems] = useState({});

  // Ref to track initial load
  const initialLoadDone = useRef(false);

  // File editor state
  const [editingFile, setEditingFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Modal states
  const [isCreateFolderModalOpen, setIsCreateFolderModalOpen] = useState(false);
  const [isCreateFileModalOpen, setIsCreateFileModalOpen] = useState(false);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [contextMenuItem, setContextMenuItem] = useState(null);

  // Get workspace root
  const fetchRoot = useCallback(async () => {
    try {
      const response = await sendWSMessage('workspace_get_root', {});
      if (response.data?.root) {
        setRootPath(response.data.root);
      }
    } catch (err) {
      message.error('Failed to get workspace root: ' + err.message);
    }
  }, [sendWSMessage]);

  // List directory contents
  const listDirectory = useCallback(async (path = '.') => {
    setLoading(true);
    try {
      const response = await sendWSMessage('workspace_list', { path });
      if (response.data?.items) {
        setItems(response.data.items);
        setCurrentPath(response.data.path);
      }
    } catch (err) {
      message.error('Failed to list directory: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage]);

  // Read file
  const readFile = useCallback(async (path) => {
    try {
      const response = await sendWSMessage('workspace_read', { path });
      if (response.data) {
        setEditingFile(response.data);
        setFileContent(response.data.content);
      }
    } catch (err) {
      message.error('Failed to read file: ' + err.message);
    }
  }, [sendWSMessage]);

  // Write file
  const writeFile = useCallback(async (path, content) => {
    setIsSaving(true);
    try {
      await sendWSMessage('workspace_write', { path, content });
      message.success('File saved successfully');
    } catch (err) {
      message.error('Failed to save file: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  }, [sendWSMessage]);

  // Load directory for tree view - defined before handleSelect
  const loadTreeDirectory = useCallback(async (path) => {
    try {
      const response = await sendWSMessage('workspace_list', { path });
      if (response.data?.items) {
        setTreeItems(prev => ({ ...prev, [path]: response.data.items }));
        return response.data.items;
      }
      return [];
    } catch (err) {
      console.error('Failed to load tree directory:', err);
      return [];
    }
  }, [sendWSMessage]);

  // Delete file or directory
  const deleteItem = useCallback(async (path, isDirectory) => {
    Modal.confirm({
      title: `Delete ${isDirectory ? 'Directory' : 'File'}`,
      content: `Are you sure you want to delete "${path}"?`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          await sendWSMessage('workspace_delete', {
            path,
            recursive: isDirectory
          });
          message.success('Deleted successfully');
          // 刷新当前目录列表
          listDirectory(currentPath);
          // 刷新树形视图 - 获取父目录路径
          const parentPath = path.includes('/') ? path.substring(0, path.lastIndexOf('/')) : '.';
          if (treeItems[parentPath]) {
            loadTreeDirectory(parentPath);
          }
          // 如果删除的是当前选中的文件，关闭编辑器
          if (selectedPath === path) {
            setSelectedPath(null);
            setEditingFile(null);
            setFileContent('');
          }
          // 从 treeItems 中移除被删除的项
          setTreeItems(prev => {
            const next = { ...prev };
            delete next[path];
            return next;
          });
        } catch (err) {
          message.error('Failed to delete: ' + err.message);
        }
      }
    });
  }, [sendWSMessage, currentPath, listDirectory, selectedPath, treeItems, loadTreeDirectory]);

  // Create directory
  const createDirectory = useCallback(async () => {
    if (!newName.trim()) return;
    const path = currentPath === '.' ? newName : `${currentPath}/${newName}`;
    try {
      await sendWSMessage('workspace_mkdir', { path });
      message.success('Directory created successfully');
      setIsCreateFolderModalOpen(false);
      setNewName('');
      listDirectory(currentPath);
      // 刷新树形视图
      loadTreeDirectory(currentPath);
    } catch (err) {
      message.error('Failed to create directory: ' + err.message);
    }
  }, [sendWSMessage, currentPath, newName, listDirectory, loadTreeDirectory]);

  // Create file
  const createFile = useCallback(async () => {
    if (!newName.trim()) return;
    const path = currentPath === '.' ? newName : `${currentPath}/${newName}`;
    try {
      await sendWSMessage('workspace_write', { path, content: '' });
      message.success('File created successfully');
      setIsCreateFileModalOpen(false);
      setNewName('');
      listDirectory(currentPath);
      // 刷新树形视图
      loadTreeDirectory(currentPath);
    } catch (err) {
      message.error('Failed to create file: ' + err.message);
    }
  }, [sendWSMessage, currentPath, newName, listDirectory, loadTreeDirectory]);

  // Rename item
  const renameItem = useCallback(async () => {
    if (!newName.trim() || !contextMenuItem) return;
    const oldPath = contextMenuItem.path;
    const parentPath = oldPath.includes('/') ? oldPath.substring(0, oldPath.lastIndexOf('/')) : '.';
    const newPath = parentPath === '.' ? newName : `${parentPath}/${newName}`;

    try {
      await sendWSMessage('workspace_rename', { old_path: oldPath, new_path: newPath });
      message.success('Renamed successfully');
      setIsRenameModalOpen(false);
      setNewName('');
      listDirectory(currentPath);
      // 刷新树形视图 - 刷新父目录
      loadTreeDirectory(parentPath);
      // 如果重命名的是当前选中的文件，更新选中路径
      if (selectedPath === oldPath) {
        setSelectedPath(newPath);
      }
    } catch (err) {
      message.error('Failed to rename: ' + err.message);
    }
  }, [sendWSMessage, contextMenuItem, currentPath, newName, listDirectory, loadTreeDirectory, selectedPath]);

  // Handle tree expand - load children on demand
  const handleTreeExpand = useCallback(async (path) => {
    const isCurrentlyExpanded = expandedPaths.has(path);

    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (isCurrentlyExpanded) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });

    // Load children if expanding and not already loaded
    if (!isCurrentlyExpanded && !treeItems[path]) {
      await loadTreeDirectory(path);
    }
  }, [expandedPaths, treeItems, loadTreeDirectory]);

  // Handle item selection
  const handleSelect = useCallback((item) => {
    setSelectedPath(item.path);
    if (item.type === 'directory') {
      listDirectory(item.path);
      // Also expand in tree view and load children
      setExpandedPaths(prev => {
        if (!prev.has(item.path)) {
          const next = new Set(prev);
          next.add(item.path);
          // Load children if not already loaded
          if (!treeItems[item.path]) {
            loadTreeDirectory(item.path);
          }
          return next;
        }
        return prev;
      });
    } else {
      readFile(item.path);
    }
  }, [listDirectory, readFile, treeItems, loadTreeDirectory]);

  // Handle context menu
  const handleContextMenu = useCallback((e, item) => {
    e.preventDefault();
    setContextMenuItem(item);
    setSelectedPath(item.path);

    const menuItems = [
      {
        key: 'rename',
        label: 'Rename',
        icon: <Edit3 size={14} />,
        onClick: () => {
          setNewName(item.name);
          setIsRenameModalOpen(true);
        }
      },
      {
        key: 'delete',
        label: 'Delete',
        icon: <Trash2 size={14} />,
        danger: true,
        onClick: () => deleteItem(item.path, item.type === 'directory')
      }
    ];

    // Show context menu using antd Dropdown
    const menu = <Menu items={menuItems} />;
    // Use a simple approach - show modal options
    Modal.confirm({
      title: item.name,
      content: (
        <div className="context-menu-options">
          <Button
            icon={<Edit3 size={14} />}
            onClick={() => {
              Modal.destroyAll();
              setNewName(item.name);
              setIsRenameModalOpen(true);
            }}
            style={{ marginRight: 8 }}
          >
            Rename
          </Button>
          <Button
            danger
            icon={<Trash2 size={14} />}
            onClick={() => {
              Modal.destroyAll();
              deleteItem(item.path, item.type === 'directory');
            }}
          >
            Delete
          </Button>
        </div>
      ),
      footer: null,
      closable: true,
      maskClosable: true
    });
  }, [deleteItem]);

  // Initial load - 只在组件挂载且 sendWSMessage 可用时执行一次
  useEffect(() => {
    if (initialLoadDone.current) return;
    if (!sendWSMessage) return;

    initialLoadDone.current = true;

    fetchRoot();
    // 直接调用 sendWSMessage 而不是通过 listDirectory，避免依赖问题
    sendWSMessage('workspace_list', { path: '.' }).then(response => {
      if (response.data?.items) {
        setItems(response.data.items);
        setCurrentPath(response.data.path || '.');
        setTreeItems({ '.': response.data.items });
      }
    }).catch(err => {
      console.error('Failed to load workspace:', err);
      message.error('Failed to load workspace: ' + err.message);
    });
  }, [sendWSMessage]); // 添加 sendWSMessage 到依赖数组

  // Filter items by search
  const filteredItems = items.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="workspace-panel-container">
      {/* Toolbar */}
      <div className="workspace-toolbar">
        <div className="toolbar-left">
          <WindowDots />
          <span className="toolbar-title">WORKSPACE_EXPLORER</span>
        </div>
        <div className="toolbar-right">
          <button
            className="toolbar-btn"
            onClick={() => listDirectory(currentPath)}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
          <button
            className="toolbar-btn"
            onClick={() => setIsCreateFolderModalOpen(true)}
          >
            <FolderPlus size={14} />
          </button>
          <button
            className="toolbar-btn"
            onClick={() => setIsCreateFileModalOpen(true)}
          >
            <FilePlus size={14} />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="workspace-content">
        {/* Sidebar - Tree View */}
        <div className="workspace-sidebar">
          <div className="sidebar-header">
            <span>EXPLORER</span>
          </div>
          <div className="tree-view">
            {treeItems['.']?.map(item => (
              <TreeNode
                key={item.path}
                item={item}
                level={0}
                selectedPath={selectedPath}
                expandedPaths={expandedPaths}
                onSelect={handleSelect}
                onToggle={handleTreeExpand}
                onContextMenu={handleContextMenu}
                treeItems={treeItems}
              />
            ))}
          </div>
        </div>

        {/* File Editor */}
        {editingFile ? (
          <FileEditor
            file={editingFile}
            content={fileContent}
            onSave={writeFile}
            onClose={() => {
              setEditingFile(null);
              setFileContent('');
            }}
            isSaving={isSaving}
            sendWSMessage={sendWSMessage}
          />
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666' }}>
            Select a file to view its contents
          </div>
        )}
      </div>

      {/* Create Folder Modal */}
      <Modal
        title="Create New Folder"
        open={isCreateFolderModalOpen}
        onOk={createDirectory}
        onCancel={() => {
          setIsCreateFolderModalOpen(false);
          setNewName('');
        }}
        okText="Create"
      >
        <Input
          placeholder="Folder name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={createDirectory}
          autoFocus
        />
      </Modal>

      {/* Create File Modal */}
      <Modal
        title="Create New File"
        open={isCreateFileModalOpen}
        onOk={createFile}
        onCancel={() => {
          setIsCreateFileModalOpen(false);
          setNewName('');
        }}
        okText="Create"
      >
        <Input
          placeholder="File name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={createFile}
          autoFocus
        />
      </Modal>

      {/* Rename Modal */}
      <Modal
        title="Rename"
        open={isRenameModalOpen}
        onOk={renameItem}
        onCancel={() => {
          setIsRenameModalOpen(false);
          setNewName('');
          setContextMenuItem(null);
        }}
        okText="Rename"
      >
        <Input
          placeholder="New name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={renameItem}
          autoFocus
        />
      </Modal>
    </div>
  );
};

export { FileEditor };
export default WorkspacePanel;
