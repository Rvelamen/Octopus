import React, { useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { looksLikeWorkspaceFilePath } from '@pages/Chat/ChatPanel/utils/workspacePathUtils';

/**
 * Shared hook for rendering message content with ReactMarkdown.
 * Returns render function + workspace preview state for clickable paths.
 */
export function useMessageRenderer() {
  const [workspacePreviewPath, setWorkspacePreviewPath] = useState(null);

  const renderMessageContent = useCallback((content) => {
    if (!content) return null;
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="md-link"
            >
              {children}
            </a>
          ),
          p({ children }) {
            const hasBlock = React.Children.toArray(children).some((child) => {
              if (typeof child === 'object' && child?.type) {
                const tag = typeof child.type === 'string' ? child.type : child.type?.name;
                if (['pre', 'div', 'table', 'ul', 'ol', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) {
                  return true;
                }
                if (tag === 'code' && child.props?.inline === false) {
                  return true;
                }
              }
              return false;
            });
            if (hasBlock) {
              return <div className="md-paragraph">{children}</div>;
            }
            return <p>{children}</p>;
          },
          code({ inline, className, children, ...props }) {
            if (inline) {
              const inlineText = String(children).trim();
              if (looksLikeWorkspaceFilePath(inlineText)) {
                return (
                  <button
                    type="button"
                    className="md-inline-workspace-path"
                    onClick={() => setWorkspacePreviewPath(inlineText)}
                    title="点击预览工作区文件"
                  >
                    {inlineText}
                  </button>
                );
              }
              return (
                <code className="md-inline-code" {...props}>
                  {children}
                </code>
              );
            }
            const text = String(children).replace(/\n$/, '').trim();
            if (looksLikeWorkspaceFilePath(text)) {
              return (
                <button
                  type="button"
                  className="md-code-block md-workspace-path-btn"
                  onClick={() => setWorkspacePreviewPath(text)}
                  title="点击预览工作区文件"
                >
                  <pre {...props}>
                    <code className={className}>{children}</code>
                  </pre>
                </button>
              );
            }
            return (
              <div className="md-code-block">
                <pre {...props}>
                  <code className={className}>{children}</code>
                </pre>
              </div>
            );
          },
          pre({ children }) {
            return <>{children}</>;
          },
          table({ children }) {
            return (
              <div className="md-table-wrapper">
                <table className="md-table">{children}</table>
              </div>
            );
          }
        }}
      >
        {content}
      </ReactMarkdown>
    );
  }, []);

  const renderPlainContent = useCallback((content) => {
    if (!content) return null;
    return <span className="plain-text-content">{content}</span>;
  }, []);

  return {
    renderMessageContent,
    renderPlainContent,
    workspacePreviewPath,
    setWorkspacePreviewPath,
  };
}
