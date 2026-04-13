/**
 * 2D Force Graph implementation using PixiJS + Web Worker physics
 * Based on Obsidian's graph view implementation
 */
import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { message } from 'antd';
import { Search as SearchIcon, X, ZoomIn, ZoomOut, RotateCcw, Maximize, Minimize, Tag, Settings2, Play, Pause, Filter } from 'lucide-react';
import PixiGraph from './PixiGraph';

const CLUSTER_COLORS = [
  'var(--accent)',
  'var(--accent-green)',
  '#d97706', // amber
  '#7c3aed', // violet
  '#db2777', // pink
  '#0891b2', // cyan
  '#ea580c', // orange
  '#16a34a', // green
  '#2563eb', // blue
  '#9333ea', // purple
];

function getClusterColor(nodeId) {
  const dir = nodeId.includes('/') ? nodeId.substring(0, nodeId.lastIndexOf('/')) : '__root__';
  let hash = 0;
  for (let i = 0; i < dir.length; i++) {
    hash = dir.charCodeAt(i) + ((hash << 5) - hash);
  }
  const idx = Math.abs(hash) % CLUSTER_COLORS.length;
  return CLUSTER_COLORS[idx];
}

export default function KnowledgeGraphTab({ sendWSMessage, centerPath, onNodeNavigate, filterTag }) {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchValue, setSearchValue] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [tags, setTags] = useState([]);
  const [selectedTag, setSelectedTag] = useState(null);
  const [dims, setDims] = useState({ width: 0, height: 0 });
  const [highlightNodes, setHighlightNodes] = useState(new Set());
  const [highlightLinks, setHighlightLinks] = useState(new Set());
  const [hoverNode, setHoverNode] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [graphZoom, setGraphZoom] = useState(1);
  const [searchResultIds, setSearchResultIds] = useState(new Set());
  
  // Physics control state
  const [showPhysicsControls, setShowPhysicsControls] = useState(false);
  const [showSearchPanel, setShowSearchPanel] = useState(false);
  const [showTagPanel, setShowTagPanel] = useState(false);
  const [simulationRunning, setSimulationRunning] = useState(true);
  const [physicsParams, setPhysicsParams] = useState({
    centerStrength: 0.05,
    repelStrength: 300,
    linkStrength: 0.5,
    linkDistance: 60,
  });

  const wrapperRef = useRef(null);
  const graphContainerRef = useRef(null);
  const fgRef = useRef(null);
  const currentCenterRef = useRef(centerPath);

  const fetchGraph = async (center = null, depth = 1, tag = null) => {
    setLoading(true);
    try {
      const response = await sendWSMessage('knowledge_graph', {
        center,
        depth,
        limit: 200,
        tag,
      });
      const data = response.data || {};
      const edges = (data.edges || []).map((e) =>
        Array.isArray(e) ? { source: e[0], target: e[1] } : e
      );
      setSelectedNode(null);
      setHoverNode(null);
      setHighlightNodes(new Set());
      setHighlightLinks(new Set());
      setGraphData({
        nodes: data.nodes || [],
        edges,
        center,
      });
    } catch (err) {
      message.error('Failed to load graph: ' + (err.message || String(err)));
    } finally {
      setLoading(false);
    }
  };

  const fetchTags = async () => {
    try {
      const response = await sendWSMessage('knowledge_get_tags', {});
      setTags(response.data?.tags || []);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    currentCenterRef.current = centerPath;
    fetchGraph(centerPath, 1, selectedTag);
  }, [centerPath, selectedTag]);

  useEffect(() => {
    if (filterTag !== undefined && filterTag !== selectedTag) {
      setSelectedTag(filterTag || null);
    }
  }, [filterTag]);

  useEffect(() => {
    fetchTags();
  }, []);

  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  // Observe graph container size (RAF batching to avoid jitter)
  useEffect(() => {
    const el = graphContainerRef.current;
    if (!el) return;
    let rafId = null;
    const update = () => {
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        setDims({ width: el.clientWidth, height: el.clientHeight });
        rafId = null;
      });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      ro.disconnect();
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, []);

  const fgData = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    const links = graphData.edges.map((e) => ({
      source: e.source,
      target: e.target,
    }));

    const nodes = graphData.nodes.map((node) => ({
      id: node.id,
      label: node.label || node.id,
      color: node.id === graphData.center ? 'rgba(131,94,228,1)' : '#cbd5e1',
      val: 5,
      degree: 0,
      neighbors: [],
      links: [],
      isCenter: node.id === graphData.center,
    }));

    // cross-link and compute degree
    links.forEach((link) => {
      const a = nodes.find((n) => n.id === link.source);
      const b = nodes.find((n) => n.id === link.target);
      if (a && b) {
        a.neighbors.push(b);
        b.neighbors.push(a);
        a.links.push(link);
        b.links.push(link);
      }
    });

    const degrees = nodes.map((n) => n.links.length);
    const maxDeg = Math.max(...degrees, 1);
    const minDeg = Math.min(...degrees, 0);

    nodes.forEach((n) => {
      n.degree = n.links.length;

      if (n.isCenter) {
        // 中心节点固定较大
        n.val = 12;
      } else if (maxDeg === minDeg) {
        n.val = 3;
      } else {
        // 使用混合缩放策略：对数 + 幂函数，突出高连接节点
        const raw = n.links.length + 1;
        const normalized = raw / (maxDeg + 1);
        // 对数缩放：让差异更平滑
        const logScale = Math.log(raw) / Math.log(maxDeg + 1);
        // 幂函数：突出高连接节点
        const powScale = Math.pow(normalized, 0.6);
        // 混合：中间偏对数，尾部偏幂函数
        const mixed = logScale * 0.4 + powScale * 0.6;
        n.val = 2 + mixed * 14; // 范围 2~16px
      }
    });

    return { nodes, links };
  }, [graphData]);

  const focusNode = useCallback(
    (nodeId) => {
      if (!fgRef.current || !nodeId) return;
      const node = fgData.nodes.find((n) => n.id === nodeId);
      if (!node || node.x == null) return;
      fgRef.current.centerAt(node.x, node.y);
      fgRef.current.zoom(2, 400);
    },
    [fgData]
  );

  const applyHighlight = useCallback((hovered, selected) => {
    const nextNodes = new Set();
    const nextLinks = new Set();
    if (selected) {
      nextNodes.add(selected);
      if (selected.neighbors) selected.neighbors.forEach((n) => nextNodes.add(n));
      if (selected.links) selected.links.forEach((l) => nextLinks.add(l));
    }
    if (hovered) {
      nextNodes.add(hovered);
      if (hovered.neighbors) hovered.neighbors.forEach((n) => nextNodes.add(n));
      if (hovered.links) hovered.links.forEach((l) => nextLinks.add(l));
    }
    setHighlightNodes(nextNodes);
    setHighlightLinks(nextLinks);
  }, []);

  const handleNodeClick = useCallback(
    (node) => {
      if (!node) return;
      setSelectedNode(node);
      applyHighlight(hoverNode, node);
      focusNode(node.id);
      if (onNodeNavigate) {
        onNodeNavigate(node.id);
      }
    },
    [focusNode, hoverNode, applyHighlight, onNodeNavigate]
  );

  const handleNodeDoubleClick = useCallback(
    (node) => {
      if (!node || !onNodeNavigate) return;
      onNodeNavigate(node.id);
    },
    [onNodeNavigate]
  );

  const handleNodeHover = useCallback((node) => {
    setHoverNode(node || null);
    applyHighlight(node || null, selectedNode);
  }, [selectedNode, applyHighlight]);

  const handleLinkHover = useCallback((link) => {
    const nextNodes = new Set();
    const nextLinks = new Set();
    if (selectedNode) {
      nextNodes.add(selectedNode);
      if (selectedNode.neighbors) selectedNode.neighbors.forEach((n) => nextNodes.add(n));
      if (selectedNode.links) selectedNode.links.forEach((l) => nextLinks.add(l));
    }
    if (link) {
      nextLinks.add(link);
      nextNodes.add(link.source);
      nextNodes.add(link.target);
    }
    setHoverNode(null);
    setHighlightNodes(nextNodes);
    setHighlightLinks(nextLinks);
  }, [selectedNode]);

  const handleBackgroundClick = useCallback(() => {
    setSelectedNode(null);
    setHoverNode(null);
    setHighlightNodes(new Set());
    setHighlightLinks(new Set());
  }, []);

  const zoomIn = () => {
    if (!fgRef.current) return;
    fgRef.current.zoomIn();
  };

  const zoomOut = () => {
    if (!fgRef.current) return;
    fgRef.current.zoomOut();
  };

  const resetView = () => {
    if (!fgRef.current) return;
    fgRef.current.zoomToFit();
  };

  const toggleSimulation = () => {
    setSimulationRunning(!simulationRunning);
    if (fgRef.current) {
      if (simulationRunning) {
        fgRef.current.stopSimulation();
      } else {
        fgRef.current.reheat();
      }
    }
  };

  const updatePhysicsParam = (key, value) => {
    const newParams = { ...physicsParams, [key]: parseFloat(value) };
    setPhysicsParams(newParams);
    if (fgRef.current) {
      fgRef.current.updateForces({
        [key === 'centerStrength' ? 'centerStrength' : 
         key === 'repelStrength' ? 'repelStrength' :
         key === 'linkStrength' ? 'linkStrength' : 'linkDistance']: parseFloat(value)
      });
    }
  };

  const toggleFullscreen = async () => {
    if (!wrapperRef.current) return;
    if (!document.fullscreenElement) {
      await wrapperRef.current.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  };

  const handleSearch = async (query) => {
    const q = query ?? searchValue;
    if (!q || !q.trim()) {
      setSearchValue('');
      setSearchResultIds(new Set());
      fetchGraph(currentCenterRef.current, 1, selectedTag);
      return;
    }
    try {
      const response = await sendWSMessage('knowledge_search', { query: q });
      const results = response.data?.results || [];
      if (results.length > 0) {
        const first = results[0];
        const path = first.path || first.id;
        // 保存所有搜索结果的 ID 用于高亮标记
        const resultIds = new Set(results.map((r) => r.path || r.id));
        setSearchResultIds(resultIds);
        if (path) {
          fetchGraph(path, 1, selectedTag);
          setTimeout(() => focusNode(path), 350);
        } else {
          message.info('No valid path found in search result');
        }
      } else {
        setSearchResultIds(new Set());
        message.info('No matching notes found');
      }
    } catch (err) {
      setSearchResultIds(new Set());
      message.error('Search failed: ' + (err.message || String(err)));
    }
  };

  return (
    <div ref={wrapperRef} style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', background: isFullscreen ? 'var(--bg)' : undefined }}>
      {/* Header - Legend & Zoom Info Only */}
      {/* <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '10px 16px',
          background: 'var(--surface-2)',
          borderBottom: '1px solid var(--border)',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <LegendItem color='rgba(131,94,228,1)' label="Center" />
          <LegendItem color='var(--text-2)' label="Linked" />
          <LegendItem color="#707070" label="Edge" />
          <LegendItem color="#22d3ee" label="Search" dashed />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {selectedTag && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 10px',
                borderRadius: 4,
                background: 'var(--accent-soft)',
                border: '1px solid var(--accent)',
                fontSize: 12,
                color: 'var(--accent)',
              }}
            >
              <Tag size={12} />
              <span>#{selectedTag}</span>
              <button
                onClick={() => setSelectedTag(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  padding: 0,
                  marginLeft: 4,
                  cursor: 'pointer',
                  color: 'var(--accent)',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <X size={12} />
              </button>
            </div>
          )}
          {searchValue && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 10px',
                borderRadius: 4,
                background: 'rgba(34, 211, 238, 0.1)',
                border: '1px solid rgba(34, 211, 238, 0.3)',
                fontSize: 12,
                color: '#22d3ee',
              }}
            >
              <SearchIcon size={12} />
              <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {searchValue}
              </span>
              <button
                onClick={() => {
                  setSearchValue('');
                  setSearchResultIds(new Set());
                  fetchGraph(currentCenterRef.current, 1, selectedTag);
                }}
                style={{
                  background: 'transparent',
                  border: 'none',
                  padding: 0,
                  marginLeft: 4,
                  cursor: 'pointer',
                  color: '#22d3ee',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <X size={12} />
              </button>
            </div>
          )}
          <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
          <span style={{ fontSize: 12, color: 'var(--text-2)', fontFamily: 'monospace' }}>
            {Math.round(graphZoom * 100)}%
          </span>
        </div>
      </div> */}

      <div
        ref={graphContainerRef}
        style={{
          flex: 1,
          position: 'relative',
          background: '#111827',
          // borderRadius: 8,
          // margin: 16,
          overflow: 'hidden',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <PixiGraph
          ref={fgRef}
          graphData={fgData}
          highlightNodes={highlightNodes}
          highlightLinks={highlightLinks}
          searchResultIds={searchResultIds}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeDoubleClick}
          onBackgroundClick={handleBackgroundClick}
          onNodeHover={handleNodeHover}
          onZoom={({ k }) => setGraphZoom(k)}
          active={simulationRunning}
          centerStrength={physicsParams.centerStrength}
          repelStrength={physicsParams.repelStrength}
          linkStrength={physicsParams.linkStrength}
          linkDistance={physicsParams.linkDistance}
        />

        {/* Floating controls */}
        <div
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            background: 'rgba(17,24,39,0.7)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 8,
            padding: 6,
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
            backdropFilter: 'blur(4px)',
          }}
        >
          <ToolButton onClick={() => { setShowSearchPanel(!showSearchPanel); setShowTagPanel(false); setShowPhysicsControls(false); }} title="Search notes" icon={<SearchIcon size={18} />} active={showSearchPanel} />
          <ToolButton onClick={() => { setShowTagPanel(!showTagPanel); setShowSearchPanel(false); setShowPhysicsControls(false); }} title="Filter by tag" icon={<Filter size={18} />} active={showTagPanel || selectedTag} />
          <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', margin: '2px 0' }} />
          <ToolButton onClick={zoomIn} title="Zoom in" icon={<ZoomIn size={18} />} />
          <ToolButton onClick={zoomOut} title="Zoom out" icon={<ZoomOut size={18} />} />
          <ToolButton onClick={resetView} title="Reset view" icon={<RotateCcw size={18} />} />
          <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', margin: '2px 0' }} />
          <ToolButton onClick={toggleSimulation} title={simulationRunning ? 'Pause simulation' : 'Resume simulation'} icon={simulationRunning ? <Pause size={18} /> : <Play size={18} />} />
          <ToolButton onClick={() => { setShowPhysicsControls(!showPhysicsControls); setShowSearchPanel(false); setShowTagPanel(false); }} title="Physics settings" icon={<Settings2 size={18} />} active={showPhysicsControls} />
          <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', margin: '2px 0' }} />
          <ToolButton onClick={toggleFullscreen} title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'} icon={isFullscreen ? <Minimize size={18} /> : <Maximize size={18} />} />
        </div>

        {/* Search Panel */}
        {showSearchPanel && (
          <div
            style={{
              position: 'absolute',
              top: 12,
              right: 56,
              width: 280,
              background: 'rgba(17,24,39,0.9)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 10,
              padding: 12,
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              backdropFilter: 'blur(16px)',
              zIndex: 100,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <SearchIcon size={14} />
              Search Notes
            </div>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                placeholder="Type to search..."
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSearch(searchValue);
                  }
                }}
                disabled={loading}
                autoFocus
                style={{
                  width: '100%',
                  padding: '8px 32px 8px 12px',
                  borderRadius: 6,
                  border: '1px solid rgba(255,255,255,0.15)',
                  background: 'rgba(255,255,255,0.05)',
                  color: '#e2e8f0',
                  fontSize: 13,
                  outline: 'none',
                  transition: 'all 0.2s',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = 'rgba(131,94,228,0.8)';
                  e.target.style.background = 'rgba(255,255,255,0.08)';
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = 'rgba(255,255,255,0.15)';
                  e.target.style.background = 'rgba(255,255,255,0.05)';
                }}
              />
              <button
                onClick={() => handleSearch(searchValue)}
                disabled={loading}
                style={{
                  position: 'absolute',
                  right: 6,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  padding: 4,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  color: loading ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.6)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 4,
                }}
              >
                <SearchIcon size={16} />
              </button>
            </div>
            {searchValue && (
              <button
                onClick={() => {
                  setSearchValue('');
                  setSearchResultIds(new Set());
                  fetchGraph(currentCenterRef.current, 1, selectedTag);
                }}
                style={{
                  marginTop: 8,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: '1px solid rgba(255,255,255,0.1)',
                  background: 'rgba(255,255,255,0.05)',
                  color: 'rgba(255,255,255,0.7)',
                  cursor: 'pointer',
                  fontSize: 11,
                  width: '100%',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.1)';
                  e.currentTarget.style.color = '#fff';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.05)';
                  e.currentTarget.style.color = 'rgba(255,255,255,0.7)';
                }}
              >
                <X size={12} />
                <span>Clear Search</span>
              </button>
            )}
          </div>
        )}

        {/* Tag Filter Panel */}
        {showTagPanel && tags.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: 56,
              right: 56,
              width: 220,
              maxHeight: 320,
              overflow: 'auto',
              background: 'rgba(17,24,39,0.9)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 10,
              padding: 12,
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              backdropFilter: 'blur(16px)',
              zIndex: 100,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Tag size={14} />
              Filter by Tag
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <button
                onClick={() => setSelectedTag(null)}
                style={{
                  padding: '8px 12px',
                  borderRadius: 6,
                  border: '1px solid',
                  borderColor: selectedTag === null ? 'rgba(131,94,228,0.8)' : 'rgba(255,255,255,0.1)',
                  background: selectedTag === null ? 'rgba(131,94,228,0.2)' : 'rgba(255,255,255,0.05)',
                  color: selectedTag === null ? '#a78bfa' : 'rgba(255,255,255,0.8)',
                  fontSize: 12,
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s',
                }}
              >
                All Tags
              </button>
              {tags.map((t) => (
                <button
                  key={t.name}
                  onClick={() => setSelectedTag(t.name === selectedTag ? null : t.name)}
                  style={{
                    padding: '8px 12px',
                    borderRadius: 6,
                    border: '1px solid',
                    borderColor: t.name === selectedTag ? 'rgba(131,94,228,0.8)' : 'rgba(255,255,255,0.1)',
                    background: t.name === selectedTag ? 'rgba(131,94,228,0.2)' : 'rgba(255,255,255,0.05)',
                    color: t.name === selectedTag ? '#a78bfa' : 'rgba(255,255,255,0.8)',
                    fontSize: 12,
                    cursor: 'pointer',
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.15s',
                  }}
                >
                  <span>#{t.name}</span>
                  <span style={{ opacity: 0.5, fontSize: 11 }}>{t.count}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Physics Controls Panel */}
        {showPhysicsControls && (
          <div
            style={{
              position: 'absolute',
              top: 12,
              right: 56,
              width: 220,
              background: 'rgba(17,24,39,0.85)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              padding: 12,
              boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
              backdropFilter: 'blur(12px)',
              zIndex: 100,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 500, color: '#e2e8f0', marginBottom: 12 }}>Physics Settings</div>
            
            <PhysicsSlider
              label="Center strength"
              value={physicsParams.centerStrength}
              min={0}
              max={1}
              step={0.01}
              onChange={(v) => updatePhysicsParam('centerStrength', v)}
            />
            <PhysicsSlider
              label="Repulsion"
              value={physicsParams.repelStrength}
              min={0}
              max={3000}
              step={50}
              onChange={(v) => updatePhysicsParam('repelStrength', v)}
            />
            <PhysicsSlider
              label="Link strength"
              value={physicsParams.linkStrength}
              min={0}
              max={2}
              step={0.01}
              onChange={(v) => updatePhysicsParam('linkStrength', v)}
            />
            <PhysicsSlider
              label="Link distance"
              value={physicsParams.linkDistance}
              min={10}
              max={500}
              step={5}
              onChange={(v) => updatePhysicsParam('linkDistance', v)}
            />
          </div>
        )}

        {!loading && graphData && graphData.nodes.length === 0 && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              color: 'var(--text-2)',
              fontSize: 14,
              pointerEvents: 'none',
              textAlign: 'center',
              padding: 24,
            }}
          >
            <div>
              <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8, color: '#e2e8f0' }}>No notes indexed yet</div>
              <div style={{ fontSize: 13, color: 'rgba(226,232,240,0.6)' }}>
                Create a note or distill a document to see the knowledge graph.
              </div>
            </div>
          </div>
        )}
        {loading && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(17, 24, 39, 0.6)',
              color: '#e2e8f0',
              fontSize: 14,
              pointerEvents: 'none',
            }}
          >
            Loading graph...
          </div>
        )}
      </div>
    </div>
  );
}

function ToolButton({ onClick, title, icon, active }) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        width: 32,
        height: 32,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 6,
        border: 'none',
        background: active ? 'rgba(255,255,255,0.15)' : 'transparent',
        color: active ? '#fff' : 'rgba(255,255,255,0.75)',
        cursor: 'pointer',
        transition: 'all 0.15s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'rgba(255,255,255,0.1)';
        e.currentTarget.style.color = '#fff';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = active ? 'rgba(255,255,255,0.15)' : 'transparent';
        e.currentTarget.style.color = active ? '#fff' : 'rgba(255,255,255,0.75)';
      }}
    >
      {icon}
    </button>
  );
}

function PhysicsSlider({ label, value, min, max, step, onChange }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)' }}>{label}</span>
        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', fontFamily: 'monospace' }}>{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: '100%',
          height: 4,
          WebkitAppearance: 'none',
          appearance: 'none',
          background: 'rgba(255,255,255,0.15)',
          borderRadius: 2,
          outline: 'none',
          cursor: 'pointer',
        }}
      />
    </div>
  );
}

function LegendItem({ color, label, dashed }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span
        style={{
          width: 10,
          height: 10,
          borderRadius: label === 'Edge' ? 1 : '50%',
          background: dashed ? 'transparent' : color,
          border: dashed ? `2px ${color} dashed` : 'none',
          display: 'inline-block',
        }}
      />
      <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{label}</span>
    </div>
  );
}
