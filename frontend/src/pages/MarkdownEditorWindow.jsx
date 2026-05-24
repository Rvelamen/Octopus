import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { X, Save } from 'lucide-react';
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
  frontmatterPlugin,
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
import { useWebSocket } from '../contexts/WebSocketContext';
import '@mdxeditor/editor/style.css';
import './MarkdownEditorWindow.css';

function parseHashParams() {
  const hash = window.location.hash;
  const queryIndex = hash.indexOf('?');
  const search = queryIndex !== -1 ? hash.slice(queryIndex + 1) : '';
  return new URLSearchParams(search);
}

const MarkdownEditorWindow = () => {
  const params = parseHashParams();
  const filePath = params.get('path');
  const fileTitle = params.get('title') || 'Markdown Editor';

  const { sendMessage } = useWebSocket();
  const editorRef = useRef(null);

  const [content, setContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Refs to pass dynamic values into the stable toolbar without recreating plugins
  const fileTitleRef = useRef(fileTitle);
  fileTitleRef.current = fileTitle;

  const isDirtyRef = useRef(false);
  isDirtyRef.current = content !== originalContent;

  const savedRef = useRef(false);
  savedRef.current = saved;

  const handleSaveRef = useRef(async () => {});

  // Load file content
  useEffect(() => {
    if (!filePath) {
      setError('No file path provided');
      setLoading(false);
      return;
    }
    let cancelled = false;
    const loadFile = async () => {
      setLoading(true);
      try {
        const response = await sendMessage('workspace_read', { path: filePath }, 30000);
        if (response?.data?.content) {
          const encoding = response.data.encoding || 'hex';
          let text;
          if (encoding === 'hex') {
            const hex = response.data.content.replace(/\s/g, '');
            const bytes = new Uint8Array(hex.match(/.{1,2}/g).map((b) => parseInt(b, 16)));
            text = new TextDecoder().decode(bytes);
          } else {
            text = response.data.content;
          }
          if (!cancelled) {
            setContent(text);
            setOriginalContent(text);
          }
        } else {
          if (!cancelled) {
            setContent('');
            setOriginalContent('');
          }
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load file');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadFile();
    return () => { cancelled = true; };
  }, [filePath, sendMessage]);

  const handleSave = useCallback(async () => {
    if (!filePath || saving) return;
    const currentMd = editorRef.current ? editorRef.current.getMarkdown() : content;
    setSaving(true);
    try {
      const encoder = new TextEncoder();
      const bytes = encoder.encode(currentMd);
      const hex = Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
      await sendMessage('workspace_write', {
        path: filePath,
        content: hex,
        encoding: 'hex',
      }, 30000);
      setOriginalContent(currentMd);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err.message || 'Failed to save file');
    } finally {
      setSaving(false);
    }
  }, [filePath, content, saving, sendMessage]);

  // Update ref so toolbar can call latest save
  handleSaveRef.current = handleSave;

  const handleClose = useCallback(() => window.close(), []);

  const handleKeyDown = useCallback((e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      handleSave();
    }
  }, [handleSave]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const plugins = useMemo(
    () => [
      toolbarPlugin({
        toolbarContents: () => (
          <div className="mdew-toolbar-row">
            <span className="mdew-title">{decodeURIComponent(fileTitleRef.current)}</span>
            {isDirtyRef.current && <span className="mdew-dirty">●</span>}
            <div className="mdew-toolbar-gap" />
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
            <div style={{ flex: 1, minWidth: 8 }} />
            {savedRef.current && <span className="mdew-saved">Saved</span>}
            <button
              className="mdew-btn mdew-btn-primary"
              onClick={() => handleSaveRef.current()}
              title="Save (Ctrl+S)"
            >
              <Save size={14} />
              <span>Save</span>
            </button>
            <button className="mdew-btn" onClick={handleClose} title="Close">
              <X size={16} />
            </button>
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
      frontmatterPlugin(),
      diffSourcePlugin(),
      directivesPlugin({ directiveDescriptors: [AdmonitionDirectiveDescriptor] }),
    ],
    []
  );

  if (loading) {
    return (
      <div className="mdew-loading">
        <div className="mdew-spinner" />
        <span>Loading…</span>
      </div>
    );
  }

  if (error && !content) {
    return (
      <div className="mdew-error">
        <span className="mdew-error-icon">⚠</span>
        <span>{error}</span>
      </div>
    );
  }

  return (
    <div className="mdew-root">
      <div className="mdew-editor">
        <MDXEditor
          ref={editorRef}
          markdown={content}
          onChange={setContent}
          plugins={plugins}
          contentEditableClassName="mdew-content"
        />
      </div>
    </div>
  );
};

export default MarkdownEditorWindow;
