import React, { useState, useCallback, useRef, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  X,
  FileText,
  FileCode,
  FileImage,
  FileJson,
  Folder,
  Edit3,
  Columns,
  Share2,
  Save,
  Plus,
  ChevronRight,
  FileType,
} from 'lucide-react';
import './VSCodeEditor.css';

// 文件图标映射
const getFileIcon = (fileName) => {
  const ext = fileName.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'js':
    case 'jsx':
    case 'ts':
    case 'tsx':
      return <FileCode size={14} color="#519aba" />;
    case 'json':
      return <FileJson size={14} color="#cbcb41" />;
    case 'md':
      return <FileText size={14} color="#519aba" />;
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'svg':
      return <FileImage size={14} color="#a074c4" />;
    case 'css':
    case 'scss':
    case 'less':
      return <FileType size={14} color="#42a5f5" />;
    default:
      return <FileText size={14} color="#7f7f7f" />;
  }
};

// 获取语言
const getLanguage = (filename) => {
  const ext = filename.split('.').pop()?.toLowerCase();
  const map = {
    js: 'javascript',
    jsx: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    py: 'python',
    md: 'markdown',
    json: 'json',
    html: 'html',
    css: 'css',
    yaml: 'yaml',
    yml: 'yaml',
    xml: 'xml',
    sql: 'sql',
    sh: 'shell',
    bash: 'shell',
    c: 'c',
    cpp: 'cpp',
    h: 'cpp',
    java: 'java',
    go: 'go',
    rs: 'rust',
    php: 'php',
    rb: 'ruby',
    log: 'plaintext',
    txt: 'plaintext',
  };
  return map[ext] || 'plaintext';
};

// Markdown 预览组件
const MarkdownViewer = ({ content }) => {
  if (!content) {
    return (
      <div style={{ padding: 24, color: 'var(--text-2)', textAlign: 'center' }}>
        No content to preview
      </div>
    );
  }
  return (
    <div
      style={{
        padding: 24,
        color: 'var(--text)',
        fontSize: 14,
        lineHeight: 1.6,
        overflowY: 'auto',
        height: '100%',
      }}
      className="markdown-preview"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
};

// 单个编辑器标签页
const EditorTab = ({ file, isActive, isDirty, onClick, onClose }) => {
  return (
    <div
      className={`vscode-tab ${isActive ? 'active' : ''} ${isDirty ? 'dirty' : ''}`}
      onClick={onClick}
      onMouseDown={(e) => {
        if (e.button === 1) {
          e.preventDefault();
          onClose();
        }
      }}
    >
      <span className="vscode-tab-icon">{getFileIcon(file.name)}</span>
      <span className="vscode-tab-name">{file.name}</span>
      <span
        className="vscode-tab-close"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
      >
        <X size={14} />
      </span>
    </div>
  );
};

// 面包屑导航
const Breadcrumbs = ({ path, onNavigate }) => {
  if (!path) return null;

  const parts = path.split('/');
  return (
    <div className="vscode-breadcrumbs">
      {parts.map((part, index) => (
        <React.Fragment key={index}>
          {index > 0 && <ChevronRight size={12} className="vscode-breadcrumb-separator" />}
          <span
            className="vscode-breadcrumb-item"
            onClick={() => {
              const navigatePath = parts.slice(0, index + 1).join('/');
              onNavigate?.(navigatePath);
            }}
          >
            {part}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
};

// 空状态
const EmptyState = () => (
  <div className="vscode-editor-empty">
    <Folder size={64} className="vscode-editor-empty-icon" />
    <span>Select a file to start editing</span>
    <div className="vscode-editor-empty-shortcuts">
      <div className="vscode-editor-empty-shortcut">
        <kbd>Ctrl</kbd> + <kbd>P</kbd>
        <span>Quick Open</span>
      </div>
      <div className="vscode-editor-empty-shortcut">
        <kbd>Ctrl</kbd> + <kbd>S</kbd>
        <span>Save</span>
      </div>
    </div>
  </div>
);

export default function VSCodeEditor({
  files,
  activeFileId,
  onChangeActive,
  onCloseFile,
  onSave,
  sendWSMessage,
  onViewInGraph,
}) {
  const [splitView, setSplitView] = useState(true);
  const [dirtyFiles, setDirtyFiles] = useState(new Set());
  const [fileContents, setFileContents] = useState({});
  const editorRefs = useRef({});

  const activeFile = files.find((f) => f.id === activeFileId);

  // 初始化文件内容
  useEffect(() => {
    const newContents = {};
    files.forEach((file) => {
      if (!(file.id in fileContents)) {
        newContents[file.id] = file.content || '';
      }
    });
    if (Object.keys(newContents).length > 0) {
      setFileContents((prev) => ({ ...prev, ...newContents }));
    }
  }, [files]);

  // 处理内容变更
  const handleContentChange = useCallback(
    (fileId, value) => {
      setFileContents((prev) => ({ ...prev, [fileId]: value }));
      setDirtyFiles((prev) => new Set(prev).add(fileId));
    },
    []
  );

  // 处理保存
  const handleSave = useCallback(
    async (fileId) => {
      const file = files.find((f) => f.id === fileId);
      if (!file || !dirtyFiles.has(fileId)) return;

      try {
        await onSave?.(file.path, fileContents[fileId]);
        setDirtyFiles((prev) => {
          const next = new Set(prev);
          next.delete(fileId);
          return next;
        });
      } catch (err) {
        console.error('Save failed:', err);
      }
    },
    [files, dirtyFiles, fileContents, onSave]
  );

  // 快捷键
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (activeFileId) {
          handleSave(activeFileId);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeFileId, handleSave]);

  // Monaco Editor 挂载
  const handleEditorDidMount = (editor, monaco, fileId) => {
    editorRefs.current[fileId] = editor;

    const file = files.find((f) => f.id === fileId);
    if (!file) return;

    // 添加 [[链接]] 自动补全
    if (file.name.endsWith('.md')) {
      monaco.languages.registerCompletionItemProvider('markdown', {
        triggerCharacters: ['['],
        provideCompletionItems: async (model, position) => {
          const lineContent = model.getLineContent(position.lineNumber);
          const textBeforeCursor = lineContent.substring(0, position.column - 1);
          const match = textBeforeCursor.match(/\[\[([^\[\]]*)$/);
          if (!match) return { suggestions: [] };

          const query = match[1].trim();
          try {
            const resp = await sendWSMessage('knowledge_search', { query });
            const results = resp.data?.results || [];
            const suggestions = results.map((r) => {
              const label = r.title || r.path.split('/').pop();
              return {
                label: `[[${label}]]`,
                kind: monaco.languages.CompletionItemKind.Reference,
                insertText: `[[${label}]]`,
                range: new monaco.Range(
                  position.lineNumber,
                  position.column - match[0].length,
                  position.lineNumber,
                  position.column
                ),
              };
            });
            return { suggestions };
          } catch {
            return { suggestions: [] };
          }
        },
      });
    }

    // 绑定保存快捷键
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      handleSave(fileId);
    });
  };

  if (files.length === 0) {
    return (
      <div className="vscode-editor">
        <EmptyState />
      </div>
    );
  }

  const isMarkdown = activeFile?.name.endsWith('.md');
  const language = activeFile ? getLanguage(activeFile.name) : 'plaintext';
  const currentContent = activeFileId ? fileContents[activeFileId] || '' : '';

  return (
    <div className="vscode-editor">
      {/* 标签页栏 */}
      <div className="vscode-tabs">
        {files.map((file) => (
          <EditorTab
            key={file.id}
            file={file}
            isActive={file.id === activeFileId}
            isDirty={dirtyFiles.has(file.id)}
            onClick={() => onChangeActive(file.id)}
            onClose={() => onCloseFile(file.id)}
          />
        ))}
        <div className="vscode-tab-new" title="New File">
          <Plus size={16} />
        </div>
      </div>

      {/* 面包屑导航 */}
      {activeFile && <Breadcrumbs path={activeFile.path} />}

      {/* 工具栏 */}
      {activeFile && (
        <div className="vscode-editor-toolbar">
          <div className="vscode-editor-toolbar-left">
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>
              {activeFile.name}
            </span>
            {dirtyFiles.has(activeFileId) && (
              <span style={{ color: 'var(--accent)', fontSize: 12 }}>● Modified</span>
            )}
          </div>
          <div className="vscode-editor-toolbar-right">
            {isMarkdown && (
              <>
                <button
                  className={`vscode-editor-toolbar-btn ${splitView ? 'active' : ''}`}
                  onClick={() => setSplitView((s) => !s)}
                  title={splitView ? 'Focus edit' : 'Split view'}
                >
                  {splitView ? <Edit3 size={14} /> : <Columns size={14} />}
                  <span>{splitView ? 'Edit' : 'Split'}</span>
                </button>
                <button
                  className="vscode-editor-toolbar-btn"
                  onClick={() => onViewInGraph?.(activeFile.path)}
                  title="View in Graph"
                >
                  <Share2 size={14} />
                  <span>Graph</span>
                </button>
              </>
            )}
            <button
              className="vscode-editor-toolbar-btn"
              onClick={() => handleSave(activeFileId)}
              disabled={!dirtyFiles.has(activeFileId)}
            >
              <Save size={14} />
              <span>Save</span>
            </button>
          </div>
        </div>
      )}

      {/* 编辑器内容区 */}
      <div className="vscode-editor-content">
        {activeFile ? (
          <div
            className={
              isMarkdown && splitView ? 'vscode-editor-split' : 'vscode-editor-pane'
            }
          >
            <div className="vscode-editor-pane">
              <Editor
                height="100%"
                width="100%"
                language={language}
                value={currentContent}
                onChange={(value) => handleContentChange(activeFileId, value)}
                onMount={(editor, monaco) =>
                  handleEditorDidMount(editor, monaco, activeFileId)
                }
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
                  readOnly: false,
                }}
                theme="vs"
              />
            </div>
            {isMarkdown && splitView && (
              <div className="vscode-editor-pane">
                <MarkdownViewer content={currentContent} />
              </div>
            )}
          </div>
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  );
}
