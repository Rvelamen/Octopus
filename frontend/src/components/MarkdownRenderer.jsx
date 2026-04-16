import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { uriTransformer } from 'react-markdown/lib/uri-transformer';
import remarkGfm from 'remark-gfm';

const WIKI_LINK_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;

function preprocessWikiLinks(content) {
  return content.replace(WIKI_LINK_RE, (match, title, alias) => {
    const cleanTitle = (title || '').replace(/\\$/, '').trim();
    const display = (alias || cleanTitle).trim();
    return `[${display}](wiki://${encodeURIComponent(cleanTitle)})`;
  });
}

function WikiLink({ href, children, sendWSMessage }) {
  const title = decodeURIComponent(href.replace('wiki://', ''));
  const [loading, setLoading] = useState(false);

  const handleClick = async (e) => {
    e.preventDefault();
    if (loading || !sendWSMessage) return;
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
        // eslint-disable-next-line no-console
        console.warn(`未找到笔记: ${title}`);
      }
    } catch (err) {
      // eslint-disable-next-line no-console
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

function parseFrontmatter(content) {
  if (typeof content !== 'string') return { frontmatter: null, body: content || '' };
  const match = content.match(/^---\s*\n([\s\S]*?)\n---\s*\n?/);
  if (!match) return { frontmatter: null, body: content };
  try {
    const yamlText = match[1];
    const result = {};
    yamlText.split('\n').forEach((line) => {
      const idx = line.indexOf(':');
      if (idx > 0) {
        const key = line.slice(0, idx).trim();
        let value = line.slice(idx + 1).trim();
        if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
          value = value.slice(1, -1);
        }
        result[key] = value;
      }
    });
    return { frontmatter: result, body: content.slice(match[0].length) };
  } catch {
    return { frontmatter: null, body: content };
  }
}

function isExternalUrl(value) {
  return typeof value === 'string' && /^https?:\/\//i.test(value);
}

function isWorkspacePath(value) {
  return typeof value === 'string' && (value.startsWith('knowledge/') || value.startsWith('workspace/'));
}

function FrontmatterLink({ value }) {
  if (isExternalUrl(value)) {
    return (
      <a
        href={value}
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: 'var(--accent)', textDecoration: 'underline' }}
      >
        {value}
      </a>
    );
  }
  if (isWorkspacePath(value)) {
    const handleClick = (e) => {
      e.preventDefault();
      window.dispatchEvent(
        new CustomEvent('knowledge-open-file', {
          detail: { path: value, name: value.split('/').pop(), is_directory: false },
        })
      );
    };
    return (
      <span
        onClick={handleClick}
        style={{ color: 'var(--accent)', textDecoration: 'underline', cursor: 'pointer' }}
        title="点击打开文件"
      >
        {value}
      </span>
    );
  }
  return <span>{value}</span>;
}

function FrontmatterCard({ data }) {
  const clickableKeys = ['source', 'archive', 'pdf_path', 'url', 'link', 'href'];
  const entries = Object.entries(data).filter(([_, v]) => v !== undefined && v !== null && v !== '');
  if (entries.length === 0) return null;
  return (
    <div
      style={{
        margin: '16px 16px 8px',
        padding: '12px 14px',
        background: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        fontSize: 12,
        lineHeight: 1.5,
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--text-2)',
          marginBottom: 8,
          textTransform: 'uppercase',
          letterSpacing: 0.5,
        }}
      >
        Metadata
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {entries.map(([key, value]) => {
          const isClickable = clickableKeys.includes(key);
          return (
            <div key={key} style={{ display: 'flex', gap: 8 }}>
              <span style={{ color: 'var(--text-3)', minWidth: 100, flexShrink: 0 }}>{key}</span>
              <span style={{ color: 'var(--text)', wordBreak: 'break-all' }}>
                {isClickable ? <FrontmatterLink value={value} /> : String(value)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * 统一的 Markdown 渲染组件
 * - 自动解析 frontmatter 并渲染成可点击的 Metadata 卡片
 * - 支持 [[WikiLink]] 语法
 * - 基于 react-markdown + remark-gfm
 */
export default function MarkdownRenderer({ content, sendWSMessage }) {
  const safeContent = typeof content === 'string' ? content : '';
  if (!safeContent.trim()) {
    return (
      <div className="markdown-preview" style={{ padding: 24, color: 'var(--text-2)', textAlign: 'center' }}>
        No content to preview
      </div>
    );
  }
  const { frontmatter, body } = parseFrontmatter(safeContent);
  const processed = preprocessWikiLinks(body);

  return (
    <div
      className="markdown-preview"
      style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'auto' }}
    >
      {frontmatter && <FrontmatterCard data={frontmatter} />}
      <div style={{ flex: 1, padding: '0 16px 16px' }}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          transformLinkUri={(href) => {
            if (href.startsWith('wiki://')) return href;
            return uriTransformer(href);
          }}
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
    </div>
  );
}
