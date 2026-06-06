import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Markmap } from 'markmap-view';
import { Transformer } from 'markmap-lib';
import {
  Eye, Code, FileCode, FileImage, Copy, Check, X, Maximize2, RotateCcw,
  MoreHorizontal,
} from 'lucide-react';
import './MindmapDiagram.css';

const transformer = new Transformer();

function cleanSource(source) {
  return String(source || '').replace(/```[a-zA-Z]*\n?|```/g, '').trim();
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

function serializeSvg(svgElement) {
  const clone = svgElement.cloneNode(true);
  if (!clone.getAttribute('viewBox')) {
    const rect = svgElement.getBoundingClientRect();
    clone.setAttribute('viewBox', `0 0 ${rect.width || 800} ${rect.height || 600}`);
  }
  if (!clone.getAttribute('xmlns')) {
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  }
  const svgData = new XMLSerializer().serializeToString(clone);
  return svgData;
}

function downloadSvg(svgElement, filename = 'mindmap.svg') {
  const svgData = serializeSvg(svgElement);
  const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
  downloadBlob(blob, filename);
}

async function downloadPng(svgElement, filename = 'mindmap.png') {
  const svgData = serializeSvg(svgElement);
  const rect = svgElement.getBoundingClientRect();
  const width = rect.width || 1200;
  const height = rect.height || 800;
  const svgBase64 = `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svgData)))}`;

  const img = new Image();
  await new Promise((resolve, reject) => {
    img.onload = resolve;
    img.onerror = () => reject(new Error('Failed to load SVG image'));
    img.src = svgBase64;
  });

  const scale = 2;
  const canvas = document.createElement('canvas');
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.scale(scale, scale);
  ctx.drawImage(img, 0, 0, width, height);

  const blob = await new Promise((resolve) => {
    canvas.toBlob((b) => resolve(b), 'image/png');
  });
  if (blob) downloadBlob(blob, filename);
}

// 自定义颜色：按深度分配柔和色系
const LEVEL_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

function getColor(node) {
  const depth = node.state?.depth ?? 0;
  return LEVEL_COLORS[depth % LEVEL_COLORS.length];
}

export default function MindmapDiagram({ source }) {
  const svgRef = useRef(null);
  const fsSvgRef = useRef(null);
  const mmRef = useRef(null);
  const fsMmRef = useRef(null);
  const toolbarRef = useRef(null);
  const [viewMode, setViewMode] = useState('diagram'); // 'diagram' | 'code'
  const [copied, setCopied] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState(null);
  const [toolbarMode, setToolbarMode] = useState('full'); // 'full' | 'icon' | 'menu'
  const [menuOpen, setMenuOpen] = useState(false);

  // ESC 退出全屏
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isFullscreen]);

  // Toolbar 响应式：根据宽度切换显示模式
  useEffect(() => {
    const toolbar = toolbarRef.current;
    if (!toolbar) return;
    const check = () => {
      const width = toolbar.getBoundingClientRect().width;
      if (width < 260) setToolbarMode('menu');
      else if (width < 400) setToolbarMode('icon');
      else setToolbarMode('full');
    };
    check();
    const ro = new ResizeObserver(check);
    ro.observe(toolbar);
    return () => ro.disconnect();
  }, [viewMode]);

  // 点击外部关闭菜单
  useEffect(() => {
    if (!menuOpen) return;
    const handleClick = (e) => {
      if (!e.target.closest('.mindmap-toolbar-overflow')) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [menuOpen]);

  const renderMarkmap = useCallback((svgEl, mmInstanceRef) => {
    if (!svgEl) return;
    try {
      const text = cleanSource(source);
      if (!text) {
        setError('大纲内容为空');
        return;
      }
      const { root } = transformer.transform(text);
      if (!root) {
        setError('未能解析出有效的思维导图结构');
        return;
      }
      setError(null);

      if (!mmInstanceRef.current) {
        mmInstanceRef.current = Markmap.create(svgEl, {
          autoFit: false,
          duration: 300,
          embedGlobalCSS: true,
          fitRatio: 0.9,
          initialExpandLevel: -1,
          maxInitialScale: 2,
          pan: true,
          zoom: true,
          toggleRecursively: true,
          color: getColor,
          maxWidth: 240,
          spacingHorizontal: 80,
          spacingVertical: 10,
        });
      }

      mmInstanceRef.current.setData(root).then(() => {
        mmInstanceRef.current.fit();
      });
    } catch (e) {
      setError(e.message || '渲染失败');
    }
  }, [source]);

  // 非全屏渲染
  useEffect(() => {
    if (viewMode === 'diagram' && !isFullscreen) {
      // 延迟确保 SVG 已挂载
      const timer = setTimeout(() => {
        renderMarkmap(svgRef.current, mmRef);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [source, viewMode, isFullscreen, renderMarkmap]);

  // 全屏渲染
  useEffect(() => {
    if (isFullscreen && viewMode === 'diagram') {
      const timer = setTimeout(() => {
        renderMarkmap(fsSvgRef.current, fsMmRef);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isFullscreen, viewMode, renderMarkmap]);

  // 销毁
  useEffect(() => {
    return () => {
      mmRef.current?.destroy();
      fsMmRef.current?.destroy();
    };
  }, []);

  const handleFit = useCallback(() => {
    mmRef.current?.fit();
  }, []);

  const handleFsFit = useCallback(() => {
    fsMmRef.current?.fit();
  }, []);

  const handleDownloadSvg = useCallback(() => {
    if (svgRef.current) downloadSvg(svgRef.current);
  }, []);

  const handleFsDownloadSvg = useCallback(() => {
    if (fsSvgRef.current) downloadSvg(fsSvgRef.current);
  }, []);

  const handleDownloadPng = useCallback(async () => {
    if (!svgRef.current) return;
    try { await downloadPng(svgRef.current); } catch (err) { console.error('PNG download failed:', err); }
  }, []);

  const handleFsDownloadPng = useCallback(async () => {
    if (!fsSvgRef.current) return;
    try { await downloadPng(fsSvgRef.current); } catch (err) { console.error('PNG download failed:', err); }
  }, []);

  const handleCopyCode = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) { console.error('Copy failed:', err); }
  }, [source]);

  // 全屏视图
  if (isFullscreen && viewMode === 'diagram' && !error) {
    return (
      <div
        className="mindmap-fullscreen-overlay"
        onClick={(e) => {
          if (e.target === e.currentTarget) setIsFullscreen(false);
        }}
      >
        <button
          type="button"
          className="mindmap-fullscreen-close"
          onClick={() => setIsFullscreen(false)}
          title="关闭预览"
        >
          <X size={20} />
        </button>

        <div className="mindmap-zoom-toolbar">
          <button type="button" onClick={handleFsFit} title="适配窗口">
            <RotateCcw size={16} />
          </button>
          <button type="button" onClick={handleFsDownloadSvg} title="下载 SVG">
            <FileCode size={16} />
          </button>
          <button type="button" onClick={handleFsDownloadPng} title="下载 PNG">
            <FileImage size={16} />
          </button>
        </div>

        <div className="mindmap-fs-wrapper">
          <svg ref={fsSvgRef} className="mindmap-svg" />
        </div>
      </div>
    );
  }

  return (
    <div className="mindmap-diagram-wrapper">
      {/* Toolbar */}
      <div className="mindmap-toolbar" ref={toolbarRef}>
        <div className="mindmap-toolbar-group">
          <button
            type="button"
            className={`mindmap-toolbar-btn ${viewMode === 'diagram' ? 'active' : ''}`}
            onClick={() => setViewMode('diagram')}
            title="查看图表"
          >
            <Eye size={14} />
            {toolbarMode !== 'icon' && <span>图表</span>}
          </button>
          <button
            type="button"
            className={`mindmap-toolbar-btn ${viewMode === 'code' ? 'active' : ''}`}
            onClick={() => setViewMode('code')}
            title="查看代码"
          >
            <Code size={14} />
            {toolbarMode !== 'icon' && <span>代码</span>}
          </button>
        </div>

        {viewMode === 'diagram' && !error && toolbarMode !== 'menu' && (
          <div className="mindmap-toolbar-group">
            <button
              type="button"
              className="mindmap-toolbar-btn"
              onClick={() => setIsFullscreen(true)}
              title="全屏预览"
            >
              <Maximize2 size={14} />
              {toolbarMode === 'full' && <span>全屏</span>}
            </button>
            <button
              type="button"
              className="mindmap-toolbar-btn"
              onClick={handleFit}
              title="适配窗口"
            >
              <RotateCcw size={14} />
              {toolbarMode === 'full' && <span>适配</span>}
            </button>
            <button
              type="button"
              className="mindmap-toolbar-btn"
              onClick={handleDownloadSvg}
              title="下载 SVG"
            >
              <FileCode size={14} />
              {toolbarMode === 'full' && <span>SVG</span>}
            </button>
            <button
              type="button"
              className="mindmap-toolbar-btn"
              onClick={handleDownloadPng}
              title="下载 PNG"
            >
              <FileImage size={14} />
              {toolbarMode === 'full' && <span>PNG</span>}
            </button>
          </div>
        )}

        {viewMode === 'diagram' && !error && toolbarMode === 'menu' && (
          <div className="mindmap-toolbar-group mindmap-toolbar-overflow">
            <button
              type="button"
              className="mindmap-toolbar-btn"
              onClick={() => setMenuOpen((v) => !v)}
              title="更多操作"
            >
              <MoreHorizontal size={14} />
            </button>
            {menuOpen && (
              <div className="mindmap-toolbar-menu">
                <button type="button" onClick={() => { setIsFullscreen(true); setMenuOpen(false); }}>
                  <Maximize2 size={14} /><span>全屏预览</span>
                </button>
                <button type="button" onClick={() => { handleFit(); setMenuOpen(false); }}>
                  <RotateCcw size={14} /><span>适配窗口</span>
                </button>
                <button type="button" onClick={() => { handleDownloadSvg(); setMenuOpen(false); }}>
                  <FileCode size={14} /><span>下载 SVG</span>
                </button>
                <button type="button" onClick={() => { handleDownloadPng(); setMenuOpen(false); }}>
                  <FileImage size={14} /><span>下载 PNG</span>
                </button>
              </div>
            )}
          </div>
        )}

        {viewMode === 'code' && (
          <button
            type="button"
            className="mindmap-toolbar-btn"
            onClick={handleCopyCode}
            title="复制代码"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {toolbarMode !== 'icon' && <span>{copied ? '已复制' : '复制'}</span>}
          </button>
        )}
      </div>

      {/* Content */}
      {viewMode === 'diagram' ? (
        error ? (
          <div className="mindmap-diagram-error">
            <div className="mindmap-error-title">⚠️ 思维导图解析失败</div>
            <div className="mindmap-error-msg">{error}</div>
            <pre className="mindmap-error-source">{source}</pre>
          </div>
        ) : (
          <div
            className="mindmap-diagram-container"
            style={{ height: 600, position: 'relative' }}
          >
            <svg ref={svgRef} className="mindmap-svg" />
            <button
              type="button"
              className="mindmap-diagram-zoom-hint"
              onClick={() => setIsFullscreen(true)}
              title="全屏预览"
            >
              <Maximize2 size={14} />
              <span>全屏预览</span>
            </button>
          </div>
        )
      ) : (
        <div className="mindmap-code-view">
          <pre><code>{source}</code></pre>
        </div>
      )}
    </div>
  );
}
