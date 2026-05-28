import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { RotateCcw } from 'lucide-react';
import { Button, Spin } from 'antd';
import PixiGraph from '../graph/PixiGraph';

const LibraryGraphTab = ({ sendWSMessage, collectionId, onNodeNavigate }) => {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const fgRef = useRef(null);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const payload = { limit: 300 };
      if (collectionId) payload.collection_id = collectionId;
      const response = await sendWSMessage('library_graph', payload, 15000);
      if (response?.data?.nodes) {
        setGraphData(response.data);
      }
    } catch (e) {
      console.error('Failed to fetch library graph:', e);
    } finally {
      setLoading(false);
    }
  }, [collectionId, sendWSMessage]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const fgData = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    const links = graphData.edges.map((e) => ({
      source: e.source,
      target: e.target,
    }));

    const nodes = graphData.nodes.map((node) => ({
      ...node,
      label: node.label || node.id,
      val: 5,
      degree: 0,
      neighbors: [],
      links: [],
    }));

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    links.forEach((link) => {
      const a = nodeMap.get(link.source);
      const b = nodeMap.get(link.target);
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
      if (maxDeg === minDeg) {
        n.val = 3;
      } else {
        const raw = n.links.length + 1;
        const normalized = raw / (maxDeg + 1);
        const logScale = Math.log(raw) / Math.log(maxDeg + 1);
        const powScale = Math.pow(normalized, 0.6);
        const mixed = logScale * 0.4 + powScale * 0.6;
        n.val = 2 + mixed * 14;
      }
    });

    return { nodes, links };
  }, [graphData]);

  const handleNodeClick = useCallback(
    (node) => {
      if (!node) return;
      // Extract item_id from note path (e.g. "knowledge/library/00049_slug/paper.md" → 49)
      const itemId = node.item_id || (node.id && parseInt(node.id.match(/knowledge\/library\/(\d+)_/)?.[1], 10));
      if (itemId && onNodeNavigate) {
        onNodeNavigate(itemId);
      }
    },
    [onNodeNavigate]
  );

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', position: 'relative' }}>
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '6px 12px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
          background: 'var(--bg-elevated)',
        }}
      >
        <Button size="small" icon={<RotateCcw size={14} />} onClick={fetchGraph} loading={loading}>
          Refresh
        </Button>
        {graphData && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {graphData.nodes.length} nodes · {graphData.edges.length} edges
          </span>
        )}
      </div>

      {/* Graph canvas */}
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        {loading && !graphData && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10 }}>
            <Spin size="large" />
          </div>
        )}
        {fgData.nodes.length > 0 && (
          <PixiGraph
            ref={fgRef}
            graphData={fgData}
            onNodeClick={handleNodeClick}
            centerStrength={0.05}
            repelStrength={300}
            linkStrength={0.3}
            linkDistance={80}
          />
        )}
        {!loading && fgData.nodes.length === 0 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: 14 }}>
            No papers to visualize
          </div>
        )}
      </div>
    </div>
  );
};

export default LibraryGraphTab;
