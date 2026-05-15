import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Eye, Code, Download, FileCode, FileImage, Copy, Check,
} from 'lucide-react';
import { useMermaid } from '../../hooks/useMermaid';
import './MermaidDiagram.css';

let idCounter = 0;
function getUniqueId() {
  idCounter += 1;
  return `mermaid-diagram-${idCounter}-${Date.now()}`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function downloadSvg(svgElement, filename = 'diagram.svg') {
  const svgData = new XMLSerializer().serializeToString(svgElement);
  const blob = new Blob([svgData], { type: 'image/svg+xml' });
  downloadBlob(blob, filename);
}

async function downloadPng(svgElement, filename = 'diagram.png') {
  const svgData = new XMLSerializer().serializeToString(svgElement);
  const encoder = new TextEncoder();
  const encoded = encoder.encode(svgData);
  const binary = Array.from(encoded, (b) => String.fromCodePoint(b)).join('');
  const svgBase64 = `data:image/svg+xml;base64,${btoa(binary)}`;

  const img = new Image();
  await new Promise((resolve, reject) => {
    img.onload = resolve;
    img.onerror = () => reject(new Error('Failed to load SVG image'));
    img.src = svgBase64;
  });

  const viewBox = svgElement.getAttribute('viewBox')?.split(' ').map(Number) || [];
  const rect = svgElement.getBoundingClientRect();
  const width = viewBox[2] || rect.width || img.naturalWidth || 800;
  const height = viewBox[3] || rect.height || img.naturalHeight || 600;

  const scale = 3;
  const canvas = document.createElement('canvas');
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext('2d');
  ctx.scale(scale, scale);
  ctx.drawImage(img, 0, 0, width, height);

  const blob = await new Promise((resolve) => {
    canvas.toBlob((b) => resolve(b), 'image/png');
  });
  if (blob) downloadBlob(blob, filename);
}

export default function MermaidDiagram({ source }) {
  const { mermaid, isLoading: isMermaidLoading, error: mermaidError } = useMermaid();
  const containerRef = useRef(null);
  const [svgContent, setSvgContent] = useState(null);
  const [renderError, setRenderError] = useState(null);
  const [viewMode, setViewMode] = useState('diagram'); // 'diagram' | 'code'
  const [copied, setCopied] = useState(false);
  const diagramId = useRef(getUniqueId()).current;

  useEffect(() => {
    if (!mermaid || !source) return;

    let cancelled = false;
    setRenderError(null);
    setSvgContent(null);

    const render = async () => {
      try {
        const result = await mermaid.render(diagramId, source);
        if (cancelled) return;

        const svg = typeof result === 'string' ? result : result?.svg;
        if (!svg) {
          throw new Error('Mermaid returned empty SVG');
        }

        const fixedSvg = svg.replace(/translate\(undefined,\s*NaN\)/g, 'translate(0, 0)');
        setSvgContent(fixedSvg);
      } catch (err) {
        if (cancelled) return;
        console.error('[MermaidDiagram] render error:', err);
        setRenderError(err instanceof Error ? err.message : 'Render error');
      }
    };

    const timer = setTimeout(render, 50);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [mermaid, source, diagramId]);

  const handleDownloadSvg = useCallback(() => {
    const svgEl = containerRef.current?.querySelector('svg');
    if (svgEl) downloadSvg(svgEl);
  }, []);

  const handleDownloadPng = useCallback(async () => {
    const svgEl = containerRef.current?.querySelector('svg');
    if (svgEl) {
      try {
        await downloadPng(svgEl);
      } catch (err) {
        console.error('PNG download failed:', err);
      }
    }
  }, []);

  const handleCopyCode = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  }, [source]);

  const error = mermaidError || renderError;

  if (isMermaidLoading) {
    return (
      <div className="mermaid-diagram-loading">
        <span className="mermaid-spinner" />
        <span>正在加载 Mermaid…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mermaid-diagram-error">
        <div className="mermaid-error-title">⚠️ Mermaid 渲染失败</div>
        <div className="mermaid-error-msg">{error}</div>
        <pre className="mermaid-error-source">{source}</pre>
      </div>
    );
  }

  return (
    <div className="mermaid-diagram-wrapper">
      {/* Toolbar */}
      <div className="mermaid-toolbar">
        <div className="mermaid-toolbar-group">
          <button
            type="button"
            className={`mermaid-toolbar-btn ${viewMode === 'diagram' ? 'active' : ''}`}
            onClick={() => setViewMode('diagram')}
            title="查看图表"
          >
            <Eye size={14} />
            <span>图表</span>
          </button>
          <button
            type="button"
            className={`mermaid-toolbar-btn ${viewMode === 'code' ? 'active' : ''}`}
            onClick={() => setViewMode('code')}
            title="查看代码"
          >
            <Code size={14} />
            <span>代码</span>
          </button>
        </div>

        {viewMode === 'diagram' && svgContent && (
          <div className="mermaid-toolbar-group">
            <button
              type="button"
              className="mermaid-toolbar-btn"
              onClick={handleDownloadSvg}
              title="下载 SVG"
            >
              <FileCode size={14} />
              <span>SVG</span>
            </button>
            <button
              type="button"
              className="mermaid-toolbar-btn"
              onClick={handleDownloadPng}
              title="下载 PNG"
            >
              <FileImage size={14} />
              <span>PNG</span>
            </button>
          </div>
        )}

        {viewMode === 'code' && (
          <button
            type="button"
            className="mermaid-toolbar-btn"
            onClick={handleCopyCode}
            title="复制代码"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            <span>{copied ? '已复制' : '复制'}</span>
          </button>
        )}
      </div>

      {/* Content */}
      {viewMode === 'diagram' ? (
        svgContent ? (
          <div
            ref={containerRef}
            className="mermaid-diagram-container"
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        ) : (
          <div className="mermaid-diagram-loading-inline">
            <span className="mermaid-spinner" />
            <span>正在渲染图表…</span>
          </div>
        )
      ) : (
        <div className="mermaid-code-view">
          <pre><code>{source}</code></pre>
        </div>
      )}
    </div>
  );
}
