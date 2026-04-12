import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Edit3, Save, Columns, Share2 } from 'lucide-react';
import Editor from '@monaco-editor/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
};

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

export default function NoteEditor({ fileName, content, onSave, sendWSMessage, onViewInGraph }) {
  const draftKey = `kb:draft:${fileName}`;
  const [editedContent, setEditedContent] = useState(content ?? '');
  const [isDirty, setIsDirty] = useState(false);
  const [isSplit, setIsSplit] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const editorRef = useRef(null);

  useEffect(() => {
    const draft = localStorage.getItem(draftKey);
    if (draft && draft !== (content ?? '')) {
      setEditedContent(draft);
      setIsDirty(true);
    } else {
      setEditedContent(content ?? '');
      setIsDirty(false);
    }
    setIsSplit(true);
  }, [content, fileName, draftKey]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (isDirty) {
        localStorage.setItem(draftKey, editedContent);
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [isDirty, editedContent, draftKey]);

  const handleSave = useCallback(async () => {
    if (!isDirty || isSaving) return;
    setIsSaving(true);
    try {
      await onSave(editedContent);
      setIsDirty(false);
      localStorage.removeItem(draftKey);
    } finally {
      setIsSaving(false);
    }
  }, [editedContent, isDirty, isSaving, onSave, draftKey]);

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      if (!isSaving) {
        handleSave();
      }
    });

    if (isMarkdown) {
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
                  position.column - (match[0].length),
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
  };

  const ext = fileName.split('.').pop()?.toLowerCase() || '';
  const isMarkdown = ext === 'md';
  const language = getLanguage(fileName);

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--surface)',
        borderRadius: 8,
        overflow: 'hidden',
        margin: 16,
        border: '1px solid var(--border)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface-2)',
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>{fileName}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isMarkdown && (
            <>
              <button
                onClick={() => setIsSplit((s) => !s)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '4px 10px',
                  borderRadius: 4,
                  border: 'none',
                  background: isSplit ? 'var(--accent-soft)' : 'transparent',
                  color: 'var(--text)',
                  cursor: 'pointer',
                  fontSize: 12,
                }}
                title={isSplit ? 'Focus edit' : 'Split view'}
              >
                {isSplit ? <Edit3 size={14} /> : <Columns size={14} />}
                <span>{isSplit ? 'Edit' : 'Split'}</span>
              </button>
              <button
                onClick={() => {
                  if (onViewInGraph) onViewInGraph();
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '4px 10px',
                  borderRadius: 4,
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--text)',
                  cursor: 'pointer',
                  fontSize: 12,
                }}
                title="View in Graph"
              >
                <Share2 size={14} />
                <span>View in Graph</span>
              </button>
            </>
          )}
          <button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 10px',
              borderRadius: 4,
              border: 'none',
              background: !isDirty || isSaving ? 'var(--surface-3)' : 'var(--accent)',
              color: 'var(--text-invert)',
              cursor: !isDirty || isSaving ? 'not-allowed' : 'pointer',
              fontSize: 12,
              opacity: !isDirty || isSaving ? 0.7 : 1,
            }}
          >
            {isSaving ? <span className="spin" /> : <Save size={14} />}
            <span>Save {isDirty ? '*' : ''}</span>
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
        <div style={{ flex: isMarkdown && isSplit ? 1 : undefined, width: '100%', height: '100%', display: 'flex' }}>
          <Editor
            height="100%"
            width="100%"
            language={language}
            value={editedContent}
            onChange={(value) => {
              setEditedContent(value);
              setIsDirty(true);
            }}
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
              readOnly: false,
            }}
            theme="vs"
          />
        </div>
        {isMarkdown && isSplit && (
          <div style={{ flex: 1, borderLeft: '1px solid var(--border)', overflow: 'hidden' }}>
            <MarkdownViewer content={editedContent} />
          </div>
        )}
      </div>
    </div>
  );
}
