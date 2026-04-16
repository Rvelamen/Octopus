import React, { useState, useEffect, useCallback, useRef } from 'react';
import Editor from '@monaco-editor/react';
import MarkdownRenderer from '@components/MarkdownRenderer';
import { Edit3, Save, Columns, Share2, ChevronRight, FileText, ExternalLink } from 'lucide-react';
import './SimpleEditor.css';

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
}) {
  const [content, setContent] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [isSplit, setIsSplit] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const editorRef = useRef(null);

  // 当文件变化时重置内容
  useEffect(() => {
    if (file) {
      setContent(file.content || '');
      setIsDirty(false);
    }
  }, [file?.path]);

  // 处理内容变更
  const handleContentChange = useCallback((value) => {
    setContent(value);
    setIsDirty(true);
  }, []);

  // 处理保存
  const handleSave = useCallback(async () => {
    if (!file || !isDirty || isSaving) return;

    setIsSaving(true);
    try {
      await onSave?.(file.path, content);
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
    editorRef.current = editor;

    // 添加 [[链接]] 自动补全
    if (file?.name?.endsWith('.md')) {
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
  const archivePath = file.meta?.archive;
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
          {archivePath && (
            <>
              <span style={{ color: 'var(--text-3)' }}>|</span>
              <span style={{ color: 'var(--text-3)' }}>📄 本地存档: {archivePath}</span>
            </>
          )}
        </div>
      )}

      {/* 头部工具栏 */}
      <div className="simple-editor-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, overflow: 'hidden' }}>
          <Breadcrumbs path={file.path} />
          {isDirty && <span className="simple-editor-dirty">● modified</span>}
        </div>
        <div className="simple-editor-actions">
          {isMarkdown && (
            <>
              <button
                className={`simple-editor-btn ${isSplit ? 'active' : ''}`}
                onClick={() => setIsSplit((s) => !s)}
                title={isSplit ? 'Focus edit' : 'Split view'}
              >
                {isSplit ? <Edit3 size={14} /> : <Columns size={14} />}
                <span>{isSplit ? 'Edit' : 'Split'}</span>
              </button>
              <button
                className="simple-editor-btn"
                onClick={() => onViewInGraph?.(file.path)}
                title="View in Graph"
              >
                <Share2 size={14} />
                <span>Graph</span>
              </button>
            </>
          )}
          <button
            className="simple-editor-btn"
            onClick={handleSave}
            disabled={!isDirty || isSaving}
          >
            <Save size={14} />
            <span>{isSaving ? 'Saving...' : 'Save'}</span>
          </button>
        </div>
      </div>

      {/* 编辑器内容区 */}
      <div className="simple-editor-content">
        <div
          className="simple-editor-pane"
          style={{
            display: 'flex',
            flexDirection: isMarkdown && isSplit ? 'row' : 'column',
          }}
        >
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
          {isMarkdown && isSplit && (
            <div
              style={{
                flex: 1,
                borderLeft: '1px solid var(--border)',
                overflow: 'hidden',
                height: '100%',
              }}
            >
              <MarkdownRenderer content={content} sendWSMessage={sendWSMessage} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
