import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  RotateCcw,
  X,
  Minus,
  Plus,
  MessageSquare,
  Underline,
  Bot,
  Send,
  Trash2,
  Sparkles,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  Network,
  StickyNote,
  BookOpen,
} from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import { useWebSocket } from '../contexts/WebSocketContext';
import { usePdfChat } from './Knowledge/library/hooks/usePdfChat';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import MermaidDiagram from '../components/MermaidDiagram';
import MindmapDiagram from '../components/MindmapDiagram';
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

// Resolve a PDF outline (bookmark tree) into a plain array of { title, pageNumber, items }.
// `pdf.getOutline()` may return either string-named destinations or arrays of refs;
// we always normalise via `pdf.getDestination(dest)` and `pdf.getPageIndex(ref)`,
// which gives a 0-based page index that we bump to 1-based for display/jump.
async function resolveOutlineDest(pdf, dest) {
  try {
    if (!dest) return null;
    const d = typeof dest === 'string' ? await pdf.getDestination(dest) : dest;
    if (!d || !d[0]) return null;
    const idx = await pdf.getPageIndex(d[0]);
    return idx + 1; // 1-based
  } catch {
    return null;
  }
}

async function resolveOutline(pdf, items) {
  if (!items || items.length === 0) return [];
  return Promise.all(
    items.map(async (it) => ({
      title: it.title || '(untitled)',
      pageNumber: await resolveOutlineDest(pdf, it.dest),
      items: await resolveOutline(pdf, it.items || []),
    })),
  );
}

// Recursive TOC tree for the right-hand sidebar.
function TocTree({ items, depth = 0, currentPage, onJump }) {
  const [expanded, setExpanded] = useState(() => new Set());
  const { t } = useTranslation();
  if (!items || items.length === 0) {
    return <div className="pdfv-sidebar-empty">{t('pdfViewer.tocEmpty')}</div>;
  }
  const toggle = (key) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };
  return (
    <>
      {items.map((it, i) => {
        const key = `${depth}-${i}`;
        const hasChildren = it.items && it.items.length > 0;
        const isOpen = expanded.has(key);
        const isActive = currentPage === it.pageNumber;
        return (
          <div key={key} className="pdfv-toc-node">
            <div
              className={`pdfv-toc-item ${isActive ? 'pdfv-toc-item-active' : ''}`}
              style={{ paddingLeft: 12 + depth * 14 }}
              onClick={() => {
                if (hasChildren) toggle(key);
                if (it.pageNumber) onJump(it.pageNumber);
              }}
              title={it.title}
            >
              {hasChildren ? (
                <span
                  className="pdfv-toc-chevron"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggle(key);
                  }}
                >
                  {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                </span>
              ) : (
                <span className="pdfv-toc-bullet" />
              )}
              <span className="pdfv-toc-title">{it.title}</span>
              {it.pageNumber && <span className="pdfv-toc-page">{it.pageNumber}</span>}
            </div>
            {hasChildren && isOpen && (
              <TocTree
                items={it.items}
                depth={depth + 1}
                currentPage={currentPage}
                onJump={onJump}
              />
            )}
          </div>
        );
      })}
    </>
  );
}

// Single page with lazy rendering via IntersectionObserver
const PdfPage = React.memo(({ pdf, pageNumber, scale, annotations, onVisible, onTextSelect }) => {
  const { t } = useTranslation();
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
                data-annotation-id={annot.id}
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
        <div className="pdfv-page-overlay">{t('pdfViewer.rendering')}</div>
      )}
    </div>
  );
});

/**
 * AnnotationComments — thread-style comment UI for a single annotation.
 *
 * Replaces the legacy single `<textarea value={annot.comment}>` field. Shows
 * existing comments as cards; composing is opt-in via a ➕ button (a deliberate
 * shift from the modal's persistent textarea so the sidebar stays compact).
 *
 * Optimistic annotations (no db id yet) cannot post comments because the
 * `library_annotation_comments_*` RPC requires an integer annotation_id.
 * In that state the ➕ button is disabled with an explanatory tooltip.
 *
 * Stateless w.r.t. parent state — receives `onAddComment` / `onDeleteComment`
 * callbacks so the parent keeps its single source of truth.
 */
const AnnotationComments = ({ annot, onAddComment, onDeleteComment }) => {
  const { t } = useTranslation();
  const comments = Array.isArray(annot.comments) ? annot.comments : [];
  const hasDbId = typeof annot.id === 'number';
  const annotKey = String(annot.id ?? annot.client_id ?? '');

  const [draft, setDraft] = useState('');
  const [composing, setComposing] = useState(false);
  const [busy, setBusy] = useState(false);

  const formatTime = (ts) => {
    if (!ts) return '';
    const d = new Date(ts);
    return isNaN(d.getTime()) ? '' : d.toLocaleString();
  };

  const openCompose = () => {
    setDraft('');
    setComposing(true);
  };

  const cancelCompose = () => {
    setDraft('');
    setComposing(false);
  };

  const submitComment = async () => {
    const content = draft.trim();
    if (!content || busy) return;
    setBusy(true);
    try {
      const newComment = await onAddComment(annotKey, content);
      if (newComment) {
        setDraft('');
        setComposing(false);
      }
    } catch (e) {
      console.error('Failed to post comment:', e);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (commentId, isPending) => {
    if (busy) return;
    setBusy(true);
    try {
      await onDeleteComment(annotKey, commentId, isPending);
    } catch (e) {
      console.error('Failed to delete comment:', e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pdfv-annot-comments" data-annot-key={annotKey}>
      {comments.length === 0 && !composing && (
        <div className="pdfv-annot-comments-empty">
          {t('annotation.noComments')}
        </div>
      )}

      {comments.length > 0 && (
        <div className="pdfv-annot-comments-list">
          {comments.map((c) => {
            const isPending = !!c._pending;
            return (
              <div
                key={c.id ?? c._localId}
                className={`pdfv-annot-comment-card${isPending ? ' pdfv-annot-comment-card-pending' : ''}`}
              >
                <div className="pdfv-annot-comment-card-head">
                  <span className="pdfv-annot-comment-author">
                    {c.author_name || t('annotation.authorYou')}
                  </span>
                  {c.created_at && (
                    <span className="pdfv-annot-comment-time">
                      {formatTime(c.created_at)}
                    </span>
                  )}
                  {isPending && (
                    <span className="pdfv-annot-comment-pending">
                      {c._pending === 'failed'
                        ? t('annotation.commentSyncFailed')
                        : t('annotation.commentSyncing')}
                    </span>
                  )}
                </div>
                <div className="pdfv-annot-comment-body">{c.content}</div>
                <button
                  className="pdfv-annot-comment-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(c.id ?? c._localId, isPending);
                  }}
                  disabled={busy}
                  title={t('annotation.deleteComment')}
                >
                  <Trash2 size={11} />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {composing ? (
        <div className="pdfv-annot-comments-composer">
          <textarea
            className="pdfv-annot-comments-input"
            placeholder={t('annotation.addCommentPlaceholder')}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submitComment();
              } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelCompose();
              }
            }}
            autoFocus
            rows={2}
          />
          <div className="pdfv-annot-comments-actions">
            <button
              className="pdfv-annot-comments-cancel"
              onClick={(e) => {
                e.stopPropagation();
                cancelCompose();
              }}
              disabled={busy}
              title={t('annotation.cancelComment')}
            >
              <X size={12} />
              {t('annotation.cancelComment')}
            </button>
            <button
              className="pdfv-annot-comments-confirm"
              onClick={(e) => {
                e.stopPropagation();
                submitComment();
              }}
              disabled={busy || !draft.trim()}
              title={t('annotation.confirmComment')}
            >
              <Check size={12} />
              {t('annotation.confirmComment')}
            </button>
          </div>
        </div>
      ) : (
        <button
          className="pdfv-annot-comments-add"
          onClick={(e) => {
            e.stopPropagation();
            openCompose();
          }}
          title={
            hasDbId
              ? t('annotation.addCommentPlaceholder')
              : t('annotation.commentPendingSync')
          }
        >
          <Plus size={12} />
          {t('annotation.addComment')}
        </button>
      )}
    </div>
  );
};

const PdfViewerWindow = () => {
  const { t } = useTranslation();
  const params = parseHashParams();
  const pdfPath = params.get('path');
  const pdfTitle = params.get('title') || 'PDF Viewer';
  const itemId = params.get('itemId');

  const { sendMessage, subscribe, unsubscribe } = useWebSocket();

  const [pdf, setPdf] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale, setScale] = useState(1.5);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [annotations, setAnnotations] = useState([]);
  const [selectedAnnotationId, setSelectedAnnotationId] = useState(null);
  const [showSidebar, setShowSidebar] = useState(false);
  // Outline (TOC) panel on the LEFT side — independent of the right-side
  // annotations sidebar so the user can keep both open simultaneously.
  const [showOutline, setShowOutline] = useState(true);
  // Outline fetched from pdf.getOutline(); null while loading / unavailable.
  const [outline, setOutline] = useState(null);
  const [selection, setSelection] = useState(null);
  const [showToolbar, setShowToolbar] = useState(false);
  const [toolbarPos, setToolbarPos] = useState({ x: 0, y: 0 });

  // ── Chat Drawer ──
  const [showChatDrawer, setShowChatDrawer] = useState(false);
  // null = "All annotations"; a positive int = lock chat drawer to that annotation id
  const [chatAnnotationFilter, setChatAnnotationFilter] = useState(null);
  const chatInputRef = useRef(null);
  // Custom dropdown UI state for the annotation filter
  const [isAnnotationFilterOpen, setIsAnnotationFilterOpen] = useState(false);
  const annotationFilterTriggerRef = useRef(null);
  const annotationFilterPanelRef = useRef(null);

  // Reading-position resume: read on mount, debounce-write on currentPage change.
  // `positionRestoredRef` guards the save effect so the initial setCurrentPage(1)
  // during PDF load doesn't clobber a previously-saved page.
  const positionRestoredRef = useRef(false);
  const savePositionTimerRef = useRef(null);

  // Pending comments queued against an optimistic annotation. Maps
  // client_id (string) → [{ localId, content }]. Flushed to the backend
  // once library_annotation_upsert returns with the real numeric id.
  // Persisted to localStorage so a window-close mid-flush doesn't lose the
  // comment — see persistPendingComments / replayPendingComments below.
  const pendingCommentsByClientIdRef = useRef(new Map());
  const pendingCommentsStorageKey = itemId ? `pdf-pending-comments:${itemId}` : null;

  // Annotation ↔ chat session binding. Each annotation should reuse the same
  // chat session across reopens ("对此批注对话" should not keep creating new
  // threads). `pdf_chat_sessions` doesn't carry an annotation_id column, so
  // we maintain this binding client-side, persisted to localStorage keyed by
  // pdfPath so re-opening the same PDF restores the same mapping.
  // Value: { sessionId: number, updatedAt: number } — updatedAt lets us age
  // out bindings to deleted sessions.
  const annotationSessionMapRef = useRef(new Map());
  const annotationSessionMapStorageKey = pdfPath
    ? `pdf-chat-session-map:${pdfPath}`
    : null;

  const persistPendingComments = useCallback(() => {
    if (!pendingCommentsStorageKey) return;
    const map = {};
    for (const [cid, queue] of pendingCommentsByClientIdRef.current.entries()) {
      if (queue.length > 0) map[cid] = queue;
    }
    if (Object.keys(map).length === 0) {
      localStorage.removeItem(pendingCommentsStorageKey);
    } else {
      try {
        localStorage.setItem(pendingCommentsStorageKey, JSON.stringify(map));
      } catch (e) {
        console.warn('Failed to persist pending comments:', e);
      }
    }
  }, [pendingCommentsStorageKey]);

  // Post queued optimistic comments to the backend now that the parent annotation
  // has a real numeric id. Each pending comment is swapped in-place (matched by
  // `_localId`) so the UI doesn't reorder the thread. On failure we mark the
  // comment `_pending: 'failed'` and keep it in the queue (persisted) so the
  // user can retry.
  const flushPendingComments = useCallback(
    async (clientId, dbId) => {
      const queue = pendingCommentsByClientIdRef.current.get(clientId);
      if (!queue || queue.length === 0) return;

      const failedEntries = [];
      for (const entry of queue) {
        const { localId, content } = entry;
        try {
          const resp = await sendMessage(
            'library_annotation_comments_add',
            { annotation_id: dbId, content },
            10000,
          );
          const real = resp?.data?.comment;
          if (!real) {
            failedEntries.push(entry);
            continue;
          }
          setAnnotations((prev) =>
            prev.map((a) =>
              a.id === dbId
                ? {
                    ...a,
                    comments: (a.comments || []).map((c) =>
                      c._localId === localId
                        ? { ...real, _localId: undefined, _pending: undefined, _clientId: undefined }
                        : c,
                    ),
                  }
                : a,
            ),
          );
        } catch (e) {
          console.error('Failed to flush pending comment:', e);
          // Mark as failed so the UI can react if desired.
          setAnnotations((prev) =>
            prev.map((a) =>
              a.id === dbId
                ? {
                    ...a,
                    comments: (a.comments || []).map((c) =>
                      c._localId === localId ? { ...c, _pending: 'failed' } : c,
                    ),
                  }
                : a,
            ),
          );
          failedEntries.push(entry);
        }
      }

      // Persist the post-flush queue (drop successful entries, keep failures
      // so they can be retried on next open / upsert).
      if (failedEntries.length > 0) {
        pendingCommentsByClientIdRef.current.set(clientId, failedEntries);
        persistPendingComments();
      } else {
        pendingCommentsByClientIdRef.current.delete(clientId);
        persistPendingComments();
      }
    },
    [sendMessage, persistPendingComments],
  );

  const clearPendingCommentsFor = useCallback(
    (clientId) => {
      pendingCommentsByClientIdRef.current.delete(clientId);
      persistPendingComments();
    },
    [persistPendingComments],
  );

  // ── Annotation ↔ chat session binding helpers ──
  // Loaded eagerly on mount from localStorage so the first "对此批注对话"
  // click after reopening the PDF still finds the same session.
  useEffect(() => {
    if (!annotationSessionMapStorageKey) return;
    try {
      const raw = localStorage.getItem(annotationSessionMapStorageKey);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        annotationSessionMapRef.current = new Map(
          Object.entries(parsed).map(([aid, val]) => [
            aid,
            { sessionId: val.sessionId, updatedAt: val.updatedAt ?? 0 },
          ]),
        );
      }
    } catch {}
  }, [annotationSessionMapStorageKey]);

  const persistAnnotationSessionMap = useCallback(() => {
    if (!annotationSessionMapStorageKey) return;
    const obj = {};
    for (const [aid, val] of annotationSessionMapRef.current.entries()) {
      obj[aid] = val;
    }
    try {
      localStorage.setItem(
        annotationSessionMapStorageKey,
        JSON.stringify(obj),
      );
    } catch {}
  }, [annotationSessionMapStorageKey]);

  const bindAnnotationToSession = useCallback(
    (annotationId, sessionId) => {
      if (annotationId == null || sessionId == null) return;
      annotationSessionMapRef.current.set(String(annotationId), {
        sessionId,
        updatedAt: Date.now(),
      });
      persistAnnotationSessionMap();
    },
    [persistAnnotationSessionMap],
  );

  const unbindAnnotationSession = useCallback(
    (annotationId) => {
      if (annotationId == null) return;
      annotationSessionMapRef.current.delete(String(annotationId));
      persistAnnotationSessionMap();
    },
    [persistAnnotationSessionMap],
  );

  // Resolve a usable session id for an annotation id. Returns the cached one
  // if it still exists in `chatSessions`; otherwise returns null (caller
  // should create a new session and bind it).
  const resolveSessionForAnnotation = useCallback(
    (annotationId, currentSessions) => {
      if (annotationId == null) return null;
      const entry = annotationSessionMapRef.current.get(String(annotationId));
      if (!entry) return null;
      const sessionStillExists = currentSessions.some(
        (s) => s.id === entry.sessionId,
      );
      if (!sessionStillExists) {
        // The bound session was deleted on the server — drop the stale
        // binding so the next click creates a fresh one.
        annotationSessionMapRef.current.delete(String(annotationId));
        persistAnnotationSessionMap();
        return null;
      }
      return entry.sessionId;
    },
    [persistAnnotationSessionMap],
  );

  // Replay any pending comments persisted from a previous session — happens
  // when the user closed the PDF window mid-flush (before the optimistic
  // annotation had a real db id, or before the comments_add RPC returned).
  //
  // For each {clientId -> [{localId, content}]} entry:
  //   1. Try to find the annotation by client_id in the loaded set.
  //   2. If found and now persisted (numeric id): add optimistic comments back
  //      to the UI thread, re-queue them in the ref. Caller is responsible
  //      for invoking flushPendingComments(clientId, dbId) afterwards to
  //      actually post them to the backend.
  //   3. If not yet persisted (annotation itself was lost): just drop the
  //      queue — there's nowhere to attach it.
  //   4. Dedup against already-synced comments by content + timestamp proximity
  //      so we don't re-post if the server actually persisted it on the prior
  //      flush attempt (e.g. RPC ack was lost mid-flight).
  //
  // Returns the list of (clientId, dbId) pairs whose queues still need to be
  // flushed — caller must invoke flushPendingComments for each.
  const replayPendingComments = useCallback(() => {
    if (!pendingCommentsStorageKey) return [];
    const raw = localStorage.getItem(pendingCommentsStorageKey);
    if (!raw) return [];
    let map;
    try {
      map = JSON.parse(raw);
    } catch {
      localStorage.removeItem(pendingCommentsStorageKey);
      return [];
    }
    if (!map || typeof map !== 'object') return [];
    const current = annotationsRef.current;
    const toFlush = [];
    for (const [clientId, queue] of Object.entries(map)) {
      if (!Array.isArray(queue) || queue.length === 0) continue;
      const annot = current.find((a) => a.client_id === clientId);
      // Annotation lost — drop the queue.
      if (!annot) continue;

      // Existing comments on this annotation (post-load from DB).
      const existing = Array.isArray(annot.comments) ? annot.comments : [];

      if (typeof annot.id === 'number') {
        // Dedup: skip entries that already match a real comment by content +
        // timestamp proximity (within 60s — covers cases where the flush ack
        // was lost but the comment did reach the server).
        const freshEntries = queue.filter((entry) => {
          return !existing.some(
            (c) =>
              c.content === entry.content &&
              c.created_at &&
              Math.abs(
                (c.created_at > 1e12 ? c.created_at : c.created_at * 1000) -
                  (entry.createdAt ?? 0),
              ) < 60000,
          );
        });
        if (freshEntries.length === 0) continue;

        // Re-add optimistic cards to the UI thread and re-queue.
        setAnnotations((prev) =>
          prev.map((a) =>
            a.client_id === clientId
              ? {
                  ...a,
                  comments: [
                    ...(a.comments || []),
                    ...freshEntries.map((entry) => ({
                      _localId: entry.localId,
                      _pending: true,
                      _clientId: clientId,
                      content: entry.content,
                      author_name: t('annotation.authorYou'),
                      created_at: entry.createdAt ?? Date.now(),
                    })),
                  ],
                }
              : a,
          ),
        );
        const refQueue =
          pendingCommentsByClientIdRef.current.get(clientId) || [];
        for (const entry of freshEntries) refQueue.push(entry);
        pendingCommentsByClientIdRef.current.set(clientId, refQueue);
        toFlush.push([clientId, annot.id]);
        // Note: flushPendingComments will persist its own post-state.
      } else {
        // Annotation still optimistic (somehow — shouldn't happen after load,
        // but safe to handle). Keep the queue intact for the upsert handler.
        const refQueue =
          pendingCommentsByClientIdRef.current.get(clientId) || [];
        for (const entry of queue) refQueue.push(entry);
        pendingCommentsByClientIdRef.current.set(clientId, refQueue);
      }
    }
    return toFlush;
  }, [pendingCommentsStorageKey, t]);

  // ── Resizable panels ──
  const [chatDrawerWidth, setChatDrawerWidth] = useState(360);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  // Outline panel sits on the LEFT — when the user drags its right edge to
  // resize, the cursor moves right-to-left, so the delta sign matches the
  // sidebar (startX - e.clientX = positive when shrinking the panel).
  const [outlineWidth, setOutlineWidth] = useState(260);
  const resizeStateRef = useRef(null);

  const startResize = useCallback((e, panel) => {
    e.preventDefault();
    const startWidth =
      panel === 'chat' ? chatDrawerWidth
      : panel === 'outline' ? outlineWidth
      : sidebarWidth;
    resizeStateRef.current = {
      panel,
      startX: e.clientX,
      startWidth,
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [chatDrawerWidth, sidebarWidth, outlineWidth]);

  useEffect(() => {
    const handleMove = (e) => {
      const state = resizeStateRef.current;
      if (!state) return;
      // For 'outline' (left panel) dragging right grows the panel, so the
      // delta sign flips vs. the right-side panels.
      const sign = state.panel === 'outline' ? -1 : 1;
      const delta = sign * (state.startX - e.clientX);
      if (state.panel === 'chat') {
        setChatDrawerWidth(Math.max(280, Math.min(600, state.startWidth + delta)));
      } else if (state.panel === 'outline') {
        setOutlineWidth(Math.max(180, Math.min(500, state.startWidth + delta)));
      } else {
        setSidebarWidth(Math.max(200, Math.min(500, state.startWidth + delta)));
      }
    };
    const handleUp = () => {
      resizeStateRef.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
    return () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
    };
  }, []);

  const {
    sessions: chatSessions,
    currentSessionId: chatSessionId,
    setCurrentSessionId: setChatSessionId,
    messages: chatMessages,
    loading: chatLoading,
    streamingContent: chatStreaming,
    createSession: createChatSession,
    deleteSession: deleteChatSession,
    sendChat: sendPdfChat,
  } = usePdfChat({
    sendMessage,
    subscribe,
    unsubscribe,
    itemId,
    pdfPath,
  });

  // Collect all referenced passages from chat history for display
  const referencedPassages = React.useMemo(() => {
    const seen = new Set();
    const result = [];
    for (const msg of chatMessages) {
      if (msg.selected_text && !seen.has(msg.selected_text)) {
        seen.add(msg.selected_text);
        result.push({
          text: msg.selected_text,
          page: msg.page_number,
          messageId: msg.id,
        });
      }
    }
    return result;
  }, [chatMessages]);

  const contentRef = useRef(null);
  const annotationsRef = useRef(annotations);
  annotationsRef.current = annotations;
  const hasLoadedRef = useRef(false);

  // If the user clicked "Open Chat" while the annotation was still in its
  // optimistic state (id === client_id), we deferred setting the filter and
  // creating the session. Once the upsert returns and `annot.id` becomes a
  // number, this effect finishes the job so the chat drawer is wired up to
  // the right annotation — and reuses the same chat session if we've already
  // opened one for this annotation.
  useEffect(() => {
    if (!selectedAnnotationId) return;
    if (chatAnnotationFilter != null) return;
    const matched = annotations.find(
      (a) => String(a.id) === String(selectedAnnotationId),
    );
    if (!matched || typeof matched.id !== 'number') return;
    setChatAnnotationFilter(matched.id);
    const existingId = resolveSessionForAnnotation(matched.id, chatSessions);
    if (existingId != null) {
      setChatSessionId(existingId);
    } else {
      createChatSession('Annotation Chat').then((session) => {
        if (session?.id != null) {
          bindAnnotationToSession(matched.id, session.id);
        }
      });
    }
  }, [
    annotations,
    selectedAnnotationId,
    chatAnnotationFilter,
    createChatSession,
    resolveSessionForAnnotation,
    bindAnnotationToSession,
    chatSessions,
  ]);

  // Close the annotation filter dropdown on outside click / Escape
  useEffect(() => {
    if (!isAnnotationFilterOpen) return;
    const handleMouseDown = (e) => {
      const trigger = annotationFilterTriggerRef.current;
      const panel = annotationFilterPanelRef.current;
      const target = e.target;
      if (trigger && trigger.contains(target)) return;
      if (panel && panel.contains(target)) return;
      setIsAnnotationFilterOpen(false);
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsAnnotationFilterOpen(false);
      }
    };
    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isAnnotationFilterOpen]);

  // Load saved annotations from SQLite (priority) > localStorage fallback
  useEffect(() => {
    hasLoadedRef.current = false;
    if (!itemId) {
      // Fallback: localStorage for legacy / direct URL access
      const key = `pdf-annotations:${pdfPath}/main.pdf`;
      const saved = localStorage.getItem(key);
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setAnnotations(parsed);
          if (parsed.length > 0) setShowSidebar(true);
        } catch {}
      }
      hasLoadedRef.current = true;
      // No itemId → no server-side annotations to replay against; clear stale
      // pending comments (no parent to attach them to).
      try {
        localStorage.removeItem('pdf-pending-comments:');
      } catch {}
      return;
    }
    let cancelled = false;
    const loadAnnotations = async () => {
      try {
        const response = await sendMessage('library_annotations_load', { item_id: Number(itemId) }, 10000);
        if (!cancelled) {
          if (response?.data?.annotations) {
            setAnnotations(response.data.annotations);
            if (response.data.annotations.length > 0) setShowSidebar(true);
          }
          hasLoadedRef.current = true;
          // Replay any pending comments left over from a previous session
          // (window was closed mid-flush) — see persistPendingComments above.
          // Returns the list of (clientId, dbId) pairs whose queues were
          // re-populated and need to be flushed to the backend.
          const toFlush = replayPendingComments();
          for (const [clientId, dbId] of toFlush) {
            flushPendingComments(clientId, dbId);
          }
        }
      } catch (e) {
        // Fallback to localStorage on error
        if (!cancelled) {
          const key = `pdf-annotations:${pdfPath}/main.pdf`;
          const saved = localStorage.getItem(key);
          if (saved) {
            try {
              const parsed = JSON.parse(saved);
              setAnnotations(parsed);
              if (parsed.length > 0) setShowSidebar(true);
            } catch {}
          }
          hasLoadedRef.current = true;
          const toFlush = replayPendingComments();
          for (const [clientId, dbId] of toFlush) {
            flushPendingComments(clientId, dbId);
          }
        }
      }
    };
    loadAnnotations();
    return () => { cancelled = true; };
  }, [itemId, pdfPath, sendMessage, replayPendingComments, flushPendingComments]);

  // Save annotations to SQLite (and localStorage as local cache)
  useEffect(() => {
    // Don't save before load completes — avoids race condition where empty initial []
    // overwrites DB before server response arrives
    if (!hasLoadedRef.current) return;

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
      }, 10000)
        .then(() => {
          window.dispatchEvent(
            new CustomEvent('library-annotations-updated', {
              detail: { item_id: Number(itemId) },
            })
          );
        })
        .catch(() => {});
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
      setError(t('pdfViewer.errorNoPath'));
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
        if (!response?.data?.content) throw new Error(t('pdfViewer.errorNoContent'));
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
        if (cancelled) return;
        setPdf(pdfDocument);
        setNumPages(pdfDocument.numPages);
        // Reset the resume guard — a new PDF (or reload after re-mount) gets
        // a fresh restore cycle. We clear it BEFORE reading localStorage so
        // the save effect can't fire on the intermediate setCurrentPage(1)
        // and overwrite the persisted value with a stale "1".
        positionRestoredRef.current = false;
        // Reading-position resume: pull the last page the user was on for
        // this PDF from localStorage. Clamp against the new numPages so a
        // shortened PDF doesn't try to scroll past the end.
        const positionKey = pdfPath ? `pdf-position:${pdfPath}/main.pdf` : null;
        let savedPage = 1;
        if (positionKey) {
          try {
            const raw = localStorage.getItem(positionKey);
            if (raw) {
              const n = parseInt(raw, 10);
              if (Number.isFinite(n) && n >= 1 && n <= pdfDocument.numPages) savedPage = n;
            }
          } catch { /* localStorage may throw in private mode */ }
        }
        setCurrentPage(savedPage);
        positionRestoredRef.current = true;
        // Wait for the Page containers to mount and the layout to settle.
        // We retry across animation frames because pageRefs and viewportSize
        // (which determines each page's rendered height) settle over more
        // than one frame — pdf.getPage() in PdfPage is async, so a freshly
        // mounted page container may still be at its default 600×800 size.
        let frames = 0;
        const tryScroll = () => {
          if (cancelled) return;
          const el = document.querySelector(`[data-page-number="${savedPage}"]`);
          if (!el || !contentRef.current) {
            if (frames++ < 10) requestAnimationFrame(tryScroll);
            return;
          }
          contentRef.current.scrollTo({ top: el.offsetTop - 20, behavior: 'auto' });
        };
        requestAnimationFrame(tryScroll);
        // Best-effort: fetch the PDF's outline (bookmarks). Some PDFs have none;
        // resolveOutline returns [] in that case, which the sidebar renders as
        // an empty-state hint. Failures are swallowed so a malformed outline
        // never blocks page rendering.
        setOutline(null);
        try {
          const raw = await pdfDocument.getOutline();
          if (!cancelled) setOutline(await resolveOutline(pdfDocument, raw));
        } catch (e) {
          console.warn('Failed to read PDF outline:', e);
          if (!cancelled) setOutline([]);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load PDF:', err);
          setError(err.message || t('pdfViewer.errorLoadFailed'));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadPdf();
    return () => { cancelled = true; };
  }, [pdfPath, sendMessage]);

  // Persist reading position (debounced 500ms). Skips until positionRestoredRef
  // is set so the brief setCurrentPage(1) at load time can't clobber a real
  // saved value. Key mirrors the annotations convention (`pdf-*` prefix,
  // scoped by pdfPath).
  useEffect(() => {
    if (!positionRestoredRef.current) return;
    if (!pdfPath || !currentPage) return;
    const key = `pdf-position:${pdfPath}/main.pdf`;
    if (savePositionTimerRef.current) clearTimeout(savePositionTimerRef.current);
    savePositionTimerRef.current = setTimeout(() => {
      try { localStorage.setItem(key, String(currentPage)); }
      catch { /* localStorage may throw in private mode */ }
    }, 500);
    return () => {
      if (savePositionTimerRef.current) clearTimeout(savePositionTimerRef.current);
    };
  }, [currentPage, pdfPath]);

  // Flush any pending save immediately when the window is being closed, so a
  // scroll-to-close sequence within the 500ms debounce window still persists.
  useEffect(() => {
    const flush = () => {
      if (savePositionTimerRef.current) {
        clearTimeout(savePositionTimerRef.current);
        savePositionTimerRef.current = null;
        if (pdfPath && currentPage && positionRestoredRef.current) {
          try { localStorage.setItem(`pdf-position:${pdfPath}/main.pdf`, String(currentPage)); } catch {}
        }
      }
    };
    window.addEventListener('beforeunload', flush);
    window.addEventListener('pagehide', flush);
    return () => {
      window.removeEventListener('beforeunload', flush);
      window.removeEventListener('pagehide', flush);
    };
  }, [pdfPath, currentPage]);

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

  const addHighlight = useCallback(
    async (color) => {
      if (!selection) return;
      window.getSelection().removeAllRanges();
      const clientId = `client-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const annotation = {
        id: clientId,
        client_id: clientId,
        page: selection.page,
        type: 'highlight',
        color,
        text: selection.text,
        comment: '',
        comments: [],
        rects: selection.rects,
        spanRange: selection.spanRange,
        createdAt: Date.now(),
      };
      // Optimistic: render immediately with the client_id
      setAnnotations((prev) => [...prev, annotation]);
      setShowToolbar(false);
      setSelection(null);
      if (!itemId) return;
      // Persist to DB, swap in real db id when upsert returns
      try {
        const resp = await sendMessage(
          'library_annotation_upsert',
          { item_id: Number(itemId), annotation },
          10000,
        );
        const dbId = resp?.data?.id;
        if (dbId != null) {
          setAnnotations((prev) =>
            prev.map((a) => (a.client_id === clientId ? { ...a, id: dbId } : a)),
          );
          // If the chat filter was set optimistically to this annotation's
          // client_id, swap to the real numeric id so the backend hook
          // receives an integer.
          setChatAnnotationFilter((prev) => (prev === clientId ? dbId : prev));
          // Flush any comments queued against this optimistic annotation.
          flushPendingComments(clientId, dbId);
        }
      } catch (e) {
        console.error('Failed to upsert highlight annotation:', e);
      }
    },
    [selection, itemId, sendMessage, flushPendingComments],
  );

  const addUnderline = useCallback(
    async (color) => {
      if (!selection) return;
      window.getSelection().removeAllRanges();
      const clientId = `client-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const annotation = {
        id: clientId,
        client_id: clientId,
        page: selection.page,
        type: 'underline',
        color,
        text: selection.text,
        comment: '',
        comments: [],
        rects: selection.rects,
        spanRange: selection.spanRange,
        createdAt: Date.now(),
      };
      setAnnotations((prev) => [...prev, annotation]);
      setShowToolbar(false);
      setSelection(null);
      if (!itemId) return;
      try {
        const resp = await sendMessage(
          'library_annotation_upsert',
          { item_id: Number(itemId), annotation },
          10000,
        );
        const dbId = resp?.data?.id;
        if (dbId != null) {
          setAnnotations((prev) =>
            prev.map((a) => (a.client_id === clientId ? { ...a, id: dbId } : a)),
          );
          // If the chat filter was set optimistically to this annotation's
          // client_id, swap to the real numeric id so the backend hook
          // receives an integer.
          setChatAnnotationFilter((prev) => (prev === clientId ? dbId : prev));
          // Flush any comments queued against this optimistic annotation.
          flushPendingComments(clientId, dbId);
        }
      } catch (e) {
        console.error('Failed to upsert underline annotation:', e);
      }
    },
    [selection, itemId, sendMessage, flushPendingComments],
  );

  // Append a comment to an existing annotation. `annotationKey` may be either
  // the numeric id (stringified) or the optimistic client_id. When the
  // annotation is still optimistic (no numeric id yet), the comment is queued
  // locally and flushed to the backend once library_annotation_upsert
  // returns — see flushPendingComments above.
  const addAnnotationComment = useCallback(
    async (annotationKey, content) => {
      if (!annotationKey || !content?.trim()) return null;
      const contentTrim = content.trim();

      // Locate the annotation by either id or client_id.
      const target = annotationsRef.current.find(
        (a) => String(a.id) === annotationKey || a.client_id === annotationKey,
      );
      if (!target) return null;
      const hasDbId = typeof target.id === 'number';

      // Optimistic path: queue locally, the upsert success handler will flush.
      if (!hasDbId) {
        const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        const optimistic = {
          _localId: localId,
          _pending: true,
          _clientId: target.client_id,
          content: contentTrim,
          author_name: t('annotation.authorYou'),
          created_at: Date.now(),
        };
        setAnnotations((prev) =>
          prev.map((a) =>
            a.client_id === target.client_id
              ? { ...a, comments: [...(a.comments || []), optimistic] }
              : a,
          ),
        );
        const queue = pendingCommentsByClientIdRef.current.get(target.client_id) || [];
        queue.push({ localId, content: contentTrim });
        pendingCommentsByClientIdRef.current.set(target.client_id, queue);
        // Persist so a window-close mid-flush doesn't drop the comment.
        persistPendingComments();
        return optimistic;
      }

      // Persisted path: call the RPC directly.
      try {
        const resp = await sendMessage(
          'library_annotation_comments_add',
          { annotation_id: target.id, content: contentTrim },
          10000,
        );
        const newComment = resp?.data?.comment;
        if (newComment) {
          setAnnotations((prev) =>
            prev.map((a) =>
              a.id === target.id
                ? { ...a, comments: [...(a.comments || []), newComment] }
                : a,
            ),
          );
        }
        return newComment || null;
      } catch (e) {
        console.error('Failed to add annotation comment:', e);
        throw e;
      }
    },
    [sendMessage, t, persistPendingComments],
  );

  const deleteAnnotationComment = useCallback(
    async (annotationKey, commentId, isPending) => {
      if (!commentId) return;

      // Pending comment: never reached the backend, just drop it locally.
      if (isPending) {
        const target = annotationsRef.current.find(
          (a) => String(a.id) === annotationKey || a.client_id === annotationKey,
        );
        if (!target) return;
        const clientId = target.client_id;
        // Remove from the flush queue so it won't fire later.
        const queue = pendingCommentsByClientIdRef.current.get(clientId);
        if (queue) {
          pendingCommentsByClientIdRef.current.set(
            clientId,
            queue.filter((q) => q.localId !== commentId),
          );
          persistPendingComments();
        }
        setAnnotations((prev) =>
          prev.map((a) =>
            a.client_id === clientId
              ? {
                  ...a,
                  comments: (a.comments || []).filter((c) => c._localId !== commentId),
                }
              : a,
          ),
        );
        return;
      }

      // Persisted comment: delete on backend, then drop from local state.
      try {
        await sendMessage(
          'library_annotation_comments_delete',
          { comment_id: commentId },
          10000,
        );
        setAnnotations((prev) =>
          prev.map((a) =>
            String(a.id) === String(annotationKey)
              ? {
                  ...a,
                  comments: (a.comments || []).filter((c) => c.id !== commentId),
                }
              : a,
          ),
        );
      } catch (e) {
        console.error('Failed to delete annotation comment:', e);
        throw e;
      }
    },
    [sendMessage, persistPendingComments],
  );

  const deleteAnnotation = useCallback(
    async (id) => {
      const target = annotations.find((a) => String(a.id) === String(id));
      setAnnotations((prev) => prev.filter((a) => String(a.id) !== String(id)));
      if (String(selectedAnnotationId) === String(id)) setSelectedAnnotationId(null);
      // If the deleted annotation is a real db row, also remove on the server.
      // Client ids (e.g. "client-..." that haven't been upserted yet) won't be sent.
      if (target && itemId && typeof target.id === 'number') {
        try {
          await sendMessage(
            'library_annotation_delete_by_id',
            { item_id: Number(itemId), annotation_id: target.id },
            10000,
          );
        } catch (e) {
          console.error('Failed to delete annotation server-side:', e);
        }
      }
    },
    [annotations, selectedAnnotationId, itemId, sendMessage],
  );

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

  const scrollToAnnotation = useCallback((id) => {
    if (!contentRef.current) return;
    const rectEls = document.querySelectorAll(`[data-annotation-id="${id}"]`);
    if (rectEls.length === 0) return;
    const container = contentRef.current;
    const containerRect = container.getBoundingClientRect();
    let bestTop = Infinity;
    rectEls.forEach((el) => {
      const r = el.getBoundingClientRect();
      const top = r.top - containerRect.top + container.scrollTop;
      if (top < bestTop) bestTop = top;
    });
    const target = Math.max(0, bestTop - 80);
    container.scrollTo({ top: target, behavior: 'smooth' });
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

  // ── Chat actions ──
  const [chatSelection, setChatSelection] = useState(null);
  const [copiedMsgId, setCopiedMsgId] = useState(null);

  const openChatWithSelection = useCallback(() => {
    if (!selection?.text) return;
    setChatSelection({ text: selection.text, page: selection.page });
    // Clear any annotation filter so the new chat isn't locked to a stale
    // annotation context — this click is about the live text selection.
    setChatAnnotationFilter(null);
    // Always spin up a brand-new session for a text-selection chat. Selection
    // chats are ephemeral (no binding map like annotations) and the user
    // expects "click chat on selection → fresh thread", mirroring the
    // "click chat on annotation → Annotation Chat" flow in
    // handleOpenChatForAnnotation below.
    createChatSession('Selection Chat');
    setShowChatDrawer(true);
    setShowToolbar(false);
    window.getSelection().removeAllRanges();
  }, [selection, createChatSession]);

  const closeChatDrawer = useCallback(() => {
    setShowChatDrawer(false);
    setChatSelection(null);
  }, []);

  // Open the chat drawer locked to a single annotation. If the annotation hasn't
  // been persisted yet (id is still the client-side uuid), just open the drawer;
  // the chat hook will fall back to creating a session once upsert completes.
  // Also seeds `chatSelection` with the annotation's text/page so the Context
  // block shows the full annotation text and the chat agent receives it as
  // `selected_text` / `page_number` (see usePdfChat.sendChat).
  //
  // Session reuse: each annotation is permanently bound to ONE chat session
  // (`annotationSessionMapRef`). Reopening the same annotation's chat always
  // reuses that session — no duplicate threads.
  const handleOpenChatForAnnotation = useCallback(
    (annot) => {
      if (!annot) return;
      // Open the chat drawer immediately so the user sees feedback.
      setShowChatDrawer(true);
      setSelectedAnnotationId(annot.id ?? annot.client_id);
      scrollToAnnotation(annot.id ?? annot.client_id);
      // Seed the context block with the annotation's own text. Only do this
      // when the annotation actually has text — for empty "note"-style rows
      // we leave chatSelection null so the user isn't shown an empty quote.
      if (annot.text) {
        setChatSelection({ text: annot.text, page: annot.page });
      }
      // Lock the dropdown to this annotation. We accept both numeric ids and
      // the optimistic client_id string — the dropdown lookup matches by either,
      // and the upsert success handlers remap client_id → numeric id so the
      // backend hook receives a real integer.
      setChatAnnotationFilter(annot.id ?? annot.client_id ?? null);
      if (typeof annot.id === 'number') {
        // Try to reuse an existing session bound to this annotation. The
        // session id is the numeric one we got back from createSession().
        const existingId = resolveSessionForAnnotation(annot.id, chatSessions);
        if (existingId != null) {
          setChatSessionId(existingId);
        } else {
          // No binding (or stale binding for a deleted session) — create a
          // fresh one and remember it. createChatSession returns the new
          // session; we bind it via a microtask so setChatSessionId lands.
          createChatSession('Annotation Chat').then((session) => {
            if (session?.id != null) {
              bindAnnotationToSession(annot.id, session.id);
            }
          });
        }
      }
    },
    [
      createChatSession,
      scrollToAnnotation,
      resolveSessionForAnnotation,
      bindAnnotationToSession,
      chatSessions,
    ],
  );

  const handleSendChat = useCallback(async (input) => {
    if (!input.trim() || chatLoading) return;
    await sendPdfChat({
      content: input.trim(),
      pageNumber: chatSelection?.page,
      selectedText: chatSelection?.text,
    });
    // Keep chatSelection so user can ask follow-up questions about the same selection
  }, [chatLoading, chatSelection, sendPdfChat]);

  const handleCopyMessage = async (msgId, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMsgId(msgId);
      setTimeout(() => setCopiedMsgId(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Insert an assistant chat reply into the comment thread of the annotation
  // currently locked in the chat drawer's filter dropdown. If no annotation is
  // selected (`chatAnnotationFilter` is null or points at an optimistic row
  // without a db id yet), we surface a brief inline toast and do nothing.
  //
  // We piggy-back on `addAnnotationComment`, which already handles the
  // optimistic-annotation queue + flush-after-upsert dance, so this works
  // uniformly whether the parent annotation is already persisted or still
  // waiting on its upsert.
  const [addedToAnnotationMsgId, setAddedToAnnotationMsgId] = useState(null);
  const [addToAnnotationErrorMsgId, setAddToAnnotationErrorMsgId] = useState(null);
  const handleAddToAnnotation = useCallback(
    async (msg) => {
      const filter = chatAnnotationFilter;
      if (filter == null) {
        setAddToAnnotationErrorMsgId(msg.id);
        setTimeout(
          () => setAddToAnnotationErrorMsgId((cur) => (cur === msg.id ? null : cur)),
          2200,
        );
        return;
      }
      // Resolve the actual annotation row + require a db id (the comments
      // RPC requires an integer annotation_id).
      const target = annotationsRef.current.find(
        (a) =>
          String(a.id) === String(filter) || a.client_id === filter,
      );
      if (!target || typeof target.id !== 'number') {
        setAddToAnnotationErrorMsgId(msg.id);
        setTimeout(
          () => setAddToAnnotationErrorMsgId((cur) => (cur === msg.id ? null : cur)),
          2200,
        );
        return;
      }
      try {
        await addAnnotationComment(String(target.id), msg.content || '');
        setAddedToAnnotationMsgId(msg.id);
        setTimeout(
          () => setAddedToAnnotationMsgId((cur) => (cur === msg.id ? null : cur)),
          2000,
        );
      } catch (e) {
        console.error('Failed to add chat reply to annotation comment:', e);
        setAddToAnnotationErrorMsgId(msg.id);
        setTimeout(
          () => setAddToAnnotationErrorMsgId((cur) => (cur === msg.id ? null : cur)),
          2200,
        );
      }
    },
    [chatAnnotationFilter, addAnnotationComment],
  );

  if (loading) {
    return (
      <div className="pdfv-loading">
        <div className="pdfv-spinner" />
        <span>{t('pdfViewer.loadingPdf')}</span>
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
          <button className="pdfv-btn" onClick={resetZoom} title={t('pdfViewer.toolbarResetZoom')}><RotateCcw size={14} /></button>
          <span className="pdfv-zoominfo">{Math.round(scale * 100)}%</span>
          <button className="pdfv-btn" onClick={zoomIn} title="Zoom in (+)"><Plus size={14} /></button>
          <button
            className={`pdfv-btn ${showOutline ? 'pdfv-btn-active' : ''}`}
            onClick={() => setShowOutline((s) => !s)}
            title={t('pdfViewer.toolbarToc')}
            style={{ position: 'relative' }}
          >
            <BookOpen size={16} />
          </button>
          <button
            className={`pdfv-btn ${showSidebar ? 'pdfv-btn-active' : ''}`}
            onClick={() => setShowSidebar((s) => !s)}
            title={t('pdfViewer.toolbarAnnotations')}
            style={{ position: 'relative' }}
          >
            <MessageSquare size={16} />
            {annotations.length > 0 && (
              <span className="pdfv-badge">{annotations.length}</span>
            )}
          </button>
          <button
            className={`pdfv-btn ${showChatDrawer ? 'pdfv-btn-active' : ''}`}
            onClick={() => setShowChatDrawer((s) => !s)}
            title={t('pdfViewer.toolbarChat')}
            style={{ position: 'relative' }}
          >
            <Bot size={16} />
            {chatSessions.length > 0 && (
              <span className="pdfv-badge">{chatSessions.length}</span>
            )}
          </button>
          <button className="pdfv-btn pdfv-btn-close" onClick={handleClose} title={t('pdfViewer.toolbarClose')}><X size={16} /></button>
        </div>
      </div>

      {/* Main */}
      <div className="pdfv-main">
        {/* TOC panel — sits on the LEFT, independent of the right-side
            annotations sidebar. Default open because chapter navigation is
            the most common reason to open a PDF reader. */}
        {showOutline && (
          <>
            <div className="pdfv-toc-panel" style={{ width: outlineWidth, minWidth: outlineWidth }}>
              <div className="pdfv-toc-panel-header">
                <span>
                  <BookOpen size={13} style={{ marginRight: 6, verticalAlign: -1 }} />
                  {t('pdfViewer.tocTab')}
                </span>
                <button className="pdfv-btn" onClick={() => setShowOutline(false)}><X size={14} /></button>
              </div>
              <div className="pdfv-toc-panel-content">
                <TocTree
                  items={outline || []}
                  currentPage={currentPage}
                  onJump={scrollToPage}
                />
              </div>
            </div>
            <div
              className="pdfv-resizer pdfv-resizer-right"
              onMouseDown={(e) => startResize(e, 'outline')}
            />
          </>
        )}
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
          <>
          <div
            className="pdfv-resizer"
            onMouseDown={(e) => startResize(e, 'sidebar')}
          />
          <div className="pdfv-sidebar" style={{ width: sidebarWidth, minWidth: sidebarWidth }}>
            <div className="pdfv-sidebar-header">
              <span>{t('pdfViewer.sidebarTitle', { count: annotations.length })}</span>
              <button className="pdfv-btn" onClick={() => setShowSidebar(false)}><X size={14} /></button>
            </div>
            <div className="pdfv-sidebar-content">
              {annotations.length === 0 ? (
                <div className="pdfv-sidebar-empty">{t('pdfViewer.selectTextHint')}</div>
              ) : (
                annotations.map((annot) => (
                  <div
                    key={annot.id}
                    className={`pdfv-annot-item ${selectedAnnotationId === annot.id ? 'pdfv-annot-item-selected' : ''}`}
                    onClick={() => {
                      setSelectedAnnotationId(annot.id);
                      scrollToAnnotation(annot.id);
                    }}
                  >
                    <div className="pdfv-annot-meta">
                      <span className="pdfv-annot-page">{t('pdfViewer.pageLabel', { page: annot.page })}</span>
                      <span className="pdfv-annot-type">{annot.type}</span>
                    </div>
                    <div className="pdfv-annot-text">"{annot.text}"</div>

                    {/* Annotation comments (thread). Replaces the legacy single
                        `comment` field — see library_annotation_comments table. */}
                    <AnnotationComments
                      annot={annot}
                      onAddComment={addAnnotationComment}
                      onDeleteComment={deleteAnnotationComment}
                    />

                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <button
                        className="pdfv-annot-open-chat"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenChatForAnnotation(annot);
                        }}
                        disabled={annot.id == null && !annot.client_id}
                        title={
                          annot.id == null && !annot.client_id
                            ? ''
                            : t('annotation.openChat')
                        }
                      >
                        <MessageSquare size={11} />
                        {t('annotation.openChat')}
                      </button>
                      <button className="pdfv-annot-delete" onClick={() => deleteAnnotation(annot.id)}>{t('pdfViewer.annotDelete')}</button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
          </>
        )}
        {/* Chat Drawer */}
        {showChatDrawer && (
          <>
          <div
            className="pdfv-resizer"
            onMouseDown={(e) => startResize(e, 'chat')}
          />
          <div className="pdfv-chat-drawer" style={{ width: chatDrawerWidth, minWidth: chatDrawerWidth }}>
            {/* Header */}
            <div className="pdfv-chat-header">
              <span className="pdfv-chat-title">
                <Bot size={14} style={{ marginRight: 6 }} />
                {t('pdfViewer.chatHeaderTitle')}
              </span>
              <div style={{ display: 'flex', gap: 4 }}>
                <button
                  className="pdfv-btn"
                  onClick={() => createChatSession()}
                  title={t('pdfViewer.toolbarNewSession')}
                >
                  <Plus size={14} />
                </button>
                <button className="pdfv-btn" onClick={closeChatDrawer}><X size={14} /></button>
              </div>
            </div>
            {/* Annotation filter dropdown */}
            <div className="pdfv-chat-annotation-filter">
              {(() => {
                const annotList = Array.isArray(annotations) ? annotations : [];
                // chatAnnotationFilter may be a numeric id or a client_id string
                // (set optimistically by handleOpenChatForAnnotation before the
                // annotation is persisted). Match either form.
                const selectedAnnot =
                  chatAnnotationFilter == null
                    ? null
                    : annotList.find(
                        (a) =>
                          String(a.id) === String(chatAnnotationFilter) ||
                          a.client_id === chatAnnotationFilter,
                      ) || null;
                const triggerColor = selectedAnnot?.color || '#4a9eff';
                const triggerPreview = selectedAnnot
                  ? (selectedAnnot.text || '').slice(0, 50) +
                    ((selectedAnnot.text || '').length > 50 ? '…' : '')
                  : null;
                const triggerLabel = selectedAnnot
                  ? t('annotation.chatForAnnotation', { preview: triggerPreview })
                  : t('annotation.chatAllAnnotations');
                const isAllSelected = chatAnnotationFilter == null;
                return (
                  <>
                    <button
                      ref={annotationFilterTriggerRef}
                      type="button"
                      className="pdfv-chat-session pdfv-chat-filter-trigger"
                      onClick={() => setIsAnnotationFilterOpen((v) => !v)}
                      aria-expanded={isAnnotationFilterOpen}
                      aria-haspopup="listbox"
                    >
                      <span
                        className="pdfv-chat-filter-color-bar"
                        style={{ background: triggerColor }}
                      />
                      <span className="pdfv-chat-session-title">{triggerLabel}</span>
                      <ChevronDown
                        size={12}
                        className={`pdfv-chat-filter-chevron ${isAnnotationFilterOpen ? 'is-open' : ''}`}
                      />
                    </button>
                    {isAnnotationFilterOpen && (
                      <div
                        ref={annotationFilterPanelRef}
                        className="pdfv-chat-filter-panel"
                        role="listbox"
                      >
                        <div
                          className={`pdfv-chat-session pdfv-chat-filter-item ${isAllSelected ? 'pdfv-chat-session-active' : ''}`}
                          role="option"
                          aria-selected={isAllSelected}
                          onClick={() => {
                            setChatAnnotationFilter(null);
                            setIsAnnotationFilterOpen(false);
                          }}
                        >
                          <span
                            className="pdfv-chat-filter-color-bar"
                            style={{ background: '#4a9eff' }}
                          />
                          <span className="pdfv-chat-session-title">
                            {t('annotation.chatAllAnnotations')}
                          </span>
                          {isAllSelected ? (
                            <Check size={12} className="pdfv-chat-filter-check" />
                          ) : (
                            <span className="pdfv-chat-filter-check-placeholder" />
                          )}
                        </div>
                        {annotList.filter((a) => typeof a.id === 'number').length === 0 ? (
                          <div className="pdfv-chat-filter-empty">
                            {t('annotation.filterEmpty')}
                          </div>
                        ) : (
                          annotList
                            .filter((a) => typeof a.id === 'number')
                            .map((a) => {
                              const isSelected = chatAnnotationFilter === a.id;
                              const preview =
                                (a.text || '').slice(0, 50) +
                                ((a.text || '').length > 50 ? '…' : '');
                              return (
                                <div
                                  key={a.id}
                                  className={`pdfv-chat-session pdfv-chat-filter-item ${isSelected ? 'pdfv-chat-session-active' : ''}`}
                                  role="option"
                                  aria-selected={isSelected}
                                  onClick={() => {
                                    setChatAnnotationFilter(a.id);
                                    setIsAnnotationFilterOpen(false);
                                    // Reuse the session bound to this
                                    // annotation. If we've never opened chat
                                    // for it, create one and bind it.
                                    const existingId = resolveSessionForAnnotation(
                                      a.id,
                                      chatSessions,
                                    );
                                    if (existingId != null) {
                                      setChatSessionId(existingId);
                                    } else {
                                      createChatSession('Annotation Chat').then(
                                        (session) => {
                                          if (session?.id != null) {
                                            bindAnnotationToSession(a.id, session.id);
                                          }
                                        },
                                      );
                                    }
                                  }}
                                >
                                  <span
                                    className="pdfv-chat-filter-color-bar"
                                    style={{ background: a.color || '#1890ff' }}
                                  />
                                  <span className="pdfv-chat-session-title">
                                    {a.page ? (
                                      <span className="pdfv-chat-filter-page-badge">
                                        {`P${a.page}·`}
                                      </span>
                                    ) : null}
                                    {t('annotation.chatForAnnotation', { preview })}
                                  </span>
                                  {isSelected ? (
                                    <Check size={12} className="pdfv-chat-filter-check" />
                                  ) : (
                                    <span className="pdfv-chat-filter-check-placeholder" />
                                  )}
                                </div>
                              );
                            })
                        )}
                      </div>
                    )}
                  </>
                );
              })()}
            </div>

            {/* Sessions */}
            {chatSessions.length > 0 && (
              <div className="pdfv-chat-sessions">
                {chatSessions.map((s) => (
                  <div
                    key={s.id}
                    className={`pdfv-chat-session ${chatSessionId === s.id ? 'pdfv-chat-session-active' : ''}`}
                    onClick={() => setChatSessionId(s.id)}
                  >
                    <span className="pdfv-chat-session-title">{s.title}</span>
                    <button
                      className="pdfv-chat-session-delete"
                      onClick={(e) => { e.stopPropagation(); deleteChatSession(s.id); }}
                    >
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Context block */}
            {chatSelection && (
              <div className="pdfv-chat-context">
                <div className="pdfv-chat-context-meta">
                  <span>{t('pdfViewer.chatContextPage', { page: chatSelection.page })}</span>
                  <button onClick={() => setChatSelection(null)}>✕</button>
                </div>
                <div className="pdfv-chat-context-text">{chatSelection.text}</div>
              </div>
            )}

            {/* Referenced Passages Summary */}
            {referencedPassages.length > 0 && (
              <details className="pdfv-chat-passages">
                <summary>
                  {t('pdfViewer.chatReferencedTitle', { count: referencedPassages.length })}
                </summary>
                <div className="pdfv-chat-passages-list">
                  {referencedPassages.map((p, i) => (
                    <div key={p.messageId} className="pdfv-chat-passage-item">
                      <div className="pdfv-chat-passage-meta">
                        #{i + 1}{p.page ? t('pdfViewer.chatReferencedPage', { page: p.page }) : ''}
                      </div>
                      <div className="pdfv-chat-passage-text">{p.text}</div>
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* Messages */}
            <div className="pdfv-chat-messages">
              {chatMessages.length === 0 && !chatSelection && !referencedPassages.length && (
                <div className="pdfv-chat-empty">
                  {t('pdfViewer.selectTextChatHint')}
                </div>
              )}
              {chatMessages.map((msg) => (
                <div key={msg.id} className={`pdfv-chat-msg pdfv-chat-msg-${msg.role}`}>
                  {msg.role === 'tool' ? (
                    <div className="pdfv-chat-tool-card">
                      <div className="pdfv-chat-tool-header">
                        <span className="pdfv-chat-tool-name">🔧 {msg.metadata?.tool || 'tool'}</span>
                        <span className={`pdfv-chat-tool-status pdfv-chat-tool-status-${msg.metadata?.status || 'done'}`}>
                          {msg.metadata?.status === 'running' ? t('pdfViewer.chatRunning') : t('pdfViewer.chatDone')}
                        </span>
                      </div>
                      {msg.metadata?.args && (
                        <details className="pdfv-chat-tool-details">
                          <summary>{t('pdfViewer.chatToolArguments')}</summary>
                          <pre className="pdfv-chat-tool-code">{JSON.stringify(msg.metadata.args, null, 2)}</pre>
                        </details>
                      )}
                      {(msg.metadata?.result || msg.content) && (
                        <details className="pdfv-chat-tool-details">
                          <summary>{t('pdfViewer.chatToolResult')}</summary>
                          <pre className="pdfv-chat-tool-code">{typeof (msg.metadata?.result || msg.content) === 'string' ? (msg.metadata?.result || msg.content) : JSON.stringify(msg.metadata?.result || msg.content, null, 2)}</pre>
                        </details>
                      )}
                    </div>
                  ) : (
                    <div className="pdfv-chat-msg-bubble">
                      {msg.role === 'assistant' && (
                        <div className="pdfv-chat-msg-avatar"><Bot size={12} /></div>
                      )}
                      <div className="pdfv-chat-msg-content">
                        {msg.role === 'user' && msg.selected_text && (
                          <div className="pdfv-chat-msg-quote">
                            <div className="pdfv-chat-msg-quote-meta">{t('pdfViewer.chatContextPage', { page: msg.page_number })}</div>
                            <blockquote>{msg.selected_text}</blockquote>
                          </div>
                        )}
                        {msg.role === 'assistant' ? (
                          <>
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm, remarkMath]}
                              rehypePlugins={[rehypeKatex]}
                              components={{
                                pre({ children }) {
                                  const childArray = React.Children.toArray(children);
                                  const codeChild = childArray.find((c) => c?.type === 'code');
                                  if (codeChild) {
                                    const lang = codeChild.props?.className?.replace('language-', '') || '';
                                    const text = String(codeChild.props.children).replace(/\n$/, '').trim();
                                    if (lang === 'mermaid') {
                                      return <MermaidDiagram source={text} />;
                                    }
                                    if (lang === 'mindmap') {
                                      return <MindmapDiagram source={text} />;
                                    }
                                  }
                                  return <pre>{children}</pre>;
                                },
                              }}
                            >
                              {msg.content || ''}
                            </ReactMarkdown>
                            {msg.content?.trim() && (
                              <div className="pdfv-chat-msg-actions">
                                <button
                                  type="button"
                                  className="pdfv-chat-msg-add-btn"
                                  onClick={() => handleAddToAnnotation(msg)}
                                  title={
                                    chatAnnotationFilter == null
                                      ? t('pdfViewer.chatAddToAnnotationNoTarget')
                                      : t('pdfViewer.chatAddToAnnotation')
                                  }
                                  disabled={chatAnnotationFilter == null}
                                >
                                  {addedToAnnotationMsgId === msg.id ? (
                                    <>
                                      <Check size={12} />
                                      <span>{t('pdfViewer.chatAddedToAnnotation')}</span>
                                    </>
                                  ) : addToAnnotationErrorMsgId === msg.id ? (
                                    <>
                                      <X size={12} />
                                      <span>{t('pdfViewer.chatAddToAnnotationNoTarget')}</span>
                                    </>
                                  ) : (
                                    <>
                                      <StickyNote size={12} />
                                      <span>{t('pdfViewer.chatAddToAnnotation')}</span>
                                    </>
                                  )}
                                </button>
                                <button
                                  type="button"
                                  className="pdfv-chat-msg-copy-btn"
                                  onClick={() => handleCopyMessage(msg.id, msg.content)}
                                  title="复制内容"
                                >
                                  {copiedMsgId === msg.id ? (
                                    <>
                                      <Check size={12} />
                                      <span>{t('pdfViewer.chatCopied')}</span>
                                    </>
                                  ) : (
                                    <>
                                      <Copy size={12} />
                                      <span>{t('pdfViewer.chatCopy')}</span>
                                    </>
                                  )}
                                </button>
                              </div>
                            )}
                          </>
                        ) : (
                          <div>{msg.content}</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {chatLoading && (
                <div className="pdfv-chat-msg pdfv-chat-msg-assistant">
                  <div className="pdfv-chat-msg-bubble">
                    <div className="pdfv-chat-msg-avatar"><Bot size={12} /></div>
                    <div className="pdfv-chat-msg-content">
                      {chatStreaming ? (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkMath]}
                          rehypePlugins={[rehypeKatex]}
                          components={{
                            pre({ children }) {
                              const childArray = React.Children.toArray(children);
                              const codeChild = childArray.find((c) => c?.type === 'code');
                              if (codeChild) {
                                const lang = codeChild.props?.className?.replace('language-', '') || '';
                                const text = String(codeChild.props.children).replace(/\n$/, '').trim();
                                // 流式中不渲染未完成的脑图（避免抖动）
                                // 检测当前代码块是否已在 chatStreaming 中完整出现（有闭合围栏）
                                const isClosed = (() => {
                                  const startIdx = chatStreaming.lastIndexOf('```' + lang);
                                  if (startIdx === -1) return false;
                                  return chatStreaming.slice(startIdx + ('```' + lang).length).includes('\n```');
                                })();
                                if (lang === 'mermaid' && isClosed) {
                                  return <MermaidDiagram source={text} />;
                                }
                                if (lang === 'mindmap' && isClosed) {
                                  return <MindmapDiagram source={text} />;
                                }
                              }
                              return <pre>{children}</pre>;
                            },
                          }}
                        >
                          {chatStreaming}
                        </ReactMarkdown>
                      ) : (
                        <span className="pdfv-chat-typing"><span /><span /><span /></span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Quick Actions */}
            {chatMessages.length === 0 && !chatLoading && (
              <div className="pdfv-quick-actions">
                <button
                  className="pdfv-quick-action-btn"
                  onClick={() => handleSendChat(t('pdfViewer.chatPromptSummary'))}
                  disabled={chatLoading}
                >
                  <Sparkles size={12} />
                  {t('pdfViewer.chatSummaryBtn')}
                </button>
                <button
                  className="pdfv-quick-action-btn"
                  onClick={() => handleSendChat(t('pdfViewer.chatPromptMindmap'))}
                  disabled={chatLoading}
                >
                  <Bot size={12} />
                  {t('pdfViewer.chatMindmapBtn')}
                </button>
                <button
                  className="pdfv-quick-action-btn"
                  onClick={() => handleSendChat(t('pdfViewer.chatPromptTreeMindmap'))}
                  disabled={chatLoading}
                >
                  <Network size={12} />
                  {t('pdfViewer.chatTreeMindmapBtn')}
                </button>
                <button
                  className="pdfv-quick-action-btn"
                  onClick={() => handleSendChat(t('pdfViewer.chatPromptMethod'))}
                  disabled={chatLoading}
                >
                  <MessageSquare size={12} />
                  {t('pdfViewer.chatMethodBtn')}
                </button>
                <button
                  className="pdfv-quick-action-btn"
                  onClick={() => handleSendChat(t('pdfViewer.chatPromptTerms'))}
                  disabled={chatLoading}
                >
                  <Underline size={12} />
                  {t('pdfViewer.chatTermsBtn')}
                </button>
              </div>
            )}

            {/* Input */}
            <div className="pdfv-chat-input-wrap">
              <textarea
                ref={chatInputRef}
                className="pdfv-chat-input"
                placeholder={chatSelection ? t('pdfViewer.chatPlaceholderSelection') : t('pdfViewer.chatPlaceholderGeneral')}
                rows={2}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    const val = e.target.value.trim();
                    if (val) {
                      handleSendChat(val);
                      e.target.value = '';
                    }
                  }
                }}
              />
              <button
                className="pdfv-chat-send"
                onClick={() => {
                  const el = chatInputRef.current;
                  if (el && el.value.trim()) {
                    handleSendChat(el.value.trim());
                    el.value = '';
                  }
                }}
                disabled={chatLoading}
              >
                <Send size={14} />
              </button>
            </div>
          </div>
          </>
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
        <button className="pdfv-toolbar-action" onClick={() => addUnderline(COLORS[2].value)} title={t('pdfViewer.toolbarUnderline')}>
          <Underline size={14} />
        </button>
        <button className="pdfv-toolbar-action" onClick={openChatWithSelection} title={t('pdfViewer.toolbarChatSelection')}>
          <MessageSquare size={14} />
        </button>
      </div>
    )}
  </div>
);
};

export default PdfViewerWindow;
