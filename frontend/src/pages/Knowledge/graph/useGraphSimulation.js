/**
 * useGraphSimulation - Web Worker-based physics engine hook
 *
 * Uses Web Worker to run D3-force simulation off the main thread.
 * Communicates with worker via SharedArrayBuffer (if supported) or ArrayBuffer.
 */

import { useRef, useEffect, useCallback, useState } from 'react';

// Worker URL - will be resolved by bundler
const WORKER_URL = new URL('./simulation.worker.js', import.meta.url);

/**
 * Hook that manages a Web Worker-based force simulation
 *
 * @param {object} graphData - { nodes: [], links: [] }
 * @param {object} options
 * @param {boolean} options.active - whether simulation should run
 * @param {number} options.centerStrength - center force strength (default: 0.05)
 * @param {number} options.repelStrength - repulsion strength (default: 300)
 * @param {number} options.linkStrength - link strength (default: 0.5)
 * @param {number} options.linkDistance - ideal link distance (default: 60)
 * @param {function} options.onTick - called every simulation tick with position data
 */
export function useGraphSimulation(graphData, options = {}) {
  const {
    active = true,
    centerStrength = 0.05,
    repelStrength = 300,
    linkStrength = 0.5,
    linkDistance = 60,
    onTick,
  } = options;

  const workerRef = useRef(null);
  const nodesRef = useRef([]);
  const idMappingRef = useRef([]);
  const coordBufferRef = useRef(null);
  const versionRef = useRef(0);
  const runningRef = useRef(active);
  const [isReady, setIsReady] = useState(false);

  // Keep running state in sync
  useEffect(() => {
    runningRef.current = active;
    if (workerRef.current) {
      workerRef.current.postMessage({ run: active });
    }
  }, [active]);

  // Initialize worker
  useEffect(() => {
    const worker = new Worker(WORKER_URL, { type: 'module' });
    workerRef.current = worker;

    worker.onmessage = (e) => {
      const data = e.data;
      if (data.ignore) return;
      
      if (data.buffer) {
        coordBufferRef.current = new Float32Array(data.buffer);
        idMappingRef.current = data.id;
        versionRef.current = data.v;
        
        if (onTick) {
          onTick({
            buffer: coordBufferRef.current,
            idMapping: idMappingRef.current,
            version: versionRef.current,
          });
        }
      }
    };

    setIsReady(true);

    return () => {
      worker.terminate();
      workerRef.current = null;
    };
  }, [onTick]);

  // Send graph data to worker
  useEffect(() => {
    if (!workerRef.current || !graphData || !isReady) return;

    // Convert nodes to worker format: { id: [x, y] }
    const nodeCount = graphData.nodes.length;
    const nodes = {};
    const idMapping = [];
    
    graphData.nodes.forEach((n, i) => {
      const angle = (i / nodeCount) * Math.PI * 2;
      const spread = Math.min(300, Math.max(60, nodeCount * 20));
      const r = spread * (0.3 + Math.random() * 0.7);
      const x = n.x ?? Math.cos(angle) * r + (Math.random() - 0.5) * 50;
      const y = n.y ?? Math.sin(angle) * r + (Math.random() - 0.5) * 50;
      nodes[n.id] = [x, y];
      idMapping.push(n.id);
    });

    // Convert links to worker format: [[sourceId, targetId], ...]
    const links = graphData.links.map((l) => [
      typeof l.source === 'object' ? l.source.id : l.source,
      typeof l.target === 'object' ? l.target.id : l.target,
    ]);

    nodesRef.current = graphData.nodes;
    idMappingRef.current = idMapping;

    workerRef.current.postMessage({
      nodes,
      links,
      forces: {
        centerStrength,
        repelStrength,
        linkStrength,
        linkDistance,
      },
      alpha: 1,
      alphaTarget: 0,
      run: runningRef.current,
    });
  }, [graphData, centerStrength, repelStrength, linkStrength, linkDistance, isReady]);

  // Update forces without restarting
  const updateForces = useCallback((forces) => {
    if (workerRef.current) {
      workerRef.current.postMessage({ forces });
    }
  }, []);

  // Fix node position (for dragging)
  const fixNode = useCallback((nodeId, x, y) => {
    if (workerRef.current) {
      workerRef.current.postMessage({
        forceNode: { id: nodeId, x, y },
        alpha: 1.5,
        alphaTarget: 0.3,
        run: runningRef.current,
      });
    }
  }, []);

  // Unfix node position
  const unfixNode = useCallback((nodeId) => {
    if (workerRef.current) {
      workerRef.current.postMessage({
        forceNode: { id: nodeId, x: null, y: null },
        alphaTarget: 0,
        run: runningRef.current,
      });
    }
  }, []);

  // Restart simulation
  const restart = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.postMessage({
        alpha: 0.5,
        run: true,
      });
    }
  }, []);

  // Reheat simulation
  const reheat = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.postMessage({
        alpha: 1,
        run: true,
      });
    }
  }, []);

  // Stop simulation
  const stop = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.postMessage({ run: false });
    }
  }, []);

  // Set alpha target
  const setAlphaTarget = useCallback((target) => {
    if (workerRef.current) {
      workerRef.current.postMessage({
        alphaTarget: target,
        run: runningRef.current,
      });
    }
  }, []);

  return {
    isReady,
    nodes: nodesRef.current,
    idMapping: idMappingRef.current,
    coordBuffer: coordBufferRef.current,
    version: versionRef.current,
    updateForces,
    fixNode,
    unfixNode,
    restart,
    reheat,
    stop,
    setAlphaTarget,
  };
}
