import React, { useState, useEffect, useLayoutEffect, useCallback, useRef, useMemo } from 'react';
import { File, Image, RefreshCw, Download } from 'lucide-react';
import { Table } from 'antd';
import * as XLSX from 'xlsx';
import * as mammoth from 'mammoth';
import JSZip from 'jszip';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';

// 设置 pdf.js worker - 使用 jsdelivr CDN
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const formatSize = (bytes) => {
  if (bytes === null || bytes === undefined) return '-';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

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

const ImageViewer = ({ file, content, fileExt }) => {
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [imageUrl, setImageUrl] = useState(null);

  useEffect(() => {
    try {
      if (!content || content.trim() === '') {
        setError(true);
        setLoading(false);
        return;
      }
      
      let byteArray;
      if (file.encoding === 'hex') {
        const hexString = content.replace(/\s/g, '');
        // 验证 hex 字符串长度是否为偶数且只包含有效字符
        if (!hexString || hexString.length === 0 || hexString.length % 2 !== 0 || !/^[0-9a-fA-F]+$/.test(hexString)) {
          console.warn('Invalid hex content for image preview:', { length: hexString?.length });
          setError(true);
          setLoading(false);
          return;
        }
        byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
      } else {
        try {
          const binaryData = atob(content);
          byteArray = new Uint8Array(binaryData.length);
          for (let i = 0; i < binaryData.length; i++) {
            byteArray[i] = binaryData.charCodeAt(i);
          }
        } catch (e) {
          console.warn('Failed to decode base64 image:', e);
          setError(true);
          setLoading(false);
          return;
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

const XlsxViewer = ({ file, content }) => {
  const [data, setData] = useState([]);
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    try {
      console.log('XlsxViewer - file.encoding:', file.encoding, 'content length:', content?.length);

      let byteArray;
      if (file.encoding === 'hex') {
        const hexString = (content || '').replace(/\s/g, ''); // 移除空白字符
        console.log('Parsing hex string, length:', hexString.length);
        const pairs = hexString.match(/.{1,2}/g);
        if (!pairs) throw new Error('Invalid hex content');
        byteArray = new Uint8Array(pairs.map(byte => parseInt(byte, 16)));
      } else if (file.encoding === 'base64') {
        const binaryData = atob(content);
        byteArray = new Uint8Array(binaryData.length);
        for (let i = 0; i < binaryData.length; i++) {
          byteArray[i] = binaryData.charCodeAt(i);
        }
      } else {
        byteArray = new TextEncoder().encode(content);
      }

      console.log('Byte array length:', byteArray.length);
      const workbook = XLSX.read(byteArray, { type: 'array' });

      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];

      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

      if (jsonData.length > 0) {
        const headers = jsonData[0];
        const cols = headers.map((header, index) => ({
          title: header || `Column ${index + 1}`,
          dataIndex: `col${index}`,
          key: `col${index}`,
          ellipsis: true,
        }));

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

const PdfViewer = ({ file, content }) => {
  const [numPages, setNumPages] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pdfLoaded, setPdfLoaded] = useState(false);
  const pdfContentRef = useRef(null);
  const pageRefs = useRef([]);
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
      setPageWidth(Math.max(120, Math.min(Math.floor(w * 0.85), 3200)));
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
    try {
      if (!content) {
        setLoading(true);
        return;
      }
      let byteArray;
      if (file.encoding === 'hex') {
        const hexString = content.replace(/\s/g, '');
        if (!hexString || hexString.length % 2 !== 0) {
          throw new Error('Invalid hex content');
        }
        byteArray = new Uint8Array(hexString.length / 2);
        for (let i = 0; i < hexString.length; i += 2) {
          byteArray[i / 2] = parseInt(hexString.substring(i, i + 2), 16);
        }
      } else {
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
      setError(null);

      return () => {
        URL.revokeObjectURL(url);
      };
    } catch (err) {
      console.error('Failed to load pdf:', err);
      setError('Failed to load PDF file');
      setLoading(false);
    }
  }, [content, file.encoding]);

  const onDocumentLoadSuccess = ({ numPages: total }) => {
    setNumPages(total);
    setPdfLoaded(true);
  };

  const onDocumentLoadError = (err) => {
    console.error('PDF document load error:', err);
    setError('Failed to load PDF document');
    setPdfLoaded(false);
  };

  const scrollToPage = useCallback((pageNum) => {
    const pageElement = pageRefs.current[pageNum - 1];
    if (pageElement && pdfContentRef.current) {
      pageElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  useEffect(() => {
    const container = pdfContentRef.current;
    if (!container || !numPages) return;

    const handleScroll = () => {
      const containerRect = container.getBoundingClientRect();
      const containerTop = containerRect.top;

      let closestPage = 1;
      let minDistance = Infinity;

      pageRefs.current.forEach((pageEl, index) => {
        if (!pageEl) return;
        const pageRect = pageEl.getBoundingClientRect();
        const pageTop = pageRect.top - containerTop;
        const distance = Math.abs(pageTop);

        if (distance < minDistance) {
          minDistance = distance;
          closestPage = index + 1;
        }
      });

      setCurrentPage(closestPage);
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [numPages]);

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
    <div className="pdf-preview pdf-scroll-mode">
      <div className="pdf-sidebar">
        <div className="pdf-sidebar-header">
          <span className="pdf-sidebar-title">Pages ({numPages || 0})</span>
        </div>
        <div className="pdf-thumbnails-scroll">
          {numPages && pdfUrl && pdfLoaded ? (
            <Document file={pdfUrl} loading={null} error={null}>
              {Array.from({ length: numPages }, (_, index) => {
                const pNum = index + 1;
                if (pNum > numPages) return null;
                return (
                  <div
                    key={`thumb-${pNum}`}
                    className={`pdf-thumb ${currentPage === pNum ? 'active' : ''}`}
                    onClick={() => scrollToPage(pNum)}
                  >
                    <div className="pdf-thumb-page">
                      <Page
                        pageNumber={pNum}
                        width={100}
                        renderTextLayer={false}
                        renderAnnotationLayer={false}
                        loading={null}
                        onError={() => null}
                      />
                    </div>
                    <div className="pdf-thumb-number">{pNum}</div>
                  </div>
                );
              })}
            </Document>
          ) : null}
        </div>
      </div>
      <div className="pdf-content-scroll" ref={pdfContentRef}>
        <Document
          file={pdfUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          loading={<div className="pdf-page-loading">Loading document...</div>}
          error={<div className="pdf-page-error">Failed to load document</div>}
        >
          {numPages && pdfLoaded && pageWidth != null ? (
            Array.from({ length: numPages }, (_, index) => {
              const pNum = index + 1;
              return (
                <div
                  key={`page-${pNum}`}
                  ref={(el) => (pageRefs.current[pNum - 1] = el)}
                  className="pdf-page-card"
                >
                  <Page
                    pageNumber={pNum}
                    width={pageWidth}
                    renderTextLayer={true}
                    renderAnnotationLayer={true}
                    loading={<div className="pdf-page-loading">Loading page {pNum}...</div>}
                    onError={() => null}
                  />
                </div>
              );
            })
          ) : (
            !pdfLoaded && !error ? (
              <div className="pdf-page-loading">Loading pages...</div>
            ) : null
          )}
        </Document>
      </div>
    </div>
  );
};

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
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const sizeRef = useRef({ w: 0, h: 0 });

  const srcDoc = useMemo(() => {
    return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
html,body{margin:0;width:100%;box-sizing:border-box;}
body{font-family:sans-serif;line-height:1.6;color:#222;background:#fff;padding:20px;}
img{max-width:100%;height:auto;}
table{border-collapse:collapse;width:100%;}
th,td{border:1px solid #ddd;padding:8px;}
pre{background:#f5f5f5;padding:12px;border-radius:4px;overflow:auto;}
${baseStyles}
</style>
</head>
<body>
${content}
${MEASURER_SCRIPT}
</body>
</html>`;
  }, [content, baseStyles]);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    iframe.srcdoc = srcDoc;

    const handleMessage = (e) => {
      if (e.source === iframe.contentWindow && e.data && e.data.type === 'sizeResult') {
        sizeRef.current = { w: e.data.w, h: e.data.h };
        if (fitMode) {
          requestAnimationFrame(() => fitIframe());
        }
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [srcDoc, fitMode]);

  const fitIframe = useCallback(() => {
    const scrollEl = scrollRef.current;
    const transEl = transformRef.current;
    if (!scrollEl || !transEl) return;
    const containerW = scrollEl.clientWidth || 400;
    const contentW = sizeRef.current.w || containerW;
    const nextScale = containerW / Math.max(1, contentW);
    const clampedScale = Math.max(0.2, Math.min(nextScale, 3));
    setScale(clampedScale);
    setOffset({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    if (fitMode) {
      const t = setTimeout(() => fitIframe(), 50);
      return () => clearTimeout(t);
    }
  }, [fitMode, fitIframe, content]);

  const onWheel = useCallback((e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      setScale((s) => {
        const next = Math.max(0.2, Math.min(s * delta, 3));
        if (Math.abs(next - 1) < 0.05 && fitMode) return s;
        return next;
      });
      setFitMode(false);
    } else if (!fitMode) {
      e.preventDefault();
      setOffset((prev) => ({ x: prev.x - e.deltaX, y: prev.y - e.deltaY }));
    }
  }, [fitMode]);

  const onMouseDown = (e) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - offset.x, y: e.clientY - offset.y };
  };

  const onMouseMove = useCallback((e) => {
    if (!isDragging) return;
    setOffset({ x: e.clientX - dragStartRef.current.x, y: e.clientY - dragStartRef.current.y });
  }, [isDragging]);

  const onMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
      return () => {
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
      };
    }
  }, [isDragging, onMouseMove, onMouseUp]);

  return (
    <div
      className="html-preview"
      onWheel={onWheel}
      onDoubleClick={() => {
        setFitMode(true);
      }}
      style={{ cursor: isDragging ? 'grabbing' : fitMode ? 'default' : 'grab' }}
    >
      <div
        className="html-preview-scroll"
        ref={scrollRef}
        onMouseDown={onMouseDown}
        style={{
          width: '100%',
          overflowX: 'hidden',
          overflowY: 'auto',
          position: 'relative',
        }}
      >
        <div
          ref={transformRef}
          style={{
            width: sizeRef.current.w || '100%',
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
            transformOrigin: 'left top',
            transition: isDragging ? 'none' : 'transform 0.15s ease-out',
          }}
        >
          <iframe
            ref={iframeRef}
            title="html-preview"
            sandbox="allow-scripts"
            style={{
              width: '100%',
              minWidth: 400,
              height: Math.max(sizeRef.current.h || 600, 400),
              border: 'none',
              display: 'block',
            }}
          />
        </div>
      </div>
      {!fitMode && (
        <div className="html-preview-hint">
          滚轮平移 · Ctrl + 滚轮缩放 · 双击恢复适应宽度
        </div>
      )}
    </div>
  );
};

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
  'li { margin: 2pt 0; }',
  'table { width: 100%; border-collapse: collapse; margin: 8pt 0; }',
  'td, th { border: 1px solid #aaa; padding: 4pt 6pt; text-align: left; }',
  'blockquote { border-left: 4px solid #ccc; padding-left: 12pt; color: #555; margin: 8pt 0; }',
].join('\n');

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
          const hexString = (content || '').replace(/\s/g, '');
          const pairs = hexString.match(/.{1,2}/g);
          if (!pairs) throw new Error('Invalid hex content');
          byteArray = new Uint8Array(pairs.map((b) => parseInt(b, 16)));
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

const collectOrderedPptxEmbedIds = (slideXml) => {
  const ids = [];
  const seen = new Set();
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

const extractPptxSlideTexts = (slideXml) => {
  if (!slideXml) return [];
  const texts = [];

  const pushText = (raw) => {
    const t = decodeXmlEntities(raw).replace(/\s+/g, ' ').trim();
    if (t) texts.push(t);
  };

  const reAT = /<a:t[^>]*>([\s\S]*?)<\/a:t>/gi;
  let m;
  while ((m = reAT.exec(slideXml)) !== null) {
    pushText(m[1]);
  }

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

const PptxViewer = ({ file, content }) => {
  const [slides, setSlides] = useState([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const scrollContainerRef = useRef(null);
  const slideRefs = useRef([]);

  useEffect(() => {
    const loadPptx = async () => {
      try {
        setLoading(true);
        setError(null);

        let byteArray;
        if (file.encoding === 'hex') {
          const hexString = (content || '').replace(/\s/g, '');
          const pairs = hexString.match(/.{1,2}/g);
          if (!pairs) throw new Error('Invalid hex content');
          byteArray = new Uint8Array(pairs.map((byte) => parseInt(byte, 16)));
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

        const slideRefsList = [];
        const contentTypes = await zip.file('[Content_Types].xml')?.async('string');

        if (contentTypes) {
          const slideMatches = contentTypes.match(/PartName="\/ppt\/slides\/slide\d+\.xml"/g) || [];
          for (const match of slideMatches) {
            const slideNum = match.match(/slide(\d+)\.xml/)[1];
            slideRefsList.push(`ppt/slides/slide${slideNum}.xml`);
          }
        }

        if (slideRefsList.length === 0) {
          const allFiles = Object.keys(zip.files);
          for (const fileName of allFiles) {
            if (fileName.match(/ppt\/slides\/slide\d+\.xml$/)) {
              slideRefsList.push(fileName);
            }
          }
        }

        slideRefsList.sort((a, b) => {
          const numA = parseInt(a.match(/slide(\d+)/)[1], 10);
          const numB = parseInt(b.match(/slide(\d+)/)[1], 10);
          return numA - numB;
        });

        const slidesData = [];
        for (const slidePath of slideRefsList) {
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

  const thumbHtml = useMemo(() => {
    return slides.map((s, i) => buildSlidePreviewHtml(s.xml, i, s.imageDataUrls || []));
  }, [slides]);

  const scrollToSlide = useCallback((index) => {
    const slideElement = slideRefs.current[index];
    if (slideElement && scrollContainerRef.current) {
      slideElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container || slides.length === 0) return;

    const handleScroll = () => {
      const containerRect = container.getBoundingClientRect();
      const containerTop = containerRect.top;
      const containerHeight = containerRect.height;

      let closestSlide = 0;
      let minDistance = Infinity;

      slideRefs.current.forEach((slideEl, index) => {
        if (!slideEl) return;
        const slideRect = slideEl.getBoundingClientRect();
        const slideTop = slideRect.top - containerTop;
        const distance = Math.abs(slideTop);

        if (distance < minDistance) {
          minDistance = distance;
          closestSlide = index;
        }
      });

      setCurrentSlide(closestSlide);
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [slides.length]);

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
    <div className="pptx-preview pptx-scroll-mode">
      <div className="pptx-sidebar">
        <div className="pptx-sidebar-header">
          <span className="pptx-sidebar-title">Slides ({slides.length})</span>
        </div>
        <div className="pptx-thumbnails-scroll">
          {slides.map((slide, index) => (
            <div
              key={slide.path || index}
              className={`pptx-thumb ${currentSlide === index ? 'active' : ''}`}
              onClick={() => scrollToSlide(index)}
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
      <div className="pptx-content-scroll" ref={scrollContainerRef}>
        {slides.map((slide, index) => {
          const slideHtml = buildSlidePreviewHtml(slide.xml, index, slide.imageDataUrls || []);
          return (
            <div
              key={slide.path || index}
              ref={(el) => (slideRefs.current[index] = el)}
              className="pptx-slide-card"
            >
              <div
                className="pptx-slide-html"
                dangerouslySetInnerHTML={{
                  __html: slideHtml || '<div class="pptx-empty-hint">Loading…</div>',
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};

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

export {
  formatSize,
  hexToBase64,
  ImageViewer,
  XlsxViewer,
  PdfViewer,
  BinaryViewer,
  HtmlViewer,
  DocxViewer,
  PptxViewer,
  getLanguage,
};
