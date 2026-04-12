/**
 * PixiGraph - WebGL-accelerated force graph using PixiJS + Web Worker physics
 *
 * Based on Obsidian's graph view implementation.
 */

import React, {
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
  forwardRef,
  useImperativeHandle,
} from 'react';
import { PixiGraphRenderer } from './PixiGraphRenderer';
import { useGraphSimulation } from './useGraphSimulation';

const PixiGraph = forwardRef(({
  graphData,
  highlightNodes,
  highlightLinks,
  searchResultIds,
  onNodeClick,
  onNodeHover,
  onNodeDoubleClick,
  onBackgroundClick,
  onZoom,
  active = true,
  // Physics parameters
  centerStrength = 0.05,
  repelStrength = 300,
  linkStrength = 0.5,
  linkDistance = 60,
}, ref) => {
  const containerRef = useRef(null);
  const rendererRef = useRef(null);
  const [ready, setReady] = useState(false);
  const hasFittedRef = useRef(false);
  const hasReceivedWorkerDataRef = useRef(false);

  // Simulation tick handler - receives data from Worker
  const handleTick = useCallback(({ buffer, idMapping, version }) => {
    if (rendererRef.current) {
      rendererRef.current.updatePositionsFromWorker({ buffer, idMapping, version });
    }
    // Trigger fit to screen on first worker data
    if (!hasReceivedWorkerDataRef.current && buffer && idMapping) {
      hasReceivedWorkerDataRef.current = true;
      if (rendererRef.current && !hasFittedRef.current) {
        hasFittedRef.current = true;
        setTimeout(() => {
          rendererRef.current?.fitToScreen();
        }, 100);
      }
    }
  }, []);

  // Initialize simulation with Worker
  const {
    isReady: simReady,
    fixNode: simFixNode,
    unfixNode: simUnfixNode,
    setAlphaTarget: simSetAlphaTarget,
    updateForces,
    reheat: simReheat,
    stop: simStop,
  } = useGraphSimulation(graphData, {
    active,
    centerStrength,
    repelStrength,
    linkStrength,
    linkDistance,
    onTick: handleTick,
  });

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    zoomIn: () => rendererRef.current?.zoomIn(),
    zoomOut: () => rendererRef.current?.zoomOut(),
    zoomToFit: () => rendererRef.current?.fitToScreen(),
    centerAt: (x, y) => rendererRef.current?.centerAt(x, y),
    reheat: () => simReheat(),
    zoom: (k, ms) => {
      if (!rendererRef.current) return;
      const renderer = rendererRef.current;
      const clampedK = Math.max(0.05, Math.min(5, k));
      const startK = renderer.scale;
      const duration = ms || 400;
      const startTime = performance.now();
      const startX = renderer.viewport.x;
      const startY = renderer.viewport.y;
      const cx = renderer.app.canvas.clientWidth / 2;
      const cy = renderer.app.canvas.clientHeight / 2;
      
      const animate = (time) => {
        const t = Math.min(1, (time - startTime) / duration);
        const eased = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
        const currentK = startK + (clampedK - startK) * eased;
        
        renderer.scale = currentK;
        renderer.viewport.scale.set(currentK);
        renderer.viewport.x = cx - (cx - startX) * (currentK / startK);
        renderer.viewport.y = cy - (cy - startY) * (currentK / startK);
        
        if (t < 1) requestAnimationFrame(animate);
      };
      requestAnimationFrame(animate);
    },
    d3Force: () => {},
    updateForces,
    stopSimulation: simStop,
  }));

  const simData = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };

    // Support both 'links' and 'edges' property names
    const links = graphData.links || graphData.edges || [];

    const nodes = graphData.nodes.map((node) => ({
      id: node.id,
      label: node.label || node.id,
      color: node.id === graphData.center ? 'rgba(131,94,228,1)' : '#cbd5e1',
      isCenter: node.id === graphData.center,
    }));

    return { nodes, links };
  }, [graphData]);

  // Initialize renderer
  useEffect(() => {
    if (!containerRef.current) return;

    const renderer = new PixiGraphRenderer(containerRef.current, {
      onNodeClick: (node, e) => {
        if (onNodeClick) {
          const original = graphData?.nodes?.find((n) => n.id === node.id);
          onNodeClick(original || node, e);
        }
      },
      onNodeHover: (node) => {
        if (onNodeHover) onNodeHover(node);
      },
      onNodeDoubleClick: (node, e) => {
        if (onNodeDoubleClick) onNodeDoubleClick(node, e);
      },
      onBackgroundClick: (e) => {
        if (onBackgroundClick) onBackgroundClick(e);
      },
      onZoom: ({ k, x, y }) => {
        if (onZoom) onZoom({ k, x, y });
      },
      onDragEnd: (info) => {
        if (info?.id) simUnfixNode(info.id);
        simSetAlphaTarget(0);
      },
    });

    renderer.onDragStart = (nodeData) => {
      simFixNode(nodeData.id, nodeData.x, nodeData.y);
      simSetAlphaTarget(0.3);
    };

    renderer.onDragMove = (nodeId, x, y) => {
      simFixNode(nodeId, x, y);
    };

    rendererRef.current = renderer;

    const checkReady = setInterval(() => {
      if (renderer.app && renderer.viewport && renderer.nodeLayer && renderer.linkGraphics && renderer.labelLayer) {
        setReady(true);
        clearInterval(checkReady);
      }
    }, 50);

    return () => {
      clearInterval(checkReady);
      if (rendererRef.current) {
        rendererRef.current.destroy();
        rendererRef.current = null;
      }
    };
  }, []);

  // Update graph data
  useEffect(() => {
    if (!rendererRef.current || !ready) return;
    rendererRef.current.updateData(simData);
  }, [simData, ready]);

  // Update highlights
  useEffect(() => {
    if (!rendererRef.current || !ready) return;
    rendererRef.current.setHighlightNodes(highlightNodes || new Set());
    rendererRef.current.setHighlightLinks(highlightLinks || new Set());
  }, [highlightNodes, highlightLinks, ready]);

  // Update search results
  useEffect(() => {
    if (!rendererRef.current || !ready) return;
    rendererRef.current.setSearchResults(searchResultIds || new Set());
  }, [searchResultIds, ready]);

  // Handle resize
  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver(() => {
      if (rendererRef.current?.app) {
        rendererRef.current.resize();
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [ready]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        overflow: 'hidden',
        background: '#1e1e1e',
      }}
    />
  );
});

PixiGraph.displayName = 'PixiGraph';

export default PixiGraph;
