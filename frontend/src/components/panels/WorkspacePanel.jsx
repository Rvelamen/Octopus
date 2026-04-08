import React, { useState, useEffect, useLayoutEffect, useCallback, useRef, useMemo } from 'react';
import {
  Folder, File, ChevronRight, ChevronDown, Home,
  RefreshCw, Plus, Trash2, Edit3, Save, X, FolderPlus,
  FilePlus, ArrowLeft, Search, FileText, Image, Code,
  MoreVertical, Download, Upload
} from 'lucide-react';
import { Modal, Input, Button, Dropdown, Menu, message, Table } from 'antd';
import Editor from '@monaco-editor/react';
import * as XLSX from 'xlsx';
import * as mammoth from 'mammoth';
import JSZip from 'jszip';
import { Document, Page, pdfjs } from 'react-pdf';
import WindowDots from '../WindowDots';

// 设置 pdf.js worker - 使用 jsdelivr CDN
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

/**
 * File Icon Component - Returns appropriate icon based on file type
 */
const FileIcon = ({ name, type, size = 16 }) => {
  if (type === 'directory') {
    return <Folder size={size} className="file-icon folder" />;
  }

  const ext = name.split('.').pop()?.toLowerCase();

  // Image files
  if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(ext)) {
    return <Image size={size} className="file-icon image" />;
  }

  // Code files
  if (['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'cpp', 'c', 'h', 'go', 'rs', 'php', 'rb'].includes(ext)) {
    return <Code size={size} className="file-icon code" />;
  }

  // Text files
  if (['txt', 'md', 'json', 'xml', 'yaml', 'yml', 'csv', 'log'].includes(ext)) {
    return <FileText size={size} className="file-icon text" />;
  }

  return <File size={size} className="file-icon" />;
};

/**
 * Format file size
 */
const formatSize = (bytes) => {
  if (bytes === null || bytes === undefined) return '-';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

/**
 * Format date
 */
const formatDate = (timestamp) => {
  if (!timestamp) return '-';
  return new Date(timestamp * 1000).toLocaleString();
};

/**
 * Tree Node Component
 */
const TreeNode = ({
  item,
  level = 0,
  selectedPath,
  expandedPaths,
  onSelect,
  onToggle,
  onContextMenu,
  treeItems
}) => {
  const isExpanded = expandedPaths.has(item.path);
  const isSelected = selectedPath === item.path;
  // 获取所有子项（文件和目录）
  const allChildren = treeItems?.[item.path] || [];
  const hasChildren = item.type === 'directory' && allChildren.length > 0;

  // 如果是文件，直接渲染文件节点
  if (item.type === 'file') {
    return (
      <div className="tree-node-container">
        <div
          className={`tree-node ${isSelected ? 'selected' : ''}`}
          style={{ paddingLeft: `${level * 16 + 8}px` }}
          onClick={() => onSelect(item)}
          onContextMenu={(e) => onContextMenu(e, item)}
        >
          <span className="tree-toggle" />
          <FileIcon name={item.name} type={item.type} size={16} />
          <span className="tree-node-name" title={item.name}>{item.name}</span>
        </div>
      </div>
    );
  }

  // 目录节点
  return (
    <div className="tree-node-container">
      <div
        className={`tree-node ${isSelected ? 'selected' : ''}`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={() => onSelect(item)}
        onContextMenu={(e) => onContextMenu(e, item)}
      >
        <span
          className="tree-toggle"
          onClick={(e) => {
            e.stopPropagation();
            onToggle(item.path);
          }}
        >
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <FileIcon name={item.name} type={item.type} size={16} />
        <span className="tree-node-name" title={item.name}>{item.name}</span>
      </div>
      {isExpanded && hasChildren && (
        <div className="tree-children">
          {allChildren.map((child) => (
            <TreeNode
              key={child.path}
              item={child}
              level={level + 1}
              selectedPath={selectedPath}
              expandedPaths={expandedPaths}
              onSelect={onSelect}
              onToggle={onToggle}
              onContextMenu={onContextMenu}
              treeItems={treeItems}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * Convert hex string to base64
 */
const hexToBase64 = (hex) => {
  if (!hex) return '';
  try {
    const bytes = new Uint8Array(hex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    const binary = bytes.reduce((acc, byte) => acc + String.fromCharCode(byte), '');
    return btoa(binary);
  } catch (e) {
    console.error('Failed to convert hex to base64:', e);
    return '';
  }
};

/**
 * Image Viewer Component
 */
const ImageViewer = ({ file, content, fileExt }) => {
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [imageUrl, setImageUrl] = useState(null);

  useEffect(() => {
    try {
      let byteArray;
      if (file.encoding === 'hex') {
        const hexString = content.replace(/\s/g, '');
        byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
      } else {
        const binaryData = atob(content);
        byteArray = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
          byteArray[i] = binaryData.charCodeAt(i);
        }
      }
      
      const mimeType = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'svg': 'image/svg+xml',
        'webp': 'image/webp'
      }[fileExt] || 'image/png';
      
      const blob = new Blob([byteArray], { type: mimeType });
      const url = URL.createObjectURL(blob);
      setImageUrl(url);
      
      return () => {
        URL.revokeObjectURL(url);
      };
    } catch (err) {
      console.error('Failed to load image:', err);
      setError(true);
      setLoading(false);
    }
  }, [content, file.encoding, fileExt]);

  if (error) {
    return (
      <div className="image-preview error">
        <Image size={48} />
        <p>Unable to preview image</p>
        <p style={{ fontSize: '12px', color: '#666' }}>{file.name}</p>
      </div>
    );
  }

  return (
    <div className="image-preview">
      {loading && (
        <div className="image-loading">
          <RefreshCw size={24} className="spin" />
          <p>Loading image...</p>
        </div>
      )}
      {imageUrl && (
        <img
          src={imageUrl}
          alt={file.name}
          style={{ display: loading ? 'none' : 'block', maxWidth: '100%', maxHeight: '100%' }}
          onLoad={() => setLoading(false)}
          onError={() => {
            setLoading(false);
            setError(true);
          }}
        />
      )}
    </div>
  );
};

/**
 * XLSX Viewer Component
 */
const XlsxViewer = ({ file, content }) => {
  const [data, setData] = useState([]);
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    try {
      console.log('XlsxViewer - file.encoding:', file.encoding, 'content length:', content?.length);
      
      // 将 hex 直接转换为 Uint8Array
      let byteArray;
      if (file.encoding === 'hex') {
        const hexString = content.replace(/\s/g, ''); // 移除空白字符
        console.log('Parsing hex string, length:', hexString.length);
        byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
      } else if (file.encoding === 'base64') {
        // 如果是 base64 编码
        console.log('Parsing base64 content');
        const binaryData = atob(content);
        byteArray = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
          byteArray[i] = binaryData.charCodeAt(i);
        }
      } else {
        // 未知编码，尝试直接作为文本处理
        console.log('Unknown encoding, trying to parse as text');
        byteArray = new TextEncoder().encode(content);
      }
      
      console.log('Byte array length:', byteArray.length);
      const workbook = XLSX.read(byteArray, { type: 'array' });
      
      // 获取第一个工作表
      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];
      
      // 转换为 JSON
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
      
      if (jsonData.length > 0) {
        // 第一行作为表头
        const headers = jsonData[0];
        const cols = headers.map((header, index) => ({
          title: header || `Column ${index + 1}`,
          dataIndex: `col${index}`,
          key: `col${index}`,
          ellipsis: true,
        }));
        
        // 数据行
        const rows = jsonData.slice(1).map((row, rowIndex) => {
          const rowData = { key: rowIndex };
          headers.forEach((_, colIndex) => {
            rowData[`col${colIndex}`] = row[colIndex] || '';
          });
          return rowData;
        });
        
        setColumns(cols);
        setData(rows);
      }
      setLoading(false);
    } catch (err) {
      console.error('Failed to parse xlsx:', err);
      setError('Failed to parse Excel file');
      setLoading(false);
    }
  }, [content, file.encoding]);

  if (loading) {
    return (
      <div className="xlsx-preview loading">
        <RefreshCw size={32} className="spin" />
        <p>Loading Excel file...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="xlsx-preview error">
        <File size={48} />
        <p>{error}</p>
        <p style={{ fontSize: '12px', color: '#666' }}>{file.name}</p>
      </div>
    );
  }

  return (
    <div className="xlsx-preview">
      <div className="xlsx-header">
        <span className="xlsx-filename">{file.name}</span>
        <span className="xlsx-sheet">Sheet: 1 of 1</span>
      </div>
      <div className="xlsx-content">
        <Table
          columns={columns}
          dataSource={data}
          pagination={{ pageSize: 50 }}
          size="small"
          scroll={{ x: 'max-content', y: 'calc(100vh - 300px)' }}
        />
      </div>
    </div>
  );
};

/**
 * PDF Viewer Component
 */
const PdfViewer = ({ file, content }) => {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const pdfContentRef = useRef(null);
  const [pageWidth, setPageWidth] = useState(null);

  useLayoutEffect(() => {
    if (!pdfUrl) return;
    const el = pdfContentRef.current;
    if (!el) return;
    const contentWidth = (node) => {
      const r = node.getBoundingClientRect();
      const s = getComputedStyle(node);
      const pl = parseFloat(s.paddingLeft) || 0;
      const pr = parseFloat(s.paddingRight) || 0;
      return Math.max(0, r.width - pl - pr);
    };
    const measure = (entry) => {
      const w = entry ? entry.contentRect.width : contentWidth(el);
      setPageWidth(Math.max(120, Math.min(Math.floor(w), 3200)));
    };
    measure();
    const ro = new ResizeObserver((entries) => {
      const e = entries[0];
      if (e) measure(e);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [pdfUrl]);

  useEffect(() => {
    setPageNumber(1);
  }, [pdfUrl]);

  useEffect(() => {
    try {
      // 将 hex 直接转换为 Uint8Array
      let byteArray;
      if (file.encoding === 'hex') {
        const hexString = content.replace(/\s/g, ''); // 移除空白字符
        byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
      } else {
        // 如果是 base64 编码
        const binaryData = atob(content);
        byteArray = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
          byteArray[i] = binaryData.charCodeAt(i);
        }
      }
      const blob = new Blob([byteArray], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      setPdfUrl(url);
      setLoading(false);
      
      return () => {
        URL.revokeObjectURL(url);
      };
    } catch (err) {
      console.error('Failed to load pdf:', err);
      setError('Failed to load PDF file');
      setLoading(false);
    }
  }, [content, file.encoding]);

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages);
  };

  const goToPrevPage = () => setPageNumber((prev) => Math.max(prev - 1, 1));
  const goToNextPage = () => setPageNumber((prev) => Math.min(prev + 1, numPages));

  if (loading) {
    return (
      <div className="pdf-preview loading">
        <RefreshCw size={32} className="spin" />
        <p>Loading PDF file...</p>
      </div>
    );
  }

  if (error || !pdfUrl) {
    return (
      <div className="pdf-preview error">
        <File size={48} />
        <p>{error || 'Failed to load PDF'}</p>
        <p style={{ fontSize: '12px', color: '#666' }}>{file.name}</p>
      </div>
    );
  }

  return (
    <div className="pdf-preview">
      <div className="pdf-toolbar">
        <button 
          className="pdf-nav-btn" 
          onClick={goToPrevPage} 
          disabled={pageNumber <= 1}
        >
          ← Prev
        </button>
        <span className="pdf-page-info">
          Page {pageNumber} of {numPages || '?'}
        </span>
        <button 
          className="pdf-nav-btn" 
          onClick={goToNextPage} 
          disabled={pageNumber >= numPages}
        >
          Next →
        </button>
      </div>
      <div className="pdf-content" ref={pdfContentRef}>
        <Document
          file={pdfUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={<div className="pdf-page-loading">Loading page...</div>}
          error={<div className="pdf-page-error">Failed to load page</div>}
        >
          {pageWidth != null ? (
            <Page
              pageNumber={pageNumber}
              width={pageWidth}
              renderTextLayer={true}
              renderAnnotationLayer={true}
            />
          ) : (
            <div className="pdf-page-loading">Loading page...</div>
          )}
        </Document>
      </div>
    </div>
  );
};

/**
 * Binary Viewer Component (for other binary files)
 */
const BinaryViewer = ({ file, content }) => {
  const fileExt = file.name.split('.').pop()?.toLowerCase() || '';
  const isDoc = ['doc', 'docx'].includes(fileExt);

  const handleDownload = () => {
    const binaryData = file.encoding === 'hex' ? hexToBase64(content) : content;
    const byteCharacters = atob(binaryData);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray]);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="binary-preview">
      <File size={48} />
      <p className="binary-filename">{file.name}</p>
      <p className="binary-size">{formatSize(file.size)}</p>
      <p className="binary-type">
        {isDoc && '📝 Word Document'}
        {!isDoc && '🔒 Binary File'}
      </p>
      <button className="binary-download-btn" onClick={handleDownload}>
        <Download size={16} />
        Download File
      </button>
      <p className="binary-hint">
        This file type cannot be previewed. Please download to view.
      </p>
    </div>
  );
};

/**
 * HTML Preview Component — renders raw HTML content in a sandboxed iframe
 * Supports:
 *   - Auto-fit width (default) — scales iframe to match scroll area width
 *   - Ctrl/⌘ + 滚轮缩放；适应宽度时滚轮交给容器原生滚动
 *   - 缩放后滚轮平移画布；拖拽平移
 *   - 双击预览区恢复「适应宽度」
 */

// measurer script lives at module scope so Babel never sees <script> inside JSX
const MEASURER_SCRIPT = [
  '<' + 'script>',
  '(function(){',
  '  var lastW=0,lastH=0;',
  '  function report(){',
  '    try{',
  '      var de=document.documentElement,b=document.body;',
  '      var w=Math.max(de.scrollWidth,b.scrollWidth,de.offsetWidth,b.offsetWidth,400);',
  '      var h=Math.max(de.scrollHeight,b.scrollHeight,de.offsetHeight,b.offsetHeight,300);',
  '      if(w!==lastW||h!==lastH){lastW=w;lastH=h;window.parent.postMessage({type:"sizeResult",w:w,h:h},"*");}',
  '    }catch(e){}',
  '  }',
  '  window.addEventListener("message",function(e){if(e.data&&e.data.type==="getSize")report();});',
  '  if(document.readyState==="complete"){report();setTimeout(report,200);setTimeout(report,500);}',
  '  else{window.addEventListener("load",function(){report();setTimeout(report,200);setTimeout(report,500);});}',
  '})();',
  '</' + 'script>'
].join('\n');

const HtmlViewer = ({ content, baseStyles = '' }) => {
  const iframeRef = useRef(null);
  const transformRef = useRef(null);
  const scrollRef = useRef(null);

  const [fitMode, setFitMode] = useState(true);
  const [scale, setScale] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [contentSize, setContentSize] = useState({ w: 1280, h: 800 });
  const [iframeSize, setIframeSize] = useState({ w: 1280, h: 800 });
  const [viewportW, setViewportW] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  // 滚动区内「去掉左右 padding」后的真实内容宽度，用于贴边铺满（避免 margin:auto + 舍入产生大块灰边）
  const availW = viewportW > 0 ? Math.max(viewportW, 1) : 0;

  // effectiveScale: fit → scale content to available width; manual → use slider value
  const effectiveScale = fitMode
    ? availW > 0 && contentSize.w > 0
      ? Math.max(0.05, Math.min(availW / contentSize.w, 8))
      : 1
    : scale;

  // Apply translate + scale on the inner layer (clip box holds layout = scaled size → no phantom horizontal scroll)
  const applyTransform = useCallback((s, px, py) => {
    const el = transformRef.current;
    if (!el) return;
    el.style.transformOrigin = 'top left';
    el.style.transform = `translate(${px}px, ${py}px) scale(${s})`;
  }, []);

  // Measure iframe from inside via postMessage (avoids scrollWidth-in-inline-block issues)
  const measureFromIframe = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe?.contentWindow) return;
    try {
      iframe.contentWindow.postMessage({ type: 'getSize' }, '*');
    } catch (_) {}
  }, []);

  // Listen for measurement result from iframe
  useEffect(() => {
    const handler = (e) => {
      if (e.data?.type !== 'sizeResult') return;
      const { w, h } = e.data;
      if (!w || !h) return;
      const cappedW = Math.min(Math.max(w, 320), 12000);
      const cappedH = Math.min(Math.max(h, 300), 24000);
      setContentSize({ w: cappedW, h: cappedH });
      setIframeSize({ w: cappedW, h: cappedH });
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  // ResizeObserver：用内容区宽度（clientWidth 减去左右 padding），与 clip 实际占位一致
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const measure = () => {
      const style = getComputedStyle(el);
      const pl = parseFloat(style.paddingLeft) || 0;
      const pr = parseFloat(style.paddingRight) || 0;
      setViewportW(Math.max(1, el.clientWidth - pl - pr));
    };
    measure();
    const ro = new ResizeObserver(() => measure());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Inject content into iframe via srcdoc + helper script, then measure
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    setPanX(0);
    setPanY(0);
    setFitMode(true);

    const userBody = content ?? '';
    const docStyles = baseStyles
      ? '<style>' + baseStyles + '</style>'
      : '';

    iframe.srcdoc = '<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8">' +
      docStyles +
      MEASURER_SCRIPT +
      '</head>\n<body>' + userBody + '</body>\n</html>';

    // If iframe already loaded, trigger measurement immediately
    if (iframe.contentDocument?.readyState === 'complete') {
      setTimeout(measureFromIframe, 100);
    }
  }, [content, measureFromIframe]);

  // Re-apply transform whenever scale/pan changes
  useEffect(() => {
    applyTransform(effectiveScale, panX, panY);
  }, [effectiveScale, panX, panY, applyTransform]);

  const handleWheel = useCallback((e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setScale((s) => Math.max(0.05, Math.min(s + delta, 10)));
      setFitMode(false);
      return;
    }
    if (fitMode) {
      return;
    }
    e.preventDefault();
    setPanX((px) => px - e.deltaX);
    setPanY((py) => py - e.deltaY);
  }, [fitMode]);

  // Drag-to-pan
  const handleMouseDown = (e) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY, panX, panY };
  };

  const handleMouseMove = useCallback((e) => {
    if (!isDragging) return;
    setPanX(dragStart.current.panX + (e.clientX - dragStart.current.x));
    setPanY(dragStart.current.panY + (e.clientY - dragStart.current.y));
  }, [isDragging]);

  const handleMouseUp = useCallback(() => setIsDragging(false), []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, [handleWheel]);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const zoomReset = () => {
    setScale(1); setPanX(0); setPanY(0);
    setIframeSize({ w: contentSize.w, h: contentSize.h });
    setFitMode(true);
  };

  // Fit 时 clip 宽强制等于 availW，避免 round(w*scale) 小于容器导致 margin:auto 两侧大块灰底
  const scaledW = fitMode
    ? Math.max(1, Math.round(availW))
    : Math.max(1, Math.round(iframeSize.w * effectiveScale));
  const scaledH = Math.max(1, Math.round(iframeSize.h * effectiveScale));

  return (
    <div className="html-preview">
      <div
        ref={scrollRef}
        className={`html-preview-scroll ${isDragging ? 'dragging' : ''}`}
        onMouseDown={handleMouseDown}
        onDoubleClick={zoomReset}
        title="Ctrl 或 ⌘ + 滚轮缩放 · 双击恢复适应宽度"
      >
        <div
          className="html-preview-clip"
          style={{ width: scaledW, height: scaledH }}
        >
          <div
            ref={transformRef}
            className="html-preview-transform"
            style={{ width: iframeSize.w, height: iframeSize.h }}
          >
            <iframe
              ref={iframeRef}
              className="html-preview-iframe"
              style={{ width: iframeSize.w, height: iframeSize.h }}
              title="HTML Preview"
              sandbox="allow-scripts allow-same-origin"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * DOCX Viewer Component — converts .docx to styled HTML via mammoth
 */
const DocxViewer = ({ file, content }) => {
  const [html, setHtml] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);

        let byteArray;
        if (file.encoding === 'hex') {
          const hexString = content.replace(/\s/g, '');
          byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map((b) => parseInt(b, 16)));
        } else {
          const binaryData = atob(content);
          byteArray = new Uint8Array(binaryData.length);
          for (let i = 0; i < binaryData.length; i++) {
            byteArray[i] = binaryData.charCodeAt(i);
          }
        }

        const result = await mammoth.convertToHtml({ arrayBuffer: byteArray.buffer }, {
          styleMap: [
            "p[style-name='Heading 1'] => h1:fresh",
            "p[style-name='Heading 2'] => h2:fresh",
            "p[style-name='Heading 3'] => h3:fresh",
            "p[style-name='Title'] => h1.title-docx:fresh",
            "b => strong",
            "i => em",
            "u => u",
            "strike => del",
          ]
        });

        setHtml(`<div class="docx-flow">${result.value}</div>`);
      } catch (err) {
        console.error('Failed to load docx:', err);
        setError('Failed to load Word file: ' + err.message);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [content, file.encoding]);

  if (loading) {
    return (
      <div className="docx-preview loading">
        <RefreshCw size={32} className="spin" />
        <p>Loading Word document…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="docx-preview error">
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="docx-preview">
      <HtmlViewer content={html} baseStyles={DOCX_BASE_STYLES} />
    </div>
  );
};

// Default styles injected into DOCX iframe so mammoth HTML looks like a real document.
// Word→mammoth 常带右缩进、max-width、大页边距等内联样式，易在预览里留下大块右侧空白；此处统一压平并让块级内容铺满 .docx-flow。
const DOCX_BASE_STYLES = [
  'html, body { margin: 0; width: 100%; box-sizing: border-box; }',
  'body { font-family: "Times New Roman", Georgia, "Songti SC", "SimSun", serif; font-size: 12pt; line-height: 1.6; color: #222; background: #fff; padding: 28px 20px; }',
  '.docx-flow { width: 100%; max-width: 100%; margin: 0; padding: 0; box-sizing: border-box; }',
  '.docx-flow p, .docx-flow h1, .docx-flow h2, .docx-flow h3, .docx-flow h4 { width: 100% !important; max-width: 100% !important; margin-left: 0 !important; margin-right: 0 !important; padding-left: 0 !important; padding-right: 0 !important; box-sizing: border-box; }',
  '.docx-flow ul, .docx-flow ol { width: 100% !important; max-width: 100% !important; margin-left: 0 !important; margin-right: 0 !important; padding-right: 0 !important; box-sizing: border-box; }',
  '.docx-flow table { width: 100% !important; max-width: 100% !important; margin-left: 0 !important; margin-right: 0 !important; }',
  '.docx-flow blockquote { width: 100% !important; max-width: 100% !important; margin-left: 0 !important; margin-right: 0 !important; padding-left: 12pt !important; padding-right: 0 !important; border-left: 4px solid #ccc; box-sizing: border-box; }',
  'h1 { font-size: 24pt; font-weight: bold; margin: 18pt 0 6pt; border-bottom: 2px solid #333; padding-bottom: 4pt; }',
  'h1.title-docx { font-size: 28pt; text-align: center; border-bottom: none; margin-bottom: 18pt; }',
  'h2 { font-size: 18pt; font-weight: bold; margin: 14pt 0 4pt; }',
  'h3 { font-size: 14pt; font-weight: bold; margin: 10pt 0 4pt; }',
  'p { margin: 4pt 0; text-indent: 24pt; }',
  'p[style-name]:not([style-name^="Heading"]):not([style-name="Title"]) { text-indent: 0; }',
  'strong, b { font-weight: bold; }',
  'em, i { font-style: italic; }',
  'u { text-decoration: underline; }',
  'del { text-decoration: line-through; }',
  'ul, ol { margin: 6pt 0; padding-left: 30pt; }',
  'li { margin: 3pt 0; }',
  'table { border-collapse: collapse; width: 100%; margin: 8pt 0; }',
  'td, th { border: 1px solid #999; padding: 4pt 8pt; }',
  'th { background: #f0f0f0; font-weight: bold; }',
  'img { max-width: 100%; height: auto; }',
  'blockquote { border-left: 4px solid #ccc; padding-left: 12pt; color: #555; margin: 8pt 0; }',
].join('\n');

/**
 * PPTX: decode entities and escape for safe HTML
 */
const decodeXmlEntities = (str) => {
  if (!str) return '';
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n, 10)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCharCode(parseInt(h, 16)));
};

const escapeHtml = (str) =>
  str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

const PPTX_WEB_IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg']);

const pptxMimeFromExt = (ext) => {
  const e = (ext || '').toLowerCase();
  if (e === 'png') return 'image/png';
  if (e === 'jpg' || e === 'jpeg') return 'image/jpeg';
  if (e === 'gif') return 'image/gif';
  if (e === 'webp') return 'image/webp';
  if (e === 'bmp') return 'image/bmp';
  if (e === 'svg') return 'image/svg+xml';
  return null;
};

const zipEntryInsensitive = (zip, pathNorm) => {
  const n = pathNorm.replace(/\\/g, '/');
  const lower = n.toLowerCase();
  const key = Object.keys(zip.files).find(
    (k) => !zip.files[k].dir && k.replace(/\\/g, '/').toLowerCase() === lower
  );
  return key ? zip.file(key) : null;
};

/** Resolve OOXML Target= relative to the part path (e.g. slide1.xml). */
const resolvePptxRelTarget = (partPath, target) => {
  const norm = partPath.replace(/\\/g, '/');
  const idx = norm.lastIndexOf('/');
  const dir = idx >= 0 ? norm.slice(0, idx) : '';
  const parts = dir.split('/').filter(Boolean);
  const segs = target.replace(/\\/g, '/').split('/').filter((x) => x && x !== '.');
  for (const p of segs) {
    if (p === '..') parts.pop();
    else parts.push(p);
  }
  return parts.join('/');
};

const parsePptxRelationshipElements = (relsXml) => {
  const rows = [];
  if (!relsXml) return rows;
  const re = /<Relationship\b([^>]*)>/gi;
  let m;
  while ((m = re.exec(relsXml)) !== null) {
    const attrs = m[1];
    const id = /Id\s*=\s*"([^"]+)"/i.exec(attrs)?.[1];
    const type = /Type\s*=\s*"([^"]+)"/i.exec(attrs)?.[1];
    const target = /Target\s*=\s*"([^"]+)"/i.exec(attrs)?.[1];
    const targetMode = /TargetMode\s*=\s*"([^"]+)"/i.exec(attrs)?.[1];
    if (id && target) rows.push({ id, type: type || '', target, targetMode });
  }
  return rows;
};

/** r:embed ids in document order (deduped) for pictures / backgrounds. */
const collectOrderedPptxEmbedIds = (slideXml) => {
  const ids = [];
  const seen = new Set();
  // Collect all r:embed attributes (covers shapes, blip fills, backgrounds, etc.)
  const re = /\br:embed="([^"]+)"/g;
  let m;
  while ((m = re.exec(slideXml)) !== null) {
    const id = m[1];
    if (!seen.has(id)) {
      seen.add(id);
      ids.push(id);
    }
  }
  return ids;
};

const PPTX_MAX_IMAGE_BYTES = 12 * 1024 * 1024;

const loadPptxSlideImageDataUrls = async (zip, slidePath, slideXml) => {
  const slideNorm = slidePath.replace(/\\/g, '/');
  const fileName = slideNorm.split('/').pop();
  const dir = slideNorm.includes('/') ? slideNorm.slice(0, slideNorm.lastIndexOf('/') + 1) : '';
  const relsPath = `${dir}_rels/${fileName}.rels`;
  const relFile = zip.file(relsPath) || zipEntryInsensitive(zip, relsPath);

  const idToImagePath = new Map();
  if (relFile) {
    const relsXml = await relFile.async('string');
    for (const row of parsePptxRelationshipElements(relsXml)) {
      if (row.targetMode === 'External') continue;
      if (!row.type.toLowerCase().includes('relationships/image')) continue;
      const t = row.target.replace(/\\/g, '/');
      const resolved = t.startsWith('/')
        ? t.replace(/^\/+/, '')
        : resolvePptxRelTarget(slideNorm, row.target);
      idToImagePath.set(row.id, resolved);
    }
  }

  const embedIds = collectOrderedPptxEmbedIds(slideXml);
  const dataUrls = [];

  for (const rid of embedIds) {
    const imgPath = idToImagePath.get(rid);
    if (!imgPath) continue;
    const ext = (imgPath.split('.').pop() || '').split('?')[0];
    const mime = pptxMimeFromExt(ext);
    if (!mime || !PPTX_WEB_IMAGE_EXT.has(ext.toLowerCase())) continue;
    const f = zip.file(imgPath) || zipEntryInsensitive(zip, imgPath);
    if (!f) continue;
    const u8 = await f.async('uint8array');
    if (u8.length > PPTX_MAX_IMAGE_BYTES) continue;
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < u8.length; i += chunk) {
      binary += String.fromCharCode.apply(null, u8.subarray(i, Math.min(i + chunk, u8.length)));
    }
    dataUrls.push(`data:${mime};base64,${btoa(binary)}`);
  }

  return dataUrls;
};

/**
 * Extract visible text from a slide / OOXML fragment.
 * Real PPTX uses <a:t xml:space="preserve"> — plain <a:t> regex misses almost all text.
 */
const extractPptxSlideTexts = (slideXml) => {
  if (!slideXml) return [];
  const texts = [];

  const pushText = (raw) => {
    const t = decodeXmlEntities(raw).replace(/\s+/g, ' ').trim();
    if (t) texts.push(t);
  };

  // DrawingML text runs (most common)
  const reAT = /<a:t[^>]*>([\s\S]*?)<\/a:t>/gi;
  let m;
  while ((m = reAT.exec(slideXml)) !== null) {
    pushText(m[1]);
  }

  // Some generators use different prefix but same local name
  if (texts.length === 0) {
    const reAnyT = /<[^:>\s]+:t[^>]*>([\s\S]*?)<\/[^:>\s]+:t>/gi;
    while ((m = reAnyT.exec(slideXml)) !== null) {
      pushText(m[1]);
    }
  }

  return texts;
};

const buildSlidePreviewHtml = (slideXml, slideIndex, imageDataUrls = []) => {
  const texts = extractPptxSlideTexts(slideXml);
  const textBlock =
    texts.length > 0 ? texts.map((t) => `<p>${escapeHtml(t)}</p>`).join('') : '';
  const imgs =
    imageDataUrls.length > 0
      ? imageDataUrls
          .map(
            (src) =>
              `<div class="pptx-slide-img-wrap"><img class="pptx-slide-img" src="${src}" alt="" /></div>`
          )
          .join('')
      : '';
  const emptyHint =
    !textBlock && !imgs
      ? '<p class="pptx-empty-hint">此页未解析到文本或图片（可能为图表、视频或特殊版式）。</p>'
      : '';
  return `
      <div class="pptx-slide-inner" data-slide="${slideIndex}">
        <div class="slide-texts">${textBlock}${emptyHint}</div>
        ${imgs ? `<div class="slide-images">${imgs}</div>` : ''}
      </div>
    `;
};

/**
 * PPTX Viewer Component
 */
const PptxViewer = ({ file, content }) => {
  const [slides, setSlides] = useState([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadPptx = async () => {
      try {
        setLoading(true);
        setError(null);

        let byteArray;
        if (file.encoding === 'hex') {
          const hexString = content.replace(/\s/g, '');
          byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map((byte) => parseInt(byte, 16)));
        } else if (file.encoding === 'base64') {
          const binaryData = atob(content);
          byteArray = new Uint8Array(binaryData.length);
          for (let i = 0; i < binaryData.length; i++) {
            byteArray[i] = binaryData.charCodeAt(i);
          }
        } else {
          const binaryData = atob(content);
          byteArray = new Uint8Array(binaryData.length);
          for (let i = 0; i < binaryData.length; i++) {
            byteArray[i] = binaryData.charCodeAt(i);
          }
        }

        const zip = await JSZip.loadAsync(byteArray);

        const slideRefs = [];
        const contentTypes = await zip.file('[Content_Types].xml')?.async('string');

        if (contentTypes) {
          const slideMatches = contentTypes.match(/PartName="\/ppt\/slides\/slide\d+\.xml"/g) || [];
          for (const match of slideMatches) {
            const slideNum = match.match(/slide(\d+)\.xml/)[1];
            slideRefs.push(`ppt/slides/slide${slideNum}.xml`);
          }
        }

        if (slideRefs.length === 0) {
          const allFiles = Object.keys(zip.files);
          for (const fileName of allFiles) {
            if (fileName.match(/ppt\/slides\/slide\d+\.xml$/)) {
              slideRefs.push(fileName);
            }
          }
        }

        slideRefs.sort((a, b) => {
          const numA = parseInt(a.match(/slide(\d+)/)[1], 10);
          const numB = parseInt(b.match(/slide(\d+)/)[1], 10);
          return numA - numB;
        });

        const slidesData = [];
        for (const slidePath of slideRefs) {
          const slideXml = await zip.file(slidePath)?.async('string');
          if (slideXml) {
            const imageDataUrls = await loadPptxSlideImageDataUrls(zip, slidePath, slideXml);
            slidesData.push({ path: slidePath, xml: slideXml, imageDataUrls });
          }
        }

        setSlides(slidesData);
        setCurrentSlide(0);
      } catch (err) {
        console.error('Failed to load pptx:', err);
        setError('Failed to load PowerPoint file: ' + err.message);
      } finally {
        setLoading(false);
      }
    };

    loadPptx();
  }, [content, file.encoding]);

  const currentSlideHtml = useMemo(() => {
    const s = slides[currentSlide];
    if (!s?.xml) return '';
    return buildSlidePreviewHtml(s.xml, currentSlide, s.imageDataUrls || []);
  }, [slides, currentSlide]);

  const thumbHtml = useMemo(() => {
    return slides.map((s, i) => buildSlidePreviewHtml(s.xml, i, s.imageDataUrls || []));
  }, [slides]);

  const goToPrevSlide = () => setCurrentSlide((prev) => Math.max(prev - 1, 0));
  const goToNextSlide = () => setCurrentSlide((prev) => Math.min(prev + 1, slides.length - 1));

  if (loading) {
    return (
      <div className="pptx-preview loading">
        <RefreshCw size={32} className="spin" />
        <p>Loading PowerPoint file...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pptx-preview error">
        <File size={48} />
        <p>{error}</p>
        <p style={{ fontSize: '12px', color: '#666' }}>{file.name}</p>
      </div>
    );
  }

  if (slides.length === 0) {
    return (
      <div className="pptx-preview error">
        <File size={48} />
        <p>No slides found in this file</p>
        <p style={{ fontSize: '12px', color: '#666' }}>{file.name}</p>
      </div>
    );
  }

  return (
    <div className="pptx-preview">
      <div className="pptx-toolbar">
        <button
          className="pptx-nav-btn"
          onClick={goToPrevSlide}
          disabled={currentSlide <= 0}
        >
          ← Prev
        </button>
        <span className="pptx-page-info">
          Slide {currentSlide + 1} of {slides.length}
        </span>
        <button
          className="pptx-nav-btn"
          onClick={goToNextSlide}
          disabled={currentSlide >= slides.length - 1}
        >
          Next →
        </button>
      </div>
      <div className="pptx-content">
        <div className="pptx-slide-container">
          <div className="pptx-slide">
            <div className="pptx-slide-number">Slide {currentSlide + 1}</div>
            <div
              className="pptx-slide-html"
              dangerouslySetInnerHTML={{
                __html: currentSlideHtml || '<div class="pptx-empty-hint">Loading…</div>',
              }}
            />
          </div>
        </div>
      </div>
      <div className="pptx-thumbnails">
        {slides.map((slide, index) => (
          <div
            key={slide.path || index}
            className={`pptx-thumb ${currentSlide === index ? 'active' : ''}`}
            onClick={() => setCurrentSlide(index)}
          >
            <div className="thumb-number">{index + 1}</div>
            <div className="thumb-content">
              {thumbHtml[index] ? (
                <div dangerouslySetInnerHTML={{ __html: thumbHtml[index] }} />
              ) : (
                <div className="thumb-placeholder">Slide {index + 1}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/**
 * Get Monaco Editor language from file extension
 */
const getLanguage = (filename) => {
  const ext = filename.split('.').pop()?.toLowerCase();
  const languageMap = {
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'py': 'python',
    'java': 'java',
    'cpp': 'cpp',
    'c': 'c',
    'h': 'c',
    'go': 'go',
    'rs': 'rust',
    'php': 'php',
    'rb': 'ruby',
    'html': 'html',
    'htm': 'html',
    'css': 'css',
    'scss': 'scss',
    'less': 'less',
    'json': 'json',
    'xml': 'xml',
    'yaml': 'yaml',
    'yml': 'yaml',
    'md': 'markdown',
    'sql': 'sql',
    'sh': 'shell',
    'bash': 'shell',
    'zsh': 'shell',
    'dockerfile': 'dockerfile',
    'vue': 'vue',
    'svelte': 'svelte',
    'swift': 'swift',
    'kt': 'kotlin',
    'scala': 'scala',
    'r': 'r',
    'dart': 'dart',
    'lua': 'lua',
    'perl': 'perl',
    'clj': 'clojure',
    'cljs': 'clojure',
    'ex': 'elixir',
    'exs': 'elixir',
    'erl': 'erlang',
    'hrl': 'erlang',
    'fs': 'fsharp',
    'fsx': 'fsharp',
    'fsi': 'fsharp',
    'ml': 'ocaml',
    'mli': 'ocaml',
    'hs': 'haskell',
    'lhs': 'haskell',
    'elm': 'elm',
    'purs': 'purescript',
    'coffee': 'coffeescript',
    'litcoffee': 'coffeescript',
    'cs': 'csharp',
    'csx': 'csharp',
    'vb': 'vb',
    'ps1': 'powershell',
    'psm1': 'powershell',
    'psd1': 'powershell',
    'bat': 'bat',
    'cmd': 'bat',
    'ini': 'ini',
    'cfg': 'ini',
    'conf': 'ini',
    'properties': 'ini',
    'toml': 'toml',
    'lock': 'json',
    'gitignore': 'ignore',
    'dockerignore': 'ignore',
    'npmignore': 'ignore',
    'eslintignore': 'ignore',
    'prettierignore': 'ignore',
    'env': 'ini',
    'env.local': 'ini',
    'env.development': 'ini',
    'env.production': 'ini',
    'env.test': 'ini',
    'log': 'log',
    'txt': 'plaintext'
  };
  return languageMap[ext] || 'plaintext';
};

/**
 * File Editor Component with Monaco Editor
 */
const FileEditor = ({ file, content, onSave, onClose, isSaving, readOnly = false }) => {
  // 确保 content 是字符串
  const safeContent = content ?? '';
  const [editedContent, setEditedContent] = useState(safeContent);
  const [isDirty, setIsDirty] = useState(false);
  const [isPreviewMode, setIsPreviewMode] = useState(false);
  const editorRef = useRef(null);

  // 监听 content 变化，更新 editedContent
  useEffect(() => {
    setEditedContent(safeContent);
    setIsDirty(false);
    setIsPreviewMode(false);
  }, [safeContent, file?.path]);

  const handleSave = () => {
    onSave(file.path, editedContent);
    setIsDirty(false);
  };

  const handleEditorChange = (value) => {
    setEditedContent(value);
    setIsDirty(true);
  };

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;

    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      if (!readOnly && isDirty && !isSaving) {
        handleSave();
      }
    });
  };

  if (!file || !file.name) {
    return null;
  }

  const isBinary = file.encoding === 'hex';
  const fileExt = file.name.split('.').pop()?.toLowerCase() || '';
  const isImage = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(fileExt);
  const isPptx = ['pptx', 'ppt'].includes(fileExt);
  const isDocx = ['docx', 'doc'].includes(fileExt);
  const isHtml = ['html', 'htm'].includes(fileExt);
  const language = getLanguage(file.name);

  return (
    <div className="file-editor">
      <div className="file-editor-header">
        <WindowDots />
        <span className="editor-filename">{file.name}</span>
        <div className="editor-actions">
          {isHtml && !isImage && (
            <button
              className={`editor-btn ${isPreviewMode ? 'active' : ''}`}
              onClick={() => setIsPreviewMode((p) => !p)}
              title={isPreviewMode ? '切换到编辑' : '预览 HTML'}
            >
              {isPreviewMode ? <Edit3 size={14} /> : <FileText size={14} />}
            </button>
          )}
          {!readOnly && !isBinary && !isImage && (
            <button
              className="editor-btn"
              onClick={handleSave}
              disabled={!isDirty || isSaving}
            >
              {isSaving ? <RefreshCw size={14} className="spin" /> : <Save size={14} />}
              {isDirty && <span className="dirty-indicator">*</span>}
            </button>
          )}
          <button className="editor-btn" onClick={onClose}>
            <X size={14} />
          </button>
        </div>
      </div>
      <div className="file-editor-content">
        {isImage ? (
          <ImageViewer file={file} content={safeContent} fileExt={fileExt} />
        ) : fileExt === 'pdf' ? (
          <PdfViewer file={file} content={safeContent} />
        ) : ['xlsx', 'xls'].includes(fileExt) ? (
          <XlsxViewer file={file} content={safeContent} />
        ) : isPptx ? (
          <PptxViewer file={file} content={safeContent} />
        ) : isDocx ? (
          <DocxViewer file={file} content={safeContent} />
        ) : isBinary ? (
          <BinaryViewer file={file} content={safeContent} />
        ) : isHtml && isPreviewMode ? (
          <HtmlViewer content={editedContent} />
        ) : (
          <Editor
            height="100%"
            language={language}
            value={editedContent}
            onChange={readOnly ? undefined : handleEditorChange}
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
              formatOnPaste: !readOnly,
              formatOnType: !readOnly,
              suggestOnTriggerCharacters: !readOnly,
              quickSuggestions: !readOnly,
              snippetSuggestions: 'inline',
              readOnly: readOnly,
            }}
            theme="vs-dark"
          />
        )}
      </div>
    </div>
  );
};

/**
 * Breadcrumb Component
 */
const Breadcrumb = ({ path, onNavigate, rootName = 'workspace' }) => {
  const parts = path === '.' ? [] : path.split('/').filter(Boolean);

  return (
    <div className="breadcrumb">
      <button
        className="breadcrumb-item root"
        onClick={() => onNavigate('.')}
      >
        <Home size={14} />
        {rootName}
      </button>
      {parts.map((part, index) => {
        const currentPath = parts.slice(0, index + 1).join('/');
        return (
          <React.Fragment key={index}>
            <ChevronRight size={14} className="breadcrumb-separator" />
            <button
              className="breadcrumb-item"
              onClick={() => onNavigate(currentPath)}
            >
              {part}
            </button>
          </React.Fragment>
        );
      })}
    </div>
  );
};

/**
 * Workspace Panel Component
 */
const WorkspacePanel = ({ sendWSMessage }) => {
  const [rootPath, setRootPath] = useState('');
  const [currentPath, setCurrentPath] = useState('.');
  const [items, setItems] = useState([]);
  const [treeData, setTreeData] = useState([]);
  const [selectedPath, setSelectedPath] = useState(null);
  const [expandedPaths, setExpandedPaths] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Tree data state - must be defined before functions that use it
  const [treeItems, setTreeItems] = useState({});

  // Ref to track initial load
  const initialLoadDone = useRef(false);

  // File editor state
  const [editingFile, setEditingFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Modal states
  const [isCreateFolderModalOpen, setIsCreateFolderModalOpen] = useState(false);
  const [isCreateFileModalOpen, setIsCreateFileModalOpen] = useState(false);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [contextMenuItem, setContextMenuItem] = useState(null);

  // Get workspace root
  const fetchRoot = useCallback(async () => {
    try {
      const response = await sendWSMessage('workspace_get_root', {});
      if (response.data?.root) {
        setRootPath(response.data.root);
      }
    } catch (err) {
      message.error('Failed to get workspace root: ' + err.message);
    }
  }, [sendWSMessage]);

  // List directory contents
  const listDirectory = useCallback(async (path = '.') => {
    setLoading(true);
    try {
      const response = await sendWSMessage('workspace_list', { path });
      if (response.data?.items) {
        setItems(response.data.items);
        setCurrentPath(response.data.path);
      }
    } catch (err) {
      message.error('Failed to list directory: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage]);

  // Read file
  const readFile = useCallback(async (path) => {
    try {
      const response = await sendWSMessage('workspace_read', { path });
      if (response.data) {
        setEditingFile(response.data);
        setFileContent(response.data.content);
      }
    } catch (err) {
      message.error('Failed to read file: ' + err.message);
    }
  }, [sendWSMessage]);

  // Write file
  const writeFile = useCallback(async (path, content) => {
    setIsSaving(true);
    try {
      await sendWSMessage('workspace_write', { path, content });
      message.success('File saved successfully');
    } catch (err) {
      message.error('Failed to save file: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  }, [sendWSMessage]);

  // Load directory for tree view - defined before handleSelect
  const loadTreeDirectory = useCallback(async (path) => {
    try {
      const response = await sendWSMessage('workspace_list', { path });
      if (response.data?.items) {
        setTreeItems(prev => ({ ...prev, [path]: response.data.items }));
        return response.data.items;
      }
      return [];
    } catch (err) {
      console.error('Failed to load tree directory:', err);
      return [];
    }
  }, [sendWSMessage]);

  // Delete file or directory
  const deleteItem = useCallback(async (path, isDirectory) => {
    Modal.confirm({
      title: `Delete ${isDirectory ? 'Directory' : 'File'}`,
      content: `Are you sure you want to delete "${path}"?`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          await sendWSMessage('workspace_delete', {
            path,
            recursive: isDirectory
          });
          message.success('Deleted successfully');
          // 刷新当前目录列表
          listDirectory(currentPath);
          // 刷新树形视图 - 获取父目录路径
          const parentPath = path.includes('/') ? path.substring(0, path.lastIndexOf('/')) : '.';
          if (treeItems[parentPath]) {
            loadTreeDirectory(parentPath);
          }
          // 如果删除的是当前选中的文件，关闭编辑器
          if (selectedPath === path) {
            setSelectedPath(null);
            setEditingFile(null);
            setFileContent('');
          }
          // 从 treeItems 中移除被删除的项
          setTreeItems(prev => {
            const next = { ...prev };
            delete next[path];
            return next;
          });
        } catch (err) {
          message.error('Failed to delete: ' + err.message);
        }
      }
    });
  }, [sendWSMessage, currentPath, listDirectory, selectedPath, treeItems, loadTreeDirectory]);

  // Create directory
  const createDirectory = useCallback(async () => {
    if (!newName.trim()) return;
    const path = currentPath === '.' ? newName : `${currentPath}/${newName}`;
    try {
      await sendWSMessage('workspace_mkdir', { path });
      message.success('Directory created successfully');
      setIsCreateFolderModalOpen(false);
      setNewName('');
      listDirectory(currentPath);
      // 刷新树形视图
      loadTreeDirectory(currentPath);
    } catch (err) {
      message.error('Failed to create directory: ' + err.message);
    }
  }, [sendWSMessage, currentPath, newName, listDirectory, loadTreeDirectory]);

  // Create file
  const createFile = useCallback(async () => {
    if (!newName.trim()) return;
    const path = currentPath === '.' ? newName : `${currentPath}/${newName}`;
    try {
      await sendWSMessage('workspace_write', { path, content: '' });
      message.success('File created successfully');
      setIsCreateFileModalOpen(false);
      setNewName('');
      listDirectory(currentPath);
      // 刷新树形视图
      loadTreeDirectory(currentPath);
    } catch (err) {
      message.error('Failed to create file: ' + err.message);
    }
  }, [sendWSMessage, currentPath, newName, listDirectory, loadTreeDirectory]);

  // Rename item
  const renameItem = useCallback(async () => {
    if (!newName.trim() || !contextMenuItem) return;
    const oldPath = contextMenuItem.path;
    const parentPath = oldPath.includes('/') ? oldPath.substring(0, oldPath.lastIndexOf('/')) : '.';
    const newPath = parentPath === '.' ? newName : `${parentPath}/${newName}`;

    try {
      await sendWSMessage('workspace_rename', { old_path: oldPath, new_path: newPath });
      message.success('Renamed successfully');
      setIsRenameModalOpen(false);
      setNewName('');
      listDirectory(currentPath);
      // 刷新树形视图 - 刷新父目录
      loadTreeDirectory(parentPath);
      // 如果重命名的是当前选中的文件，更新选中路径
      if (selectedPath === oldPath) {
        setSelectedPath(newPath);
      }
    } catch (err) {
      message.error('Failed to rename: ' + err.message);
    }
  }, [sendWSMessage, contextMenuItem, currentPath, newName, listDirectory, loadTreeDirectory, selectedPath]);

  // Handle tree expand - load children on demand
  const handleTreeExpand = useCallback(async (path) => {
    const isCurrentlyExpanded = expandedPaths.has(path);

    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (isCurrentlyExpanded) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });

    // Load children if expanding and not already loaded
    if (!isCurrentlyExpanded && !treeItems[path]) {
      await loadTreeDirectory(path);
    }
  }, [expandedPaths, treeItems, loadTreeDirectory]);

  // Handle item selection
  const handleSelect = useCallback((item) => {
    setSelectedPath(item.path);
    if (item.type === 'directory') {
      listDirectory(item.path);
      // Also expand in tree view and load children
      setExpandedPaths(prev => {
        if (!prev.has(item.path)) {
          const next = new Set(prev);
          next.add(item.path);
          // Load children if not already loaded
          if (!treeItems[item.path]) {
            loadTreeDirectory(item.path);
          }
          return next;
        }
        return prev;
      });
    } else {
      readFile(item.path);
    }
  }, [listDirectory, readFile, treeItems, loadTreeDirectory]);

  // Handle context menu
  const handleContextMenu = useCallback((e, item) => {
    e.preventDefault();
    setContextMenuItem(item);
    setSelectedPath(item.path);

    const menuItems = [
      {
        key: 'rename',
        label: 'Rename',
        icon: <Edit3 size={14} />,
        onClick: () => {
          setNewName(item.name);
          setIsRenameModalOpen(true);
        }
      },
      {
        key: 'delete',
        label: 'Delete',
        icon: <Trash2 size={14} />,
        danger: true,
        onClick: () => deleteItem(item.path, item.type === 'directory')
      }
    ];

    // Show context menu using antd Dropdown
    const menu = <Menu items={menuItems} />;
    // Use a simple approach - show modal options
    Modal.confirm({
      title: item.name,
      content: (
        <div className="context-menu-options">
          <Button
            icon={<Edit3 size={14} />}
            onClick={() => {
              Modal.destroyAll();
              setNewName(item.name);
              setIsRenameModalOpen(true);
            }}
            style={{ marginRight: 8 }}
          >
            Rename
          </Button>
          <Button
            danger
            icon={<Trash2 size={14} />}
            onClick={() => {
              Modal.destroyAll();
              deleteItem(item.path, item.type === 'directory');
            }}
          >
            Delete
          </Button>
        </div>
      ),
      footer: null,
      closable: true,
      maskClosable: true
    });
  }, [deleteItem]);

  // Initial load - 只在组件挂载且 sendWSMessage 可用时执行一次
  useEffect(() => {
    if (initialLoadDone.current) return;
    if (!sendWSMessage) return;

    initialLoadDone.current = true;

    fetchRoot();
    // 直接调用 sendWSMessage 而不是通过 listDirectory，避免依赖问题
    sendWSMessage('workspace_list', { path: '.' }).then(response => {
      if (response.data?.items) {
        setItems(response.data.items);
        setCurrentPath(response.data.path || '.');
        setTreeItems({ '.': response.data.items });
      }
    }).catch(err => {
      console.error('Failed to load workspace:', err);
      message.error('Failed to load workspace: ' + err.message);
    });
  }, [sendWSMessage]); // 添加 sendWSMessage 到依赖数组

  // Filter items by search
  const filteredItems = items.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="workspace-panel-container">
      {/* Toolbar */}
      <div className="workspace-toolbar">
        <div className="toolbar-left">
          <WindowDots />
          <span className="toolbar-title">WORKSPACE_EXPLORER</span>
        </div>
        <div className="toolbar-right">
          <button
            className="toolbar-btn"
            onClick={() => listDirectory(currentPath)}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
          <button
            className="toolbar-btn"
            onClick={() => setIsCreateFolderModalOpen(true)}
          >
            <FolderPlus size={14} />
          </button>
          <button
            className="toolbar-btn"
            onClick={() => setIsCreateFileModalOpen(true)}
          >
            <FilePlus size={14} />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="workspace-content">
        {/* Sidebar - Tree View */}
        <div className="workspace-sidebar">
          <div className="sidebar-header">
            <span>EXPLORER</span>
          </div>
          <div className="tree-view">
            {treeItems['.']?.map(item => (
              <TreeNode
                key={item.path}
                item={item}
                level={0}
                selectedPath={selectedPath}
                expandedPaths={expandedPaths}
                onSelect={handleSelect}
                onToggle={handleTreeExpand}
                onContextMenu={handleContextMenu}
                treeItems={treeItems}
              />
            ))}
          </div>
        </div>

        {/* File Editor */}
        {editingFile ? (
          <FileEditor
            file={editingFile}
            content={fileContent}
            onSave={writeFile}
            onClose={() => {
              setEditingFile(null);
              setFileContent('');
            }}
            isSaving={isSaving}
          />
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666' }}>
            Select a file to view its contents
          </div>
        )}
      </div>

      {/* Create Folder Modal */}
      <Modal
        title="Create New Folder"
        open={isCreateFolderModalOpen}
        onOk={createDirectory}
        onCancel={() => {
          setIsCreateFolderModalOpen(false);
          setNewName('');
        }}
        okText="Create"
      >
        <Input
          placeholder="Folder name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={createDirectory}
          autoFocus
        />
      </Modal>

      {/* Create File Modal */}
      <Modal
        title="Create New File"
        open={isCreateFileModalOpen}
        onOk={createFile}
        onCancel={() => {
          setIsCreateFileModalOpen(false);
          setNewName('');
        }}
        okText="Create"
      >
        <Input
          placeholder="File name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={createFile}
          autoFocus
        />
      </Modal>

      {/* Rename Modal */}
      <Modal
        title="Rename"
        open={isRenameModalOpen}
        onOk={renameItem}
        onCancel={() => {
          setIsRenameModalOpen(false);
          setNewName('');
          setContextMenuItem(null);
        }}
        okText="Rename"
      >
        <Input
          placeholder="New name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={renameItem}
          autoFocus
        />
      </Modal>
    </div>
  );
};

export { FileEditor };
export default WorkspacePanel;
