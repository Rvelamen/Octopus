import React, { useState, useEffect } from 'react';
import { message } from 'antd';
import { X, Eye, Edit3, ExternalLink } from 'lucide-react';
import FileIcon from '../file-icon/FileIcon';
import {
  ImageViewer,
  PdfViewer,
  XlsxViewer,
  DocxViewer,
  PptxViewer,
  BinaryViewer,
  HtmlViewer,
  getLanguage,
} from '@components/FileViewers';
import Editor from '@monaco-editor/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const WIKI_LINK_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;

function preprocessWikiLinks(content) {
  return content.replace(WIKI_LINK_RE, (match, title, alias) => {
    const display = (alias || title).trim();
    return `[${display}](wiki://${encodeURIComponent(title.trim())})`;
  });
}

function WikiLink({ href, children, sendWSMessage }) {
  const title = decodeURIComponent(href.replace('wiki://', ''));
  const [loading, setLoading] = useState(false);

  const handleClick = async (e) => {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    try {
      const response = await sendWSMessage('knowledge_search', { query: title });
      const results = response.data?.results || [];
      const match =
        results.find(
          (r) =>
            r.title?.replace(/\s+/g, '').toLowerCase() ===
            title.replace(/\s+/g, '').toLowerCase()
        ) || results[0];
      if (match) {
        window.dispatchEvent(
          new CustomEvent('knowledge-open-file', {
            detail: {
              path: match.path,
              name: match.path.split('/').pop(),
              is_directory: false,
            },
          })
        );
      } else {
        message.warning(`未找到笔记: ${title}`);
      }
    } catch (err) {
      console.error('Wiki link resolve failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <span
      onClick={handleClick}
      style={{
        color: 'var(--accent)',
        cursor: loading ? 'wait' : 'pointer',
        textDecoration: 'underline',
        opacity: loading ? 0.6 : 1,
      }}
      title={`打开: ${title}`}
    >
      {children}
    </span>
  );
}

/**
 * Markdown 预览组件
 */
const MarkdownPreview = ({ content, file, sendWSMessage }) => {
  const safeContent = typeof content === 'string' ? content : '';
  const processed = preprocessWikiLinks(safeContent);
  return (
    <div className="markdown-preview">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: (props) => {
            if (props.href?.startsWith('wiki://')) {
              return (
                <WikiLink href={props.href} sendWSMessage={sendWSMessage}>
                  {props.children}
                </WikiLink>
              );
            }
            return <a {...props} />;
          },
        }}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
};

/**
 * 预览抽屉组件
 * 从右侧滑出的文件预览面板
 */
export default function PreviewDrawer({
  file,
  content,
  isOpen,
  onClose,
  sendWSMessage,
}) {
  const [isPreviewMode, setIsPreviewMode] = useState(true);

  // 当文件变化时，重置为预览模式
  useEffect(() => {
    setIsPreviewMode(true);
  }, [file?.path]);

  if (!isOpen || !file) return null;

  const fileName = file.name || '';
  const displayName = file.meta?.title || fileName;
  const fileExt = fileName.split('.').pop()?.toLowerCase() || '';
  const sourceUrl = file.meta?.source;
  const isWebPreview = sourceUrl && typeof sourceUrl === 'string' && sourceUrl.startsWith('http');
  
  // 判断文件类型
  const isImage = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(fileExt);
  const isPdf = fileExt === 'pdf';
  const isExcel = ['xlsx', 'xls'].includes(fileExt);
  const isPptx = ['pptx', 'ppt'].includes(fileExt);
  const isDocx = ['docx', 'doc'].includes(fileExt);
  const isHtml = ['html', 'htm'].includes(fileExt);
  const isMarkdown = ['md', 'markdown'].includes(fileExt);
  const isText = ['txt', 'json', 'xml', 'yaml', 'yml', 'csv', 'log', 'js', 'jsx', 'ts', 'tsx', 'py', 'java', 'cpp', 'c', 'go', 'rs', 'php', 'rb'].includes(fileExt);
  const isBinary = !isImage && !isPdf && !isExcel && !isPptx && !isDocx && !isHtml && !isMarkdown && !isText;

  const language = getLanguage(fileName);
  const safeContent = typeof content === 'string' ? content : '';

  // 渲染网页预览（Electron webview）
  const renderWebPreview = () => {
    const isElectron = typeof navigator !== 'undefined' && navigator.userAgent.includes('Electron');
    if (!isElectron) {
      return (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-2)' }}>
          <p style={{ marginBottom: 16 }}>网页预览需要在 Electron 环境中运行</p>
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--accent)', textDecoration: 'none' }}
          >
            在外部浏览器打开
          </a>
        </div>
      );
    }
    return (
      <webview
        src={sourceUrl}
        style={{ width: '100%', height: '100%', border: 'none' }}
        allowpopups="on"
      />
    );
  };

  // 渲染预览内容
  const renderPreview = () => {
    if (isWebPreview) {
      return renderWebPreview();
    }
    if (isImage) {
      return <ImageViewer file={file} content={content} fileExt={fileExt} />;
    }
    if (isPdf) {
      return <PdfViewer file={file} content={content} />;
    }
    if (isExcel) {
      return <XlsxViewer file={file} content={content} />;
    }
    if (isPptx) {
      return <PptxViewer file={file} content={content} />;
    }
    if (isDocx) {
      return <DocxViewer file={file} content={content} />;
    }
    if (isHtml) {
      return <HtmlViewer content={safeContent} />;
    }
    if (isMarkdown && isPreviewMode) {
      return <MarkdownPreview content={safeContent} file={file} sendWSMessage={sendWSMessage} />;
    }
    if (isBinary) {
      return <BinaryViewer file={file} content={content} />;
    }
    
    // 默认使用编辑器显示
    return (
      <Editor
        height="100%"
        language={language}
        value={safeContent}
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
          readOnly: true,
        }}
        theme="vs-dark"
      />
    );
  };

  return (
    <>
      {/* 遮罩层 */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          zIndex: 1000,
          opacity: isOpen ? 1 : 0,
          visibility: isOpen ? 'visible' : 'hidden',
          transition: 'opacity 0.3s ease, visibility 0.3s ease',
        }}
        onClick={onClose}
      />
      
      {/* 抽屉面板 */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: '80%',
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          zIndex: 1001,
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.3s ease',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '-4px 0 24px rgba(0, 0, 0, 0.15)',
        }}
      >
        {/* 头部 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '10px 14px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--surface)',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, overflow: 'hidden', flex: 1 }}>
            <div style={{ flexShrink: 0 }}>
              <FileIcon name={fileName} isDirectory={false} size={36} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--text)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  lineHeight: 1.4,
                }}
                title={fileName}
              >
                {displayName}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: 'var(--text-3)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  lineHeight: 1.3,
                }}
                title={isWebPreview ? sourceUrl : file.path}
              >
                {isWebPreview
                  ? new URL(sourceUrl).hostname
                  : file.path}
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            {/* 外部打开按钮 - 仅对 web preview 显示 */}
            {isWebPreview && (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  background: 'var(--surface-2)',
                  color: 'var(--text-2)',
                  cursor: 'pointer',
                  fontSize: 12,
                  textDecoration: 'none',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--accent-soft)';
                  e.currentTarget.style.color = 'var(--accent)';
                  e.currentTarget.style.borderColor = 'var(--accent)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--surface-2)';
                  e.currentTarget.style.color = 'var(--text-2)';
                  e.currentTarget.style.borderColor = 'var(--border)';
                }}
                title="在外部浏览器打开"
              >
                <ExternalLink size={13} />
                <span>打开</span>
              </a>
            )}

            {/* 预览/编辑切换按钮 - 仅对 Markdown 和文本文件显示 */}
            {(isMarkdown || isText) && (
              <button
                onClick={() => setIsPreviewMode(!isPreviewMode)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  background: 'var(--surface-2)',
                  color: 'var(--text-2)',
                  cursor: 'pointer',
                  fontSize: 12,
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--accent-soft)';
                  e.currentTarget.style.color = 'var(--accent)';
                  e.currentTarget.style.borderColor = 'var(--accent)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--surface-2)';
                  e.currentTarget.style.color = 'var(--text-2)';
                  e.currentTarget.style.borderColor = 'var(--border)';
                }}
              >
                {isPreviewMode ? <Edit3 size={13} /> : <Eye size={13} />}
                <span>{isPreviewMode ? '编辑' : '预览'}</span>
              </button>
            )}

            <div style={{ width: 1, height: 20, background: 'var(--border)', margin: '0 4px' }} />

            <button
              onClick={onClose}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 28,
                height: 28,
                borderRadius: 6,
                border: 'none',
                background: 'transparent',
                color: 'var(--text-2)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(255, 107, 107, 0.12)';
                e.currentTarget.style.color = '#FF6B6B';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = 'var(--text-2)';
              }}
            >
              <X size={16} />
            </button>
          </div>
        </div>
        
        {/* 预览内容区域 */}
        <div
          style={{
            flex: 1,
            overflow: 'hidden',
            minHeight: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {renderPreview()}
        </div>
      </div>
    </>
  );
}
