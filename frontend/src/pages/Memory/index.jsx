import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Brain,
  Search,
  RefreshCw,
  Clock,
  Hash,
  FileText,
  Tag,
  Trash2,
  X,
  ChevronLeft,
  ChevronRight,
  Filter,
} from 'lucide-react';
import WindowDots from '@components/layout/WindowDots';

const TYPE_ICONS = {
  gotcha: '🔴',
  'problem-solution': '🟡',
  'how-it-works': '🔵',
  'what-changed': '🟢',
  discovery: '🟣',
  'why-it-exists': '🟠',
  decision: '🟤',
  'trade-off': '⚖️',
  general: '⚪',
};

const TYPE_LABELS = {
  gotcha: 'Gotcha',
  'problem-solution': 'Problem/Solution',
  'how-it-works': 'How It Works',
  'what-changed': 'What Changed',
  discovery: 'Discovery',
  'why-it-exists': 'Why It Exists',
  decision: 'Decision',
  'trade-off': 'Trade-off',
  general: 'General',
};

const TYPE_OPTIONS = [
  { value: '', label: 'All Types' },
  ...Object.keys(TYPE_LABELS).map((k) => ({ value: k, label: TYPE_LABELS[k] })),
];

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString();
}

function truncate(str, len = 120) {
  if (!str || str.length <= len) return str;
  return str.slice(0, len).trim() + '…';
}

const MemoryPanel = ({ sendWSMessage }) => {
  const [observations, setObservations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [selected, setSelected] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [promoting, setPromoting] = useState(false);

  const fetchList = useCallback(async () => {
    if (!sendWSMessage) return;
    setLoading(true);
    try {
      const resp = await sendWSMessage('memory_list', { limit: 100 }, 8000);
      setObservations(resp.data?.observations || []);
    } catch (err) {
      console.error('Failed to fetch observations:', err);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage]);

  const fetchSearch = useCallback(async () => {
    if (!sendWSMessage || !query.trim()) {
      fetchList();
      return;
    }
    setLoading(true);
    try {
      const payload = { query: query.trim(), limit: 50 };
      if (typeFilter) payload.type_filter = typeFilter;
      const resp = await sendWSMessage('memory_search', payload, 8000);
      setObservations(resp.data?.observations || []);
    } catch (err) {
      console.error('Failed to search observations:', err);
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage, query, typeFilter, fetchList]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (query.trim()) {
        fetchSearch();
      } else {
        fetchList();
      }
    }, 300);
    return () => clearTimeout(t);
  }, [query, typeFilter, fetchSearch, fetchList]);

  const openDetail = useCallback(async (obs) => {
    setSelected(obs);
    setDetailOpen(true);
    setDetailLoading(true);
    setTimeline([]);
    try {
      const [readResp, timelineResp] = await Promise.all([
        sendWSMessage('memory_read', { observation_id: obs.id }, 5000),
        sendWSMessage('memory_timeline', { observation_id: obs.id, depth_before: 3, depth_after: 3 }, 5000),
      ]);
      setSelected(readResp.data?.observation || obs);
      setTimeline(timelineResp.data?.observations || []);
    } catch (err) {
      console.error('Failed to load detail:', err);
    } finally {
      setDetailLoading(false);
    }
  }, [sendWSMessage]);

  const closeDetail = useCallback(() => {
    setDetailOpen(false);
    setSelected(null);
    setTimeline([]);
  }, []);

  useEffect(() => {
    setPromoting(false);
  }, [selected?.id]);

  const handlePromote = useCallback(async (target = 'memory') => {
    if (!selected || promoting) return;
    setPromoting(true);
    try {
      const resp = await sendWSMessage('memory_promote', {
        observation_id: selected.id,
        target,
      }, 10000);
      if (resp.data?.success) {
        alert(`Promoted to ${target} memory. Usage: ${resp.data?.usage || ''}`);
      } else {
        const err = resp.data?.error || 'Promotion failed';
        if (err.includes('limit') || err.includes('exceed')) {
          alert(`Memory full! ${err}\n\nTry removing some old entries first.`);
        } else {
          alert('Promotion failed: ' + err);
        }
      }
    } catch (err) {
      console.error('Promotion failed:', err);
      alert('Promotion failed: ' + err.message);
    } finally {
      setPromoting(false);
    }
  }, [sendWSMessage, selected, promoting]);

  const handleDelete = useCallback(async (obsId) => {
    if (!confirm('Delete this observation?')) return;
    try {
      await sendWSMessage('memory_delete', { observation_id: obsId }, 5000);
      setObservations((prev) => prev.filter((o) => o.id !== obsId));
      if (selected?.id === obsId) closeDetail();
    } catch (err) {
      console.error('Failed to delete observation:', err);
      alert('Delete failed');
    }
  }, [sendWSMessage, selected, closeDetail]);

  const handleExtract = useCallback(async () => {
    if (!sendWSMessage || extracting) return;
    const instanceIdStr = prompt("Enter the active chat instance ID to extract observations from:");
    if (!instanceIdStr) return;
    const instanceId = parseInt(instanceIdStr, 10);
    if (!instanceId) {
      alert("Invalid instance ID");
      return;
    }
    setExtracting(true);
    try {
      const resp = await sendWSMessage('memory_extract', { instance_id: instanceId }, 30000);
      if (resp.data?.success) {
        alert(`Extraction complete! ${resp.data.extracted_count || 0} observation(s) extracted.`);
        fetchList();
      } else {
        alert("Extraction failed: " + (resp.data?.error || "Unknown error"));
      }
    } catch (err) {
      console.error('Extraction failed:', err);
      alert('Extraction failed: ' + err.message);
    } finally {
      setExtracting(false);
    }
  }, [sendWSMessage, extracting, fetchList]);

  const grouped = useMemo(() => {
    const groups = {};
    observations.forEach((obs) => {
      const date = obs.created_at ? new Date(obs.created_at).toLocaleDateString() : 'Unknown';
      if (!groups[date]) groups[date] = [];
      groups[date].push(obs);
    });
    return Object.entries(groups).sort((a, b) => new Date(b[0]) - new Date(a[0]));
  }, [observations]);

  return (
    <div className="panel memory-panel">
      <div className="window-header">
        <WindowDots />
        <span className="window-title">MEMORY STREAM</span>
        <button className="refresh-btn" onClick={fetchList} disabled={loading} title="Refresh">
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
        <button
          className="memory-extract-btn"
          onClick={handleExtract}
          disabled={extracting || loading}
          title="Extract observations from current chat"
        >
          {extracting ? 'Extracting...' : 'Extract from current chat'}
        </button>
      </div>

      <div className="memory-toolbar">
        <div className="memory-search">
          <Search size={14} />
          <input
            type="text"
            placeholder="Search observations..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="memory-filter">
          <Filter size={14} />
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="memory-layout">
        <div className={`memory-list ${detailOpen ? 'shrunk' : ''}`}>
          {grouped.length === 0 ? (
            <div className="memory-empty">
              <Brain size={48} opacity={0.3} />
              <p>No observations yet.</p>
              <span className="memory-empty-hint">
                Observations are automatically extracted when context is compressed.
              </span>
            </div>
          ) : (
            grouped.map(([date, items]) => (
              <div key={date} className="memory-day">
                <div className="memory-day-header">
                  <Clock size={12} />
                  {date}
                </div>
                <div className="memory-cards">
                  {items.map((obs) => (
                    <div
                      key={obs.id}
                      className={`memory-card ${selected?.id === obs.id ? 'active' : ''}`}
                      onClick={() => openDetail(obs)}
                    >
                      <div className="memory-card-top">
                        <span className="memory-type" title={TYPE_LABELS[obs.type] || obs.type}>
                          {TYPE_ICONS[obs.type] || '⚪'}
                        </span>
                        <span className="memory-title">{obs.title}</span>
                      </div>
                      <div className="memory-card-body">{truncate(obs.narrative, 140)}</div>
                      <div className="memory-card-footer">
                        <span className="memory-meta">
                          <Hash size={10} />#{obs.id}
                        </span>
                        {obs.token_count > 0 && (
                          <span className="memory-meta">~{obs.token_count} tokens</span>
                        )}
                        {obs.concepts?.length > 0 && (
                          <span className="memory-concepts">
                            {obs.concepts.slice(0, 3).map((c, i) => (
                              <span key={i} className="memory-concept">
                                {c}
                              </span>
                            ))}
                            {obs.concepts.length > 3 && (
                              <span className="memory-concept-more">+{obs.concepts.length - 3}</span>
                            )}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        {detailOpen && (
          <div className="memory-detail">
            <div className="memory-detail-header">
              <button className="memory-back" onClick={closeDetail}>
                <ChevronLeft size={16} />
                Back
              </button>
              <div className="memory-detail-actions">
                <button
                  className="memory-action promote"
                  onClick={() => handlePromote('memory')}
                  disabled={promoting}
                  title="Promote to MEMORY"
                >
                  {promoting ? '…' : 'Promote'}
                </button>
                <button
                  className="memory-action promote"
                  onClick={() => handlePromote('user')}
                  disabled={promoting}
                  title="Promote to USER PROFILE"
                >
                  {promoting ? '…' : 'User'}
                </button>
                <button
                  className="memory-action danger"
                  onClick={() => handleDelete(selected?.id)}
                  title="Delete"
                >
                  <Trash2 size={14} />
                </button>
                <button className="memory-action" onClick={closeDetail}>
                  <X size={14} />
                </button>
              </div>
            </div>

            {detailLoading ? (
              <div className="memory-detail-loading">Loading...</div>
            ) : selected ? (
              <div className="memory-detail-content">
                <div className="memory-detail-type">
                  <span className="memory-type large">
                    {TYPE_ICONS[selected.type] || '⚪'}
                  </span>
                  <span className="memory-detail-type-label">
                    {TYPE_LABELS[selected.type] || selected.type}
                  </span>
                </div>
                <h2 className="memory-detail-title">{selected.title}</h2>
                <div className="memory-detail-meta">
                  <span><Hash size={12} /> Observation #{selected.id}</span>
                  <span><Clock size={12} /> {formatTime(selected.created_at)}</span>
                  {selected.token_count > 0 && <span>~{selected.token_count} tokens</span>}
                </div>
                <div className="memory-detail-narrative">{selected.narrative}</div>

                {selected.files?.length > 0 && (
                  <div className="memory-detail-section">
                    <h4><FileText size={12} /> Referenced Files</h4>
                    <ul className="memory-file-list">
                      {selected.files.map((f, i) => (
                        <li key={i}>{f}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {selected.concepts?.length > 0 && (
                  <div className="memory-detail-section">
                    <h4><Tag size={12} /> Concepts</h4>
                    <div className="memory-concept-cloud">
                      {selected.concepts.map((c, i) => (
                        <span key={i} className="memory-concept large">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {timeline.length > 0 && (
                  <div className="memory-detail-section">
                    <h4>Timeline Context</h4>
                    <div className="memory-timeline">
                      {timeline.map((t, idx) => {
                        const isAnchor = t.id === selected.id;
                        return (
                          <div
                            key={t.id}
                            className={`memory-timeline-item ${isAnchor ? 'anchor' : ''}`}
                            onClick={() => !isAnchor && openDetail(t)}
                          >
                            <div className="memory-timeline-dot">
                              {isAnchor ? '★' : TYPE_ICONS[t.type] || '⚪'}
                            </div>
                            <div className="memory-timeline-body">
                              <div className="memory-timeline-title">{truncate(t.title, 60)}</div>
                              <div className="memory-timeline-time">{formatTime(t.created_at)}</div>
                            </div>
                            {!isAnchor && <ChevronRight size={12} className="memory-timeline-arrow" />}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}
      </div>

      <style>{`
        .memory-panel {
          height: 100%;
          display: flex;
          flex-direction: column;
          background: var(--surface);
          border: 1px solid var(--board);
          border-radius: var(--r-lg);
          overflow: hidden;
        }

        .refresh-btn {
          background: transparent;
          border: 1px solid var(--border);
          padding: 6px;
          border-radius: var(--r-sm);
          cursor: pointer;
          color: var(--text-2);
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .refresh-btn:hover { background: var(--surface-2); }
        .refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        .memory-extract-btn {
          background: var(--surface);
          border: 1px solid var(--border);
          color: var(--text);
          padding: 6px 12px;
          border-radius: var(--r-sm);
          font-size: 12px;
          cursor: pointer;
        }
        .memory-extract-btn:hover {
          background: var(--surface-2);
        }
        .memory-extract-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .memory-toolbar {
          display: flex;
          gap: var(--s-3);
          padding: var(--s-3) var(--s-4);
          border-bottom: 1px solid var(--border);
          background: var(--surface-2);
        }

        .memory-search {
          flex: 1;
          display: flex;
          align-items: center;
          gap: var(--s-2);
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--r-md);
          padding: 0 var(--s-3);
          color: var(--text-2);
        }
        .memory-search input {
          flex: 1;
          background: transparent;
          border: none;
          padding: var(--s-2) 0;
          color: var(--text);
          font-size: 13px;
          outline: none;
        }
        .memory-search input::placeholder { color: var(--text-3); }

        .memory-filter {
          display: flex;
          align-items: center;
          gap: var(--s-2);
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--r-md);
          padding: 0 var(--s-3);
          color: var(--text-2);
        }
        .memory-filter select {
          background: transparent;
          border: none;
          padding: var(--s-2) 0;
          color: var(--text);
          font-size: 13px;
          outline: none;
          cursor: pointer;
        }

        .memory-layout {
          flex: 1;
          display: flex;
          min-height: 0;
          overflow: hidden;
        }

        .memory-list {
          flex: 1;
          overflow-y: auto;
          padding: var(--s-3);
          transition: flex 0.25s ease;
        }
        .memory-list.shrunk {
          flex: 0 0 45%;
          border-right: 1px solid var(--border);
        }

        .memory-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: var(--text-3);
          text-align: center;
          padding: var(--s-6);
        }
        .memory-empty p { margin: var(--s-3) 0 0; font-size: 15px; }
        .memory-empty-hint {
          font-size: 12px;
          opacity: 0.7;
          margin-top: var(--s-2);
        }

        .memory-day { margin-bottom: var(--s-4); }
        .memory-day-header {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          font-weight: 600;
          color: var(--text-2);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: var(--s-2);
          padding-left: var(--s-1);
        }

        .memory-cards {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: var(--s-3);
        }

        .memory-card {
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: var(--r-md);
          padding: var(--s-3);
          cursor: pointer;
          transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
        }
        .memory-card:hover {
          border-color: var(--accent);
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .memory-card.active {
          border-color: var(--accent);
          box-shadow: 0 0 0 2px rgba(236, 94, 55, 0.2);
        }

        .memory-card-top {
          display: flex;
          align-items: center;
          gap: var(--s-2);
          margin-bottom: var(--s-2);
        }
        .memory-type {
          font-size: 14px;
          line-height: 1;
          flex-shrink: 0;
        }
        .memory-type.large { font-size: 20px; }
        .memory-title {
          font-weight: 600;
          font-size: 13px;
          color: var(--text);
          line-height: 1.3;
          overflow: hidden;
          text-overflow: ellipsis;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
        }

        .memory-card-body {
          font-size: 12px;
          color: var(--text-2);
          line-height: 1.45;
          margin-bottom: var(--s-2);
          overflow: hidden;
          text-overflow: ellipsis;
          display: -webkit-box;
          -webkit-line-clamp: 3;
          -webkit-box-orient: vertical;
        }

        .memory-card-footer {
          display: flex;
          align-items: center;
          gap: var(--s-2);
          flex-wrap: wrap;
        }
        .memory-meta {
          display: inline-flex;
          align-items: center;
          gap: 3px;
          font-size: 10px;
          color: var(--text-3);
          background: var(--surface-3);
          padding: 2px 6px;
          border-radius: var(--r-sm);
        }
        .memory-concepts {
          display: flex;
          gap: 4px;
          flex-wrap: wrap;
        }
        .memory-concept {
          font-size: 10px;
          color: var(--accent);
          background: rgba(236, 94, 55, 0.12);
          padding: 2px 6px;
          border-radius: var(--r-sm);
        }
        .memory-concept-more {
          font-size: 10px;
          color: var(--text-3);
          background: var(--surface-3);
          padding: 2px 6px;
          border-radius: var(--r-sm);
        }
        .memory-concept.large {
          font-size: 11px;
          padding: 3px 8px;
        }

        .memory-detail {
          flex: 1;
          display: flex;
          flex-direction: column;
          background: var(--surface);
          min-width: 0;
        }
        .memory-detail-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--s-3) var(--s-4);
          border-bottom: 1px solid var(--border);
          background: var(--surface-2);
        }
        .memory-back {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 12px;
          color: var(--text-2);
          background: transparent;
          border: none;
          cursor: pointer;
        }
        .memory-back:hover { color: var(--text); }
        .memory-detail-actions { display: flex; gap: var(--s-2); }
        .memory-action {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          border: 1px solid var(--border);
          background: var(--surface);
          color: var(--text-2);
          border-radius: var(--r-sm);
          cursor: pointer;
        }
        .memory-action:hover { background: var(--surface-3); color: var(--text); }
        .memory-action.danger:hover { color: #ef4444; border-color: #ef4444; }
        .memory-action.promote:hover { color: var(--accent); border-color: var(--accent); }

        .memory-detail-loading {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-3);
          font-size: 13px;
        }

        .memory-detail-content {
          flex: 1;
          overflow-y: auto;
          padding: var(--s-4);
        }

        .memory-detail-type {
          display: flex;
          align-items: center;
          gap: var(--s-2);
          margin-bottom: var(--s-2);
        }
        .memory-detail-type-label {
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.6px;
          color: var(--text-2);
        }
        .memory-detail-title {
          font-size: 18px;
          font-weight: 700;
          color: var(--text);
          margin: 0 0 var(--s-2) 0;
          line-height: 1.3;
        }
        .memory-detail-meta {
          display: flex;
          align-items: center;
          gap: var(--s-3);
          margin-bottom: var(--s-4);
          flex-wrap: wrap;
        }
        .memory-detail-meta span {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          font-size: 11px;
          color: var(--text-3);
        }
        .memory-detail-narrative {
          font-size: 13px;
          line-height: 1.65;
          color: var(--text-2);
          white-space: pre-wrap;
          margin-bottom: var(--s-4);
        }

        .memory-detail-section h4 {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          font-weight: 600;
          color: var(--text);
          margin: var(--s-4) 0 var(--s-2) 0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .memory-file-list {
          list-style: none;
          margin: 0;
          padding: 0;
          font-size: 12px;
          color: var(--text-2);
        }
        .memory-file-list li {
          padding: 4px 0;
          border-bottom: 1px dashed var(--border);
        }
        .memory-file-list li:last-child { border-bottom: none; }

        .memory-concept-cloud {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }

        .memory-timeline {
          display: flex;
          flex-direction: column;
          gap: var(--s-1);
        }
        .memory-timeline-item {
          display: flex;
          align-items: center;
          gap: var(--s-2);
          padding: var(--s-2) var(--s-3);
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: var(--r-md);
          cursor: pointer;
          transition: background 0.15s;
        }
        .memory-timeline-item:hover { background: var(--surface-3); }
        .memory-timeline-item.anchor {
          background: rgba(236, 94, 55, 0.08);
          border-color: rgba(236, 94, 55, 0.4);
          cursor: default;
        }
        .memory-timeline-dot {
          width: 22px;
          height: 22px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 11px;
          border-radius: 50%;
          background: var(--surface);
          flex-shrink: 0;
        }
        .memory-timeline-body {
          flex: 1;
          min-width: 0;
        }
        .memory-timeline-title {
          font-size: 12px;
          color: var(--text);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .memory-timeline-time {
          font-size: 10px;
          color: var(--text-3);
        }
        .memory-timeline-arrow {
          color: var(--text-3);
          flex-shrink: 0;
        }

        @media (max-width: 900px) {
          .memory-list.shrunk {
            display: none;
          }
          .memory-detail {
            position: absolute;
            inset: 0;
            z-index: 10;
          }
        }
      `}</style>
    </div>
  );
};

export default MemoryPanel;
