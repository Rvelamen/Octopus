import React, { useState, useEffect, useCallback, useRef } from 'react';
import Editor from '@monaco-editor/react';
import { MDXEditor } from '@mdxeditor/editor';
import {
  headingsPlugin,
  listsPlugin,
  quotePlugin,
  thematicBreakPlugin,
  markdownShortcutPlugin,
  linkPlugin,
  imagePlugin,
  tablePlugin,
  codeBlockPlugin,
  codeMirrorPlugin,
  toolbarPlugin,

  diffSourcePlugin,
  directivesPlugin,
  AdmonitionDirectiveDescriptor,
  UndoRedo,
  BoldItalicUnderlineToggles,
  CodeToggle,
  HighlightToggle,
  ListsToggle,
  BlockTypeSelect,
  CreateLink,
  InsertImage,
  InsertTable,
  InsertCodeBlock,
  InsertThematicBreak,
  Separator,
} from '@mdxeditor/editor';
import { Save, Share2, ChevronRight, FileText, ExternalLink, X, Bot } from 'lucide-react';
import './SimpleEditor.css';
import '@mdxeditor/editor/style.css';

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

// MDXEditor 静态 plugins（不依赖组件状态，避免 hooks 条件调用问题）
const MDX_PLUGINS = [
  toolbarPlugin({
    toolbarContents: () => (
      <div className="simple-mdx-toolbar">
        <UndoRedo />
        <Separator />
        <BoldItalicUnderlineToggles />
        <CodeToggle />
        <HighlightToggle />
        <Separator />
        <ListsToggle />
        <Separator />
        <BlockTypeSelect />
        <Separator />
        <CreateLink />
        <InsertImage />
        <InsertTable />
        <InsertCodeBlock />
        <InsertThematicBreak />
      </div>
    ),
  }),
  headingsPlugin(),
  listsPlugin(),
  quotePlugin(),
  thematicBreakPlugin(),
  markdownShortcutPlugin(),
  linkPlugin(),
  imagePlugin(),
  tablePlugin(),
  codeBlockPlugin(),
  codeMirrorPlugin(),

  diffSourcePlugin(),
  directivesPlugin({ directiveDescriptors: [AdmonitionDirectiveDescriptor] }),
];

// 面包屑导航
const Breadcrumbs = ({ path, onNavigate }) => {
  if (!path) return null;

  const parts = path.split('/');
  return (
    <div className="simple-breadcrumbs">
      {parts.map((part, index) => (
        <React.Fragment key={index}>
          {index > 0 && <ChevronRight size={12} className="simple-breadcrumb-separator" />}
          <span
            className="simple-breadcrumb-item"
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

export default function SimpleEditor({
  file,
  onSave,
  sendWSMessage,
  onViewInGraph,
  onClose,
  onToggleChat,
  chatOpen,
}) {
  const [content, setContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const monacoRef = useRef(null);
  const mdxRef = useRef(null);

  // 当文件变化时重置内容
  useEffect(() => {
    if (file) {
      const nextContent = file.content || '';
      setContent(nextContent);
      setOriginalContent(nextContent);
      setIsDirty(false);
      // MDXEditor 的 markdown prop 只在初始化时读取，切换文件需显式 setMarkdown
      if (mdxRef.current) {
        mdxRef.current.setMarkdown(nextContent);
      }
    }
  }, [file?.path]);

  // Monaco 内容变更
  const handleContentChange = useCallback((value) => {
    setContent(value);
    setIsDirty(true);
  }, []);

  // MDXEditor 内容变更
  const handleMdxChange = useCallback((value) => {
    setContent(value);
    setIsDirty(value !== originalContent);
  }, [originalContent]);

  // 处理保存
  const handleSave = useCallback(async () => {
    if (!file || !isDirty || isSaving) return;

    const isMarkdown = file.name?.endsWith('.md');
    const saveContent = isMarkdown && mdxRef.current
      ? mdxRef.current.getMarkdown()
      : content;

    setIsSaving(true);
    try {
      await onSave?.(file.path, saveContent);
      setOriginalContent(saveContent);
      setIsDirty(false);
    } catch (err) {
      console.error('Save failed:', err);
    } finally {
      setIsSaving(false);
    }
  }, [file, content, isDirty, isSaving, onSave]);

  // 快捷键
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSave]);

  // Monaco Editor 挂载
  const handleEditorDidMount = (editor, monaco) => {
    monacoRef.current = editor;
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      handleSave();
    });
  };

  if (!file) {
    return (
      <div className="simple-editor">
        <div className="simple-editor-empty">
          <FileText size={48} style={{ opacity: 0.3 }} />
          <span>Select a file to start editing</span>
        </div>
      </div>
    );
  }

  const isMarkdown = file.name?.endsWith('.md');
  const language = getLanguage(file.name);
  const sourceUrl = file.meta?.source;
  const hasSource = sourceUrl && typeof sourceUrl === 'string' && sourceUrl.startsWith('http');

  return (
    <div className="simple-editor">
      {/* Source link banner */}
      {hasSource && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '8px 16px',
            background: 'var(--accent-soft)',
            borderBottom: '1px solid var(--border)',
            fontSize: 12,
          }}
        >
          <span style={{ color: 'var(--text-2)' }}>🔗 来源：</span>
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              color: 'var(--accent)',
              textDecoration: 'none',
              fontWeight: 500,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={sourceUrl}
          >
            {sourceUrl.length > 60 ? sourceUrl.slice(0, 60) + '...' : sourceUrl}
            <ExternalLink size={12} />
          </a>
        </div>
      )}

      {/* 头部工具栏 */}
      <div className="simple-editor-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, overflow: 'hidden' }}>
          <Breadcrumbs path={file.path} />
          {isDirty && <span className="simple-editor-dirty">● modified</span>}
        </div>
        <div className="simple-editor-actions">
          <button
            className={`simple-editor-btn ${chatOpen ? 'active' : ''}`}
            onClick={onToggleChat}
            title="Toggle chat"
          >
            <Bot size={14} />
            <span>Chat</span>
          </button>
          {isMarkdown && (
            <button
              className="simple-editor-btn"
              onClick={() => onViewInGraph?.(file.path)}
              title="View in Graph"
            >
              <Share2 size={14} />
              <span>Graph</span>
            </button>
          )}
          <button
            className="simple-editor-btn"
            onClick={handleSave}
            disabled={!isDirty || isSaving}
          >
            <Save size={14} />
            <span>{isSaving ? 'Saving...' : 'Save'}</span>
          </button>
          <button
            className="simple-editor-btn simple-editor-btn-close"
            onClick={onClose}
            title="Close file"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* 编辑器内容区 */}
      <div className="simple-editor-content">
        <div className="simple-editor-pane">
          {isMarkdown ? (
            <div className="simple-mdx-editor">
              <MDXEditor
                ref={mdxRef}
                markdown={content}
                onChange={handleMdxChange}
                plugins={MDX_PLUGINS}
                contentEditableClassName="simple-mdx-content"
              />
            </div>
          ) : (
            <div style={{ flex: 1, minWidth: 0, height: '100%' }}>
              <Editor
                height="100%"
                width="100%"
                language={language}
                value={content}
                onChange={handleContentChange}
                onMount={handleEditorDidMount}
                options={{
                  minimap: { enabled: false },
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
          )}
        </div>
      </div>
    </div>
  );
}
