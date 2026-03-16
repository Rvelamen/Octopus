import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Folder, File, ChevronRight, ChevronDown, Home,
  RefreshCw, Plus, Trash2, Edit3, Save, X, FolderPlus,
  FilePlus, ArrowLeft, Search, FileText, Image, Code,
  MoreVertical, Download, Upload
} from 'lucide-react';
import { Modal, Input, Button, Dropdown, Menu, message, Table } from 'antd';
import Editor from '@monaco-editor/react';
import * as XLSX from 'xlsx';
import { Document, Page, pdfjs } from 'react-pdf';
import WindowDots from '../WindowDots';

// 设置 pdf.js worker - 使用 jsdelivr CDN
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

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
const formatSize = (bytes) => {
  if (bytes === null || bytes === undefined) return '-';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

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
const hexToBase64 = (hex) => {
  if (!hex) return '';
  try {
    const bytes = new Uint8Array(hex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    const binary = bytes.reduce((acc, byte) => acc + String.fromCharCode(byte), '');
    return btoa(binary);
  } catch (e) {
    console.error('Failed to convert hex to base64:', e);
    return '';
  }
};

/**
 * Image Viewer Component
 */
const ImageViewer = ({ file, content, fileExt }) => {
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [imageUrl, setImageUrl] = useState(null);

  useEffect(() => {
    try {
      let byteArray;
      if (file.encoding === 'hex') {
        const hexString = content.replace(/\s/g, '');
        byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
      } else {
        const binaryData = atob(content);
        byteArray = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
          byteArray[i] = binaryData.charCodeAt(i);
        }
      }
      
      const mimeType = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'svg': 'image/svg+xml',
        'webp': 'image/webp'
      }[fileExt] || 'image/png';
      
      const blob = new Blob([byteArray], { type: mimeType });
      const url = URL.createObjectURL(blob);
      setImageUrl(url);
      
      return () => {
        URL.revokeObjectURL(url);
      };
    } catch (err) {
      console.error('Failed to load image:', err);
      setError(true);
      setLoading(false);
    }
  }, [content, file.encoding, fileExt]);

  if (error) {
    return (
      <div className="image-preview error">
        <Image size={48} />
        <p>Unable to preview image</p>
        <p style={{ fontSize: '12px', color: '#666' }}>{file.name}</p>
      </div>
    );
  }

  return (
    <div className="image-preview">
      {loading && (
        <div className="image-loading">
          <RefreshCw size={24} className="spin" />
          <p>Loading image...</p>
        </div>
      )}
      {imageUrl && (
        <img
          src={imageUrl}
          alt={file.name}
          style={{ display: loading ? 'none' : 'block', maxWidth: '100%', maxHeight: '100%' }}
          onLoad={() => setLoading(false)}
          onError={() => {
            setLoading(false);
            setError(true);
          }}
        />
      )}
    </div>
  );
};

/**
 * XLSX Viewer Component
 */
const XlsxViewer = ({ file, content }) => {
  const [data, setData] = useState([]);
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    try {
      console.log('XlsxViewer - file.encoding:', file.encoding, 'content length:', content?.length);
      
      // 将 hex 直接转换为 Uint8Array
      let byteArray;
      if (file.encoding === 'hex') {
        const hexString = content.replace(/\s/g, ''); // 移除空白字符
        console.log('Parsing hex string, length:', hexString.length);
        byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
      } else if (file.encoding === 'base64') {
        // 如果是 base64 编码
        console.log('Parsing base64 content');
        const binaryData = atob(content);
        byteArray = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
          byteArray[i] = binaryData.charCodeAt(i);
        }
      } else {
        // 未知编码，尝试直接作为文本处理
        console.log('Unknown encoding, trying to parse as text');
        byteArray = new TextEncoder().encode(content);
      }
      
      console.log('Byte array length:', byteArray.length);
      const workbook = XLSX.read(byteArray, { type: 'array' });
      
      // 获取第一个工作表
      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];
      
      // 转换为 JSON
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
      
      if (jsonData.length > 0) {
        // 第一行作为表头
        const headers = jsonData[0];
        const cols = headers.map((header, index) => ({
          title: header || `Column ${index + 1}`,
          dataIndex: `col${index}`,
          key: `col${index}`,
          ellipsis: true,
        }));
        
        // 数据行
        const rows = jsonData.slice(1).map((row, rowIndex) => {
          const rowData = { key: rowIndex };
          headers.forEach((_, colIndex) => {
            rowData[`col${colIndex}`] = row[colIndex] || '';
          });
          return rowData;
        });
        
        setColumns(cols);
        setData(rows);
      }
      setLoading(false);
    } catch (err) {
      console.error('Failed to parse xlsx:', err);
      setError('Failed to parse Excel file');
      setLoading(false);
    }
  }, [content, file.encoding]);

  if (loading) {
    return (
      <div className="xlsx-preview loading">
        <RefreshCw size={32} className="spin" />
        <p>Loading Excel file...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="xlsx-preview error">
        <File size={48} />
        <p>{error}</p>
        <p style={{ fontSize: '12px', color: '#666' }}>{file.name}</p>
      </div>
    );
  }

  return (
    <div className="xlsx-preview">
      <div className="xlsx-header">
        <span className="xlsx-filename">{file.name}</span>
        <span className="xlsx-sheet">Sheet: 1 of 1</span>
      </div>
      <div className="xlsx-content">
        <Table
          columns={columns}
          dataSource={data}
          pagination={{ pageSize: 50 }}
          size="small"
          scroll={{ x: 'max-content', y: 'calc(100vh - 300px)' }}
        />
      </div>
    </div>
  );
};

/**
 * PDF Viewer Component
 */
const PdfViewer = ({ file, content }) => {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    try {
      // 将 hex 直接转换为 Uint8Array
      let byteArray;
      if (file.encoding === 'hex') {
        const hexString = content.replace(/\s/g, ''); // 移除空白字符
        byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
      } else {
        // 如果是 base64 编码
        const binaryData = atob(content);
        byteArray = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
          byteArray[i] = binaryData.charCodeAt(i);
        }
      }
      const blob = new Blob([byteArray], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      setPdfUrl(url);
      setLoading(false);
      
      return () => {
        URL.revokeObjectURL(url);
      };
    } catch (err) {
      console.error('Failed to load pdf:', err);
      setError('Failed to load PDF file');
      setLoading(false);
    }
  }, [content, file.encoding]);

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages);
  };

  const goToPrevPage = () => setPageNumber((prev) => Math.max(prev - 1, 1));
  const goToNextPage = () => setPageNumber((prev) => Math.min(prev + 1, numPages));

  if (loading) {
    return (
      <div className="pdf-preview loading">
        <RefreshCw size={32} className="spin" />
        <p>Loading PDF file...</p>
      </div>
    );
  }

  if (error || !pdfUrl) {
    return (
      <div className="pdf-preview error">
        <File size={48} />
        <p>{error || 'Failed to load PDF'}</p>
        <p style={{ fontSize: '12px', color: '#666' }}>{file.name}</p>
      </div>
    );
  }

  return (
    <div className="pdf-preview">
      <div className="pdf-toolbar">
        <button 
          className="pdf-nav-btn" 
          onClick={goToPrevPage} 
          disabled={pageNumber <= 1}
        >
          ← Prev
        </button>
        <span className="pdf-page-info">
          Page {pageNumber} of {numPages || '?'}
        </span>
        <button 
          className="pdf-nav-btn" 
          onClick={goToNextPage} 
          disabled={pageNumber >= numPages}
        >
          Next →
        </button>
      </div>
      <div className="pdf-content">
        <Document
          file={pdfUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={<div className="pdf-page-loading">Loading page...</div>}
          error={<div className="pdf-page-error">Failed to load page</div>}
        >
          <Page 
            pageNumber={pageNumber} 
            scale={1.2}
            renderTextLayer={true}
            renderAnnotationLayer={true}
          />
        </Document>
      </div>
    </div>
  );
};

/**
 * Binary Viewer Component (for other binary files)
 */
const BinaryViewer = ({ file, content }) => {
  const fileExt = file.name.split('.').pop()?.toLowerCase() || '';
  const isDoc = ['doc', 'docx'].includes(fileExt);

  const handleDownload = () => {
    const binaryData = file.encoding === 'hex' ? hexToBase64(content) : content;
    const byteCharacters = atob(binaryData);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray]);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="binary-preview">
      <File size={48} />
      <p className="binary-filename">{file.name}</p>
      <p className="binary-size">{formatSize(file.size)}</p>
      <p className="binary-type">
        {isDoc && '📝 Word Document'}
        {!isDoc && '🔒 Binary File'}
      </p>
      <button className="binary-download-btn" onClick={handleDownload}>
        <Download size={16} />
        Download File
      </button>
      <p className="binary-hint">
        This file type cannot be previewed. Please download to view.
      </p>
    </div>
  );
};

/**
 * Get Monaco Editor language from file extension
 */
const getLanguage = (filename) => {
  const ext = filename.split('.').pop()?.toLowerCase();
  const languageMap = {
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'py': 'python',
    'java': 'java',
    'cpp': 'cpp',
    'c': 'c',
    'h': 'c',
    'go': 'go',
    'rs': 'rust',
    'php': 'php',
    'rb': 'ruby',
    'html': 'html',
    'htm': 'html',
    'css': 'css',
    'scss': 'scss',
    'less': 'less',
    'json': 'json',
    'xml': 'xml',
    'yaml': 'yaml',
    'yml': 'yaml',
    'md': 'markdown',
    'sql': 'sql',
    'sh': 'shell',
    'bash': 'shell',
    'zsh': 'shell',
    'dockerfile': 'dockerfile',
    'vue': 'vue',
    'svelte': 'svelte',
    'swift': 'swift',
    'kt': 'kotlin',
    'scala': 'scala',
    'r': 'r',
    'dart': 'dart',
    'lua': 'lua',
    'perl': 'perl',
    'clj': 'clojure',
    'cljs': 'clojure',
    'ex': 'elixir',
    'exs': 'elixir',
    'erl': 'erlang',
    'hrl': 'erlang',
    'fs': 'fsharp',
    'fsx': 'fsharp',
    'fsi': 'fsharp',
    'ml': 'ocaml',
    'mli': 'ocaml',
    'hs': 'haskell',
    'lhs': 'haskell',
    'elm': 'elm',
    'purs': 'purescript',
    'coffee': 'coffeescript',
    'litcoffee': 'coffeescript',
    'cs': 'csharp',
    'csx': 'csharp',
    'vb': 'vb',
    'ps1': 'powershell',
    'psm1': 'powershell',
    'psd1': 'powershell',
    'bat': 'bat',
    'cmd': 'bat',
    'ini': 'ini',
    'cfg': 'ini',
    'conf': 'ini',
    'properties': 'ini',
    'toml': 'toml',
    'lock': 'json',
    'gitignore': 'ignore',
    'dockerignore': 'ignore',
    'npmignore': 'ignore',
    'eslintignore': 'ignore',
    'prettierignore': 'ignore',
    'env': 'ini',
    'env.local': 'ini',
    'env.development': 'ini',
    'env.production': 'ini',
    'env.test': 'ini',
    'log': 'log',
    'txt': 'plaintext'
  };
  return languageMap[ext] || 'plaintext';
};

/**
 * File Editor Component with Monaco Editor
 */
const FileEditor = ({ file, content, onSave, onClose, isSaving }) => {
  // 确保 content 是字符串
  const safeContent = content ?? '';
  const [editedContent, setEditedContent] = useState(safeContent);
  const [isDirty, setIsDirty] = useState(false);
  const editorRef = useRef(null);

  // 监听 content 变化，更新 editedContent
  useEffect(() => {
    setEditedContent(safeContent);
    setIsDirty(false);
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
    
    // 添加保存快捷键 Ctrl+S / Cmd+S
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      if (isDirty && !isSaving) {
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
  const language = getLanguage(file.name);

  return (
    <div className="file-editor">
      <div className="file-editor-header">
        <WindowDots />
        <span className="editor-filename">{file.name}</span>
        <div className="editor-actions">
          {!isBinary && !isImage && (
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
        ) : isBinary ? (
          <BinaryViewer file={file} content={safeContent} />
        ) : (
          <Editor
            height="100%"
            language={language}
            value={editedContent}
            onChange={handleEditorChange}
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
              formatOnPaste: true,
              formatOnType: true,
              suggestOnTriggerCharacters: true,
              quickSuggestions: true,
              snippetSuggestions: 'inline',
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
          <div className="toolbar-icon">[]</div>
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

export default WorkspacePanel;
