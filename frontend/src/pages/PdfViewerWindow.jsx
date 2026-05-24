import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  RotateCcw,
  X,
  Minus,
  Plus,
  MessageSquare,
  Underline,
} from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import { useWebSocket } from '../contexts/WebSocketContext';
import './PdfViewerWindow.css';

pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;

function parseHashParams() {
  const hash = window.location.hash;
  const queryIndex = hash.indexOf('?');
  const search = queryIndex !== -1 ? hash.slice(queryIndex + 1) : '';
  return new URLSearchParams(search);
}

const COLORS = [
  { name: 'Yellow', value: '#ffeb3b' },
  { name: 'Green', value: '#4caf50' },
  { name: 'Blue', value: '#2196f3' },
  { name: 'Pink', value: '#e91e63' },
  { name: 'Orange', value: '#ff9800' },
];

// Single page with lazy rendering via IntersectionObserver
const PdfPage = React.memo(({ pdf, pageNumber, scale, annotations, onVisible, onTextSelect }) => {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const textLayerRef = useRef(null);
  const renderTaskRef = useRef(null);
  const [rendered, setRendered] = useState(false);
  const [viewportSize, setViewportSize] = useState(null);

  // Compute viewport size once per scale change
  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    pdf.getPage(pageNumber).then((page) => {
      if (cancelled) return;
      const vp = page.getViewport({ scale });
      setViewportSize({ width: vp.width, height: vp.height });
    });
    return () => { cancelled = true; };
  }, [pdf, pageNumber, scale]);

  // IntersectionObserver: render when near viewport, track visibility
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          onVisible(pageNumber);
          if (!rendered && viewportSize && canvasRef.current) {
            doRender();
          }
        }
      },
      { rootMargin: '400px' }
    );
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [viewportSize, rendered, pageNumber, onVisible]);

  // Re-render when scale changes
  useEffect(() => {
    if (rendered && viewportSize && canvasRef.current) {
      doRender();
    }
  }, [scale]); // eslint-disable-line react-hooks/exhaustive-deps

  const doRender = async () => {
    if (!pdf || !canvasRef.current || !viewportSize) return;
    try {
      if (renderTaskRef.current) {
        try { renderTaskRef.current.cancel(); } catch {}
      }
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale });
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');
      const dpr = window.devicePixelRatio || 1;
      canvas.width = viewport.width * dpr;
      canvas.height = viewport.height * dpr;
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      renderTaskRef.current = page.render({ canvasContext: context, viewport });
      await renderTaskRef.current.promise;

      if (textLayerRef.current) {
        textLayerRef.current.innerHTML = '';
        textLayerRef.current.style.setProperty('--scale-factor', String(viewport.scale));
        const textContent = await page.getTextContent();
        const textLayer = new pdfjsLib.TextLayer({
          container: textLayerRef.current,
          textContentSource: textContent,
          viewport,
        });
        await textLayer.render();
        const spans = textLayerRef.current.querySelectorAll('span');
        spans.forEach((span, i) => {
          span.dataset.spanIndex = String(i);
        });
      }
      setRendered(true);
    } catch (err) {
      if (err.name !== 'RenderingCancelledException') {
        console.error('Failed to render page', pageNumber, err);
      }
    }
  };

  const handleMouseUp = (e) => {
    onTextSelect(e, pageNumber, textLayerRef.current);
  };

  const pageAnnotations = annotations.filter((a) => a.page === pageNumber);

  return (
    <div
      ref={containerRef}
      data-page-number={pageNumber}
      className="pdfv-scroll-page"
      style={{
        width: viewportSize ? viewportSize.width : 600,
        height: viewportSize ? viewportSize.height : 800,
        position: 'relative',
        background: 'white',
        boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
        marginBottom: 16,
      }}
      onMouseUp={handleMouseUp}
    >
      <canvas ref={canvasRef} className="pdfv-canvas" />
      <div ref={textLayerRef} className="pdfv-textlayer" />

      {/* Highlight layer */}
      <div className="pdfv-highlight-layer">
        {pageAnnotations.map((annot) => (
          <div key={annot.id}>
            {annot.rects && annot.rects.map((rect, idx) => (
              <div
                key={idx}
                className={`pdfv-highlight ${annot.type}`}
                style={{
                  left: rect.left,
                  top: rect.top,
                  width: rect.width,
                  height: rect.height,
                  backgroundColor: annot.type === 'highlight' ? annot.color : 'transparent',
                  opacity: annot.type === 'highlight' ? 0.35 : 1,
                  mixBlendMode: annot.type === 'highlight' ? 'multiply' : 'normal',
                  borderBottom: annot.type === 'underline'
                    ? `2px solid ${annot.color}`
                    : 'none',
                }}
              />
            ))}
          </div>
        ))}
      </div>

      {!rendered && viewportSize && (
        <div className="pdfv-page-overlay">Rendering…</div>
      )}
    </div>
  );
});

const PdfViewerWindow = () => {
  const params = parseHashParams();
  const pdfPath = params.get('path');
  const pdfTitle = params.get('title') || 'PDF Viewer';
  const itemId = params.get('itemId');

  const { sendMessage } = useWebSocket();

  const [pdf, setPdf] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale, setScale] = useState(1.5);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [annotations, setAnnotations] = useState([]);
  const [selectedAnnotationId, setSelectedAnnotationId] = useState(null);
  const [showSidebar, setShowSidebar] = useState(false);
  const [selection, setSelection] = useState(null);
  const [showToolbar, setShowToolbar] = useState(false);
  const [toolbarPos, setToolbarPos] = useState({ x: 0, y: 0 });

  const contentRef = useRef(null);
  const annotationsRef = useRef(annotations);
  annotationsRef.current = annotations;

  // Load saved annotations from SQLite (priority) > localStorage fallback
  useEffect(() => {
    if (!itemId) {
      // Fallback: localStorage for legacy / direct URL access
      const key = `pdf-annotations:${pdfPath}/main.pdf`;
      const saved = localStorage.getItem(key);
      if (saved) {
        try { setAnnotations(JSON.parse(saved)); } catch {}
      }
      return;
    }
    let cancelled = false;
    const loadAnnotations = async () => {
      try {
        const response = await sendMessage('library_annotations_load', { item_id: Number(itemId) }, 10000);
        if (response?.data?.annotations && !cancelled) {
          setAnnotations(response.data.annotations);
        }
      } catch (e) {
        // Fallback to localStorage on error
        const key = `pdf-annotations:${pdfPath}/main.pdf`;
        const saved = localStorage.getItem(key);
        if (saved && !cancelled) {
          try { setAnnotations(JSON.parse(saved)); } catch {}
        }
      }
    };
    loadAnnotations();
    return () => { cancelled = true; };
  }, [itemId, pdfPath, sendMessage]);

  // Save annotations to SQLite (and localStorage as local cache)
  useEffect(() => {
    if (!itemId) {
      const key = `pdf-annotations:${pdfPath}/main.pdf`;
      if (annotations.length > 0) localStorage.setItem(key, JSON.stringify(annotations));
      else localStorage.removeItem(key);
      return;
    }
    const timeout = setTimeout(() => {
      sendMessage('library_annotations_save', {
        item_id: Number(itemId),
        annotations,
      }, 10000).catch(() => {});
    }, 500);
    // Keep localStorage as local cache
    const key = `pdf-annotations:${pdfPath}/main.pdf`;
    if (annotations.length > 0) localStorage.setItem(key, JSON.stringify(annotations));
    else localStorage.removeItem(key);
    return () => clearTimeout(timeout);
  }, [annotations, itemId, pdfPath, sendMessage]);

  // Load PDF
  useEffect(() => {
    if (!pdfPath) {
      setError('No PDF path provided');
      setLoading(false);
      return;
    }
    let cancelled = false;
    const loadPdf = async () => {
      setLoading(true);
      setError(null);
      try {
        const pdfFilePath = `${pdfPath}/main.pdf`;
        const response = await sendMessage('workspace_read', { path: pdfFilePath }, 30000);
        if (!response?.data?.content) throw new Error('No PDF content');
        let bytes;
        const encoding = response.data.encoding || 'hex';
        if (encoding === 'hex') {
          const hex = response.data.content.replace(/\s/g, '');
          bytes = new Uint8Array(hex.match(/.{1,2}/g).map((b) => parseInt(b, 16)));
        } else {
          const binary = atob(response.data.content);
          bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        }
        const pdfDocument = await pdfjsLib.getDocument({ data: bytes }).promise;
        if (!cancelled) {
          setPdf(pdfDocument);
          setNumPages(pdfDocument.numPages);
          setCurrentPage(1);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load PDF:', err);
          setError(err.message || 'Failed to load PDF');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadPdf();
    return () => { cancelled = true; };
  }, [pdfPath, sendMessage]);

  // Track which page is currently most visible
  const onPageVisible = useCallback((pageNum) => {
    setCurrentPage(pageNum);
  }, []);

  // Text selection across any page
  const onTextSelect = useCallback((e, pageNumber, textLayerEl) => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !textLayerEl) {
      setShowToolbar(false);
      return;
    }
    const text = sel.toString().trim();
    if (!text) {
      setShowToolbar(false);
      return;
    }
    const range = sel.getRangeAt(0);
    const rawRects = Array.from(range.getClientRects());
    const textLayerRect = textLayerEl.getBoundingClientRect();

    // Merge rects by row
    const rows = new Map();
    rawRects.forEach((r) => {
      const key = Math.round(r.top);
      const existing = rows.get(key);
      if (existing) {
        existing.left = Math.min(existing.left, r.left);
        existing.right = Math.max(existing.right, r.right);
        existing.top = Math.min(existing.top, r.top);
        existing.bottom = Math.max(existing.bottom, r.bottom);
      } else {
        rows.set(key, { left: r.left, right: r.right, top: r.top, bottom: r.bottom });
      }
    });
    const sortedRows = Array.from(rows.values()).sort((a, b) => a.top - b.top);
    for (let i = 0; i < sortedRows.length - 1; i++) {
      if (sortedRows[i].bottom > sortedRows[i + 1].top) {
        sortedRows[i].bottom = sortedRows[i + 1].top;
      }
    }
    const mappedRects = sortedRows.map((r) => ({
      left: r.left - textLayerRect.left,
      top: r.top - textLayerRect.top,
      width: r.right - r.left,
      height: r.bottom - r.top,
    }));

    // Span range tracking
    let startNode = range.startContainer;
    let endNode = range.endContainer;
    if (startNode.nodeType === Node.TEXT_NODE) startNode = startNode.parentElement;
    if (endNode.nodeType === Node.TEXT_NODE) endNode = endNode.parentElement;
    const startSpan = startNode.closest ? startNode.closest('span[data-span-index]') : null;
    const endSpan = endNode.closest ? endNode.closest('span[data-span-index]') : null;
    let spanRange = null;
    if (startSpan && endSpan && textLayerEl.contains(startSpan)) {
      spanRange = {
        start: parseInt(startSpan.dataset.spanIndex, 10),
        end: parseInt(endSpan.dataset.spanIndex, 10),
      };
    }

    setSelection({ text, rects: mappedRects, spanRange, page: pageNumber });

    if (rawRects.length > 0) {
      const lastRect = rawRects[rawRects.length - 1];
      setToolbarPos({ x: lastRect.right, y: lastRect.top });
    } else {
      setToolbarPos({ x: e.clientX, y: Math.max(e.clientY - 56, 8) });
    }
    setShowToolbar(true);
  }, []);

  const addHighlight = useCallback((color) => {
    if (!selection) return;
    window.getSelection().removeAllRanges();
    const annotation = {
      id: `annot-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
      page: selection.page,
      type: 'highlight',
      color,
      text: selection.text,
      comment: '',
      rects: selection.rects,
      spanRange: selection.spanRange,
      createdAt: Date.now(),
    };
    setAnnotations((prev) => [...prev, annotation]);
    setShowToolbar(false);
    setSelection(null);
  }, [selection]);

  const addUnderline = useCallback((color) => {
    if (!selection) return;
    window.getSelection().removeAllRanges();
    const annotation = {
      id: `annot-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
      page: selection.page,
      type: 'underline',
      color,
      text: selection.text,
      comment: '',
      rects: selection.rects,
      spanRange: selection.spanRange,
      createdAt: Date.now(),
    };
    setAnnotations((prev) => [...prev, annotation]);
    setShowToolbar(false);
    setSelection(null);
  }, [selection]);

  const updateComment = useCallback((id, comment) => {
    setAnnotations((prev) => prev.map((a) => (a.id === id ? { ...a, comment } : a)));
  }, []);

  const deleteAnnotation = useCallback((id) => {
    setAnnotations((prev) => prev.filter((a) => a.id !== id));
    if (selectedAnnotationId === id) setSelectedAnnotationId(null);
  }, [selectedAnnotationId]);

  const zoomIn = useCallback(() => setScale((s) => Math.min(s + 0.25, 3)), []);
  const zoomOut = useCallback(() => setScale((s) => Math.max(s - 0.25, 0.5)), []);
  const resetZoom = useCallback(() => setScale(1.5), []);
  const handleClose = useCallback(() => window.close(), []);

  const scrollToPage = useCallback((pageNum) => {
    const el = document.querySelector(`[data-page-number="${pageNum}"]`);
    if (el && contentRef.current) {
      contentRef.current.scrollTo({ top: el.offsetTop - 20, behavior: 'smooth' });
    }
  }, []);

  const handleKeyDown = useCallback((e) => {
    if (e.key === '+' || e.key === '=') zoomIn();
    if (e.key === '-') zoomOut();
  }, [zoomIn, zoomOut]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    const handleClick = (e) => {
      if (showToolbar && !e.target.closest('.pdfv-selection-toolbar')) {
        setShowToolbar(false);
        window.getSelection().removeAllRanges();
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showToolbar]);

  if (loading) {
    return (
      <div className="pdfv-loading">
        <div className="pdfv-spinner" />
        <span>Loading PDF…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pdfv-error">
        <span className="pdfv-error-icon">⚠</span>
        <span>{error}</span>
      </div>
    );
  }

  return (
    <div className="pdfv-root">
      {/* Toolbar */}
      <div className="pdfv-toolbar">
        <div className="pdfv-toolbar-left">
          <span className="pdfv-title">{decodeURIComponent(pdfTitle)}</span>
        </div>
        <div className="pdfv-toolbar-center">
          <span className="pdfv-pageinfo">{currentPage} / {numPages}</span>
        </div>
        <div className="pdfv-toolbar-right">
          <button className="pdfv-btn" onClick={zoomOut} title="Zoom out (-)"><Minus size={14} /></button>
          <button className="pdfv-btn" onClick={resetZoom} title="Reset zoom"><RotateCcw size={14} /></button>
          <span className="pdfv-zoominfo">{Math.round(scale * 100)}%</span>
          <button className="pdfv-btn" onClick={zoomIn} title="Zoom in (+)"><Plus size={14} /></button>
          <button
            className={`pdfv-btn ${showSidebar ? 'pdfv-btn-active' : ''}`}
            onClick={() => setShowSidebar((s) => !s)}
            title="Annotations"
            style={{ position: 'relative' }}
          >
            <MessageSquare size={16} />
            {annotations.length > 0 && (
              <span className="pdfv-badge">{annotations.length}</span>
            )}
          </button>
          <button className="pdfv-btn pdfv-btn-close" onClick={handleClose} title="Close"><X size={16} /></button>
        </div>
      </div>

      {/* Main */}
      <div className="pdfv-main">
        <div className="pdfv-content" ref={contentRef}>
          {Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
            <PdfPage
              key={pageNum}
              pdf={pdf}
              pageNumber={pageNum}
              scale={scale}
              annotations={annotations}
              onVisible={onPageVisible}
              onTextSelect={onTextSelect}
            />
          ))}
        </div>

        {/* Sidebar */}
        {showSidebar && (
          <div className="pdfv-sidebar">
            <div className="pdfv-sidebar-header">
              <span>Annotations ({annotations.length})</span>
              <button className="pdfv-btn" onClick={() => setShowSidebar(false)}><X size={14} /></button>
            </div>
            <div className="pdfv-sidebar-content">
              {annotations.length === 0 ? (
                <div className="pdfv-sidebar-empty">Select text and highlight to add annotations</div>
              ) : (
                annotations.map((annot) => (
                  <div
                    key={annot.id}
                    className={`pdfv-annot-item ${selectedAnnotationId === annot.id ? 'pdfv-annot-item-selected' : ''}`}
                    onClick={() => {
                      setSelectedAnnotationId(annot.id);
                      scrollToPage(annot.page);
                    }}
                  >
                    <div className="pdfv-annot-meta">
                      <span className="pdfv-annot-page">Page {annot.page}</span>
                      <span className="pdfv-annot-type">{annot.type}</span>
                    </div>
                    <div className="pdfv-annot-text">"{annot.text}"</div>
                    <textarea
                      className="pdfv-annot-comment"
                      placeholder="Add a comment..."
                      value={annot.comment}
                      onChange={(e) => updateComment(annot.id, e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                    />
                    <button className="pdfv-annot-delete" onClick={() => deleteAnnotation(annot.id)}>Delete</button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* Selection toolbar */}
      {showToolbar && selection && (
        <div
          className="pdfv-selection-toolbar"
          style={{ left: toolbarPos.x, top: toolbarPos.y }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="pdfv-color-picker">
            {COLORS.map((c) => (
              <button
                key={c.name}
                className="pdfv-color-btn"
                style={{ backgroundColor: c.value }}
                title={`Highlight ${c.name}`}
                onClick={() => addHighlight(c.value)}
              />
            ))}
          </div>
          <div className="pdfv-toolbar-divider" />
          <button className="pdfv-toolbar-action" onClick={() => addUnderline(COLORS[2].value)} title="Underline">
            <Underline size={14} />
          </button>
        </div>
      )}
    </div>
  );
};

export default PdfViewerWindow;
