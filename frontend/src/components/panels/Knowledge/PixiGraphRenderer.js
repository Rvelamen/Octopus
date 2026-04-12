/**
 * PixiGraphRenderer - WebGL-accelerated graph rendering using PixiJS
 * 
 * Based on Obsidian's graph view implementation.
 * Uses viewport-based zoom/pan with consistent visual sizing.
 */

import * as PIXI from 'pixi.js';

// Color palette (matching HTML version)
const COLORS = {
  node: 0xaaaab2,
  hover: 0x835ee4,
  drag: 0x835ee4,
  line: 0x3f3f3f,
  activeLine: 0x7a55e4,
  label: 0xdadada,
};

const LABEL_FONT_SIZE = 10;

export class PixiGraphRenderer {
  constructor(container, {
    onNodeClick,
    onNodeHover,
    onNodeDoubleClick,
    onBackgroundClick,
    onZoom,
    onDragEnd,
  } = {}) {
    this.container = container;
    this.onNodeClick = onNodeClick || (() => {});
    this.onNodeHover = onNodeHover || (() => {});
    this.onNodeDoubleClick = onNodeDoubleClick || (() => {});
    this.onBackgroundClick = onBackgroundClick || (() => {});
    this.onZoom = onZoom || (() => {});
    this.onDragEnd = onDragEnd || (() => {});
    this.onDragStart = (() => {});
    this.onDragMove = (() => {});

    // Viewport transform state (matching HTML version)
    this.scale = 1;
    this.viewportX = 0;
    this.viewportY = 0;

    // Interaction state
    this.isPanning = false;
    this.lastPan = null;
    this.draggedId = null;
    this.hoveredId = null;

    // Node/link data
  this.nodes = new Map();
  this.links = new Map();
  this.nodeSprites = {};
  this.labelSprites = {};
  this.linkIndices = [];

  // Hover border
  this.HOVER_BORDER_COLOR = 0xa18bf2;
  this.HOVER_BORDER_WIDTH = 2;

    // Highlight state
    this.highlightNodes = new Set();
    this.highlightLinks = new Set();
    this.searchResultIds = new Set();

    // Worker data
    this.coordBuffer = null;
    this.idMapping = [];
    this.version = 0;

    // Frame counter
    this.frame = 0;

    // Abort controller for cancelable initialization
    this._abortController = null;

    this._init();
  }

  async _init() {
    this._abortController = new AbortController();
    const signal = this._abortController.signal;

    if (this._destroyed) return;

    try {
      this.app = new PIXI.Application();
      await this.app.init({
        resizeTo: this.container,
        backgroundAlpha: 0,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
        powerPreference: 'high-performance',
      });
    } catch (e) {
      if (signal.aborted) return;
      throw e;
    }

    if (this._destroyed || signal.aborted) {
      this._destroyApp();
      return;
    }

    this.container.appendChild(this.app.canvas);

    // Viewport container (centered like HTML version)
    this.viewport = new PIXI.Container();
    this.app.stage.addChild(this.viewport);
    this.viewport.x = this.app.screen.width / 2;
    this.viewport.y = this.app.screen.height / 2;

    // Layers: links below nodes below labels
    this.linkGraphics = new PIXI.Graphics();
    this.viewport.addChild(this.linkGraphics);

    this.nodeLayer = new PIXI.Container();
    this.viewport.addChild(this.nodeLayer);

    this.labelLayer = new PIXI.Container();
    this.viewport.addChild(this.labelLayer);

    this._bindEvents();
    this.app.ticker.add(() => this._render());
  }

  _destroyApp() {
    if (this.app) {
      try {
        this.app.destroy(true, { children: true, texture: true });
      } catch (e) {
        // ignore
      }
      this.app = null;
    }
  }

  _bindEvents() {
    const canvas = this.app.canvas;

    // Wheel for zoom
    canvas.addEventListener('wheel', (e) => this._onWheel(e), { passive: false });

    // Pointer events
    canvas.addEventListener('pointerdown', (e) => this._onPointerDown(e));
    canvas.addEventListener('dblclick', (e) => this._onDblClick(e));

    // Global pointer events for drag
    window.addEventListener('pointermove', (e) => this._onPointerMove(e));
    window.addEventListener('pointerup', () => this._onPointerUp());

    // Context menu
    this.container.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  _unbindEvents() {
    window.removeEventListener('pointermove', this._onPointerMove);
    window.removeEventListener('pointerup', this._onPointerUp);
  }

  _getWorldPos(ev) {
    const rect = this.app.view.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    return this.viewport.toLocal(new PIXI.Point(x, y));
  }

  _getBaseNodeScale() {
    return Math.min(1.6, Math.max(0.45, Math.pow(1 / Math.max(0.05, this.scale), 0.35)));
  }

  _onWheel(e) {
    e.preventDefault();
    // Slower zoom: changed from 0.92/1.08 to 0.98/1.02
    const factor = e.deltaY > 0 ? 0.98 : 1.02;
    const rect = this.app.view.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const before = this.viewport.toLocal(new PIXI.Point(mx, my));
    this.scale = Math.max(0.05, Math.min(5, this.scale * factor));
    this.viewport.scale.set(this.scale);

    const after = this.viewport.toLocal(new PIXI.Point(mx, my));
    this.viewport.x += (after.x - before.x) * this.scale;
    this.viewport.y += (after.y - before.y) * this.scale;

    this.onZoom({ k: this.scale, x: this.viewport.x, y: this.viewport.y });
  }

  _onPointerDown(e) {
    const worldPos = this._getWorldPos(e);
    const hitNode = this._hitTest(worldPos.x, worldPos.y);

    if (hitNode) {
      this.draggedId = hitNode.id;
      const sprite = this.nodeSprites[hitNode.id];
      if (sprite) {
        sprite.setNodeTint(COLORS.drag);
        sprite.borderGraphics.visible = true;
      }

      this.onDragStart({ id: hitNode.id, x: worldPos.x, y: worldPos.y });

      // Update node position immediately
      const s = this.nodeSprites[hitNode.id];
      const t = this.labelSprites[hitNode.id];
      if (s) { s.x = worldPos.x; s.y = worldPos.y; }
      if (t) { t.x = worldPos.x; t.y = worldPos.y + (t.yOffset || 0) * this._getBaseNodeScale(); }
    } else if (e.target === this.app.canvas) {
      this.isPanning = true;
      this.lastPan = { x: e.clientX, y: e.clientY };
    }
  }

  _onPointerMove(e) {
    const worldPos = this._getWorldPos(e);

    if (this.draggedId) {
      const s = this.nodeSprites[this.draggedId];
      const t = this.labelSprites[this.draggedId];
      if (s) { s.x = worldPos.x; s.y = worldPos.y; }
      if (t) { t.x = worldPos.x; t.y = worldPos.y + (t.yOffset || 0) * this._getBaseNodeScale(); }

      this.onDragMove(this.draggedId, worldPos.x, worldPos.y);
    } else if (this.isPanning && this.lastPan) {
      this.viewport.x += e.clientX - this.lastPan.x;
      this.viewport.y += e.clientY - this.lastPan.y;
      this.lastPan = { x: e.clientX, y: e.clientY };
      this.onZoom({ k: this.scale, x: this.viewport.x, y: this.viewport.y });
    }

    // Hover detection
    const hitNode = this._hitTest(worldPos.x, worldPos.y);
    if (hitNode && hitNode.id !== this.hoveredId) {
      this.hoveredId = hitNode.id;
      const sprite = this.nodeSprites[hitNode.id];
      if (sprite && hitNode.id !== this.draggedId) {
        sprite.setNodeTint(COLORS.hover);
        sprite.borderGraphics.visible = true;
      }
      this.onNodeHover(hitNode);
    } else if (!hitNode && this.hoveredId) {
      const prevSprite = this.nodeSprites[this.hoveredId];
      if (prevSprite && this.hoveredId !== this.draggedId) {
        prevSprite.setNodeTint(COLORS.node);
        prevSprite.borderGraphics.visible = false;
      }
      this.hoveredId = null;
      this.onNodeHover(null);
    }
  }

  _onPointerUp() {
    if (this.draggedId) {
      const s = this.nodeSprites[this.draggedId];
      if (s) {
        s.setNodeTint(COLORS.node);
        s.borderGraphics.visible = false;
      }

      const node = this.nodes.get(this.draggedId);
      this.onDragEnd({ id: this.draggedId, x: node?.data?.x, y: node?.data?.y });

      this.draggedId = null;
      this.hoveredId = null;
    }
    this.isPanning = false;
    this.lastPan = null;
  }

  _onDblClick(e) {
    const worldPos = this._getWorldPos(e);
    const hitNode = this._hitTest(worldPos.x, worldPos.y);
    if (hitNode) {
      this.onNodeDoubleClick(hitNode.data, e);
    }
  }

  _hitTest(x, y) {
    const baseNodeScale = this._getBaseNodeScale();

    for (const [id, sprite] of Object.entries(this.nodeSprites)) {
      const node = this.nodes.get(id);
      if (!node) continue;

      const degree = node.data.degree || 0;
      const maxDegree = node.data.maxDegree || 1;
      const ratio = degree / maxDegree;
      const baseRadius = 2.5 + ratio * 7 + (ratio > 0.6 ? 2 : 0);
      const radius = Math.max(1, baseRadius * baseNodeScale);
      const hitRadius = radius + 3;

      const dx = sprite.x - x;
      const dy = sprite.y - y;
      if (dx * dx + dy * dy < hitRadius * hitRadius) {
        return { id, data: node.data };
      }
    }
    return null;
  }

  // ── Data Update ─────────────────────────────────────────────────────────────

  updateData(graphData) {
    if (!this.app || !this.nodeLayer || !this.linkGraphics || !this.labelLayer) {
      return;
    }

    const { nodes: newNodes, links: newLinks } = graphData;

    // Calculate degrees
    const degreeCounts = {};
    newNodes.forEach((n) => { degreeCounts[n.id] = 0; });
    newLinks.forEach((l) => {
      const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;
      degreeCounts[sourceId] = (degreeCounts[sourceId] || 0) + 1;
      degreeCounts[targetId] = (degreeCounts[targetId] || 0) + 1;
    });
    const maxDegree = Math.max(1, ...Object.values(degreeCounts));

    // Remove old nodes
    const newNodeIds = new Set(newNodes.map((n) => n.id));
    for (const id of Object.keys(this.nodeSprites)) {
      if (!newNodeIds.has(id)) {
        const s = this.nodeSprites[id];
        const t = this.labelSprites[id];
        if (s) {
          this.nodeLayer.removeChild(s);
          s.destroy();
        }
        if (t) {
          this.labelLayer.removeChild(t);
          t.destroy();
        }
        delete this.nodeSprites[id];
        delete this.labelSprites[id];
        this.nodes.delete(id);
      }
    }

    // Add/update nodes
    newNodes.forEach((n) => {
      const degree = degreeCounts[n.id] || 0;
      const ratio = degree / maxDegree;
      // radius formula: min 6, max 9 (isolated nodes: 6, high degree: 6+3)
      const radius = 6 + ratio * 3;

      if (this.nodeSprites[n.id]) {
        // Update existing node
        const node = this.nodes.get(n.id);
        if (node) {
          node.data = { ...n, degree, maxDegree };
          this.nodeSprites[n.id].baseRadius = radius;
          this.labelSprites[n.id].yOffset = radius + 5;
        }
      } else {
        // Create new node
        this._createNode(n, radius, degree, maxDegree);
      }
    });

    // Build link indices
    const idToIndex = new Map();
    newNodes.forEach((n, i) => idToIndex.set(n.id, i));
    this.linkIndices = newLinks.map((l) => {
      const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;
      return {
        sourceIdx: idToIndex.get(sourceId),
        targetIdx: idToIndex.get(targetId),
        sourceId,
        targetId,
      };
    });

    // Store links data
    this.links.clear();
    newLinks.forEach((l) => {
      const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;
      this.links.set(`${sourceId}_${targetId}`, { data: l });
    });
  }

  _createNode(n, radius, degree, maxDegree) {
    if (!this.nodeLayer || !this.labelLayer) return;

    const container = new PIXI.Container();
    container.eventMode = 'static';
    container.cursor = 'pointer';

    const border = new PIXI.Graphics();
    border.beginFill(this.HOVER_BORDER_COLOR, 1);
    border.drawCircle(0, 0, 50 + this.HOVER_BORDER_WIDTH);
    border.endFill();
    border.visible = false;
    container.addChild(border);

    const fill = new PIXI.Graphics();
    fill.beginFill(0xffffff, 1);
    fill.drawCircle(0, 0, 50);
    fill.endFill();
    container.addChild(fill);

    const scale = radius / 50;
    container.scale.set(scale);
    container.nodeId = n.id;
    container.baseRadius = radius;
    container.borderGraphics = border;
    container.fillGraphics = fill;
    container.setNodeTint = (color) => {
      fill.tint = color;
    };

    this.nodeLayer.addChild(container);
    this.nodeSprites[n.id] = container;

    // Create label with word wrap (max 2 lines)
    const label = new PIXI.Text({
      text: n.label || n.id,
      style: {
        fontFamily: 'var(--font-interface), system-ui, sans-serif',
        fontSize: LABEL_FONT_SIZE,
        fill: COLORS.label,
        resolution: 2,
        dropShadow: true,
        dropShadowColor: 0x000000,
        dropShadowDistance: 0,
        dropShadowBlur: 3,
        wordWrap: true,
        wordWrapWidth: 120,
        breakWords: true,
        lineHeight: LABEL_FONT_SIZE + 2,
      },
    });
    label.anchor.set(0.5, 0);
    label.visible = true;
    label.nodeId = n.id;
    label.yOffset = radius + 5;
    this.labelLayer.addChild(label);
    this.labelSprites[n.id] = label;

    this.nodes.set(n.id, { data: { ...n, degree, maxDegree } });
  }

  // ── Render Loop ─────────────────────────────────────────────────────────────

  _render() {
    this.frame++;
    const baseNodeScale = this._getBaseNodeScale();

    // Update node positions from Worker (if available)
    if (this.coordBuffer && this.idMapping) {
      for (let i = 0; i < this.idMapping.length; i++) {
        const id = this.idMapping[i];
        if (id === this.draggedId) continue;

        const x = this.coordBuffer[i * 2];
        const y = this.coordBuffer[i * 2 + 1];

        const s = this.nodeSprites[id];
        const t = this.labelSprites[id];

        if (s) { s.x = x; s.y = y; }
        if (t) { t.x = x; t.y = y + (t.yOffset || 0) * baseNodeScale; }

        // Update stored position
        const node = this.nodes.get(id);
        if (node) {
          node.data.x = x;
          node.data.y = y;
        }
      }
    }

    const activeId = this.hoveredId || this.draggedId;
    const labelScale = Math.min(2.2, Math.max(0.35, 0.9 / Math.max(0.1, this.scale)));

    // Calculate label alpha based on zoom
    let labelAlpha;
    if (this.scale <= 0.25) labelAlpha = 0;
    else if (this.scale >= 0.6) labelAlpha = 1;
    else labelAlpha = Math.pow((this.scale - 0.25) / 0.35, 6);

    // Update visual states
    if (activeId) {
      const neighborSet = new Set([activeId]);
      for (const link of this.linkIndices) {
        if (link.sourceId === activeId) neighborSet.add(link.targetId);
        if (link.targetId === activeId) neighborSet.add(link.sourceId);
      }

      for (const [id, sprite] of Object.entries(this.nodeSprites)) {
        const isNeighbor = neighborSet.has(id);
        const isActive = id === activeId;

        sprite.alpha = isNeighbor || isActive ? 1 : 0.25;
        sprite.setNodeTint(isActive ? COLORS.hover : COLORS.node);

        const rScale = sprite.baseRadius / 50;
        let targetScale;
        if (isActive) targetScale = rScale * baseNodeScale * 1.35;
        else if (isNeighbor) targetScale = rScale * baseNodeScale * 1.15;
        else targetScale = rScale * baseNodeScale;
        sprite.scale.set(targetScale);

        sprite.borderGraphics.visible = isActive;
      }

      for (const label of Object.values(this.labelSprites)) {
        label.visible = labelAlpha > 0;
        label.scale.set(labelScale);
        label.alpha = labelAlpha;
      }
    } else {
      for (const [id, sprite] of Object.entries(this.nodeSprites)) {
        sprite.alpha = 1;
        sprite.setNodeTint(COLORS.node);
        const rScale = sprite.baseRadius / 50;
        sprite.scale.set(rScale * baseNodeScale);
        sprite.borderGraphics.visible = false;
      }

      for (const label of Object.values(this.labelSprites)) {
        label.visible = labelAlpha > 0;
        label.scale.set(labelScale);
        label.alpha = labelAlpha;
      }
    }

    // Render links (every 2 frames)
    if (this.frame % 2 === 0) {
      this._drawLinks(activeId, labelAlpha);
    }
  }

  _drawLinks(activeId, labelAlpha) {
    if (!this.linkGraphics) return;
    if (!this.linkIndices || this.linkIndices.length === 0) return;

    this.linkGraphics.clear();

    // Calculate line alpha based on zoom
    let baseLineAlpha;
    if (this.scale <= 0.25) baseLineAlpha = 0.65;
    else if (this.scale >= 0.9) baseLineAlpha = 0.38;
    else baseLineAlpha = 0.65 - (this.scale - 0.25) / 0.65 * 0.27;

    const screenLineWidth = this.scale < 0.4 ? 1.3 : 0.8;
    const lw = screenLineWidth / Math.max(0.05, this.scale);

    // Get positions from node sprites (not from coordBuffer)
    const getPos = (id) => {
      const sprite = this.nodeSprites[id];
      if (sprite) return { x: sprite.x, y: sprite.y };
      const node = this.nodes.get(id);
      if (node) return { x: node.data.x || 0, y: node.data.y || 0 };
      return { x: 0, y: 0 };
    };

    if (activeId) {
      // Draw non-active links dimmed
      for (const link of this.linkIndices) {
        if (link.sourceId === activeId || link.targetId === activeId) continue;

        const s = getPos(link.sourceId);
        const t = getPos(link.targetId);

        this.linkGraphics.moveTo(s.x, s.y);
        this.linkGraphics.lineTo(t.x, t.y);
        this.linkGraphics.stroke({ width: lw, color: COLORS.line, alpha: baseLineAlpha * 0.5 });
      }

      // Draw active links highlighted
      for (const link of this.linkIndices) {
        if (link.sourceId !== activeId && link.targetId !== activeId) continue;

        const s = getPos(link.sourceId);
        const t = getPos(link.targetId);

        this.linkGraphics.moveTo(s.x, s.y);
        this.linkGraphics.lineTo(t.x, t.y);
        this.linkGraphics.stroke({ width: lw, color: COLORS.activeLine, alpha: 0.9 });
      }
    } else {
      // Draw all links normally
      for (const link of this.linkIndices) {
        const s = getPos(link.sourceId);
        const t = getPos(link.targetId);

        this.linkGraphics.moveTo(s.x, s.y);
        this.linkGraphics.lineTo(t.x, t.y);
        this.linkGraphics.stroke({ width: lw, color: COLORS.line, alpha: baseLineAlpha });
      }
    }
  }

  // ── Position Updates from Worker ────────────────────────────────────────────

  updatePositionsFromWorker({ buffer, idMapping, version }) {
    if (!buffer || !idMapping) return;
    this.coordBuffer = buffer;
    this.idMapping = idMapping;
    this.version = version;
  }

  // ── Highlight ───────────────────────────────────────────────────────────────

  setHighlightNodes(set) {
    this.highlightNodes = set;
  }

  setHighlightLinks(set) {
    this.highlightLinks = set;
  }

  setSearchResults(ids) {
    this.searchResultIds = ids;
  }

  // ── Camera Controls ─────────────────────────────────────────────────────────

  zoomIn() {
    if (!this.app) return;
    const cx = this.app.canvas.clientWidth / 2;
    const cy = this.app.canvas.clientHeight / 2;
    const before = this.viewport.toLocal(new PIXI.Point(cx, cy));
    this.scale = Math.min(5, this.scale * 1.3);
    this.viewport.scale.set(this.scale);
    const after = this.viewport.toLocal(new PIXI.Point(cx, cy));
    this.viewport.x += (after.x - before.x) * this.scale;
    this.viewport.y += (after.y - before.y) * this.scale;
    this.onZoom({ k: this.scale, x: this.viewport.x, y: this.viewport.y });
  }

  zoomOut() {
    if (!this.app) return;
    const cx = this.app.canvas.clientWidth / 2;
    const cy = this.app.canvas.clientHeight / 2;
    const before = this.viewport.toLocal(new PIXI.Point(cx, cy));
    this.scale = Math.max(0.05, this.scale / 1.3);
    this.viewport.scale.set(this.scale);
    const after = this.viewport.toLocal(new PIXI.Point(cx, cy));
    this.viewport.x += (after.x - before.x) * this.scale;
    this.viewport.y += (after.y - before.y) * this.scale;
    this.onZoom({ k: this.scale, x: this.viewport.x, y: this.viewport.y });
  }

  centerAt(x, y) {
    if (!this.app) return;
    this.viewport.x = this.app.canvas.clientWidth / 2 - x * this.scale;
    this.viewport.y = this.app.canvas.clientHeight / 2 - y * this.scale;
    this.onZoom({ k: this.scale, x: this.viewport.x, y: this.viewport.y });
  }

  fitToScreen() {
    if (!this.app || this.nodes.size === 0) return;

    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;

    for (const [id, node] of this.nodes) {
      const x = node.data.x || 0;
      const y = node.data.y || 0;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }

    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const bw = maxX - minX || 1;
    const bh = maxY - minY || 1;
    const padding = 80;

    const targetScale = Math.max(0.15, Math.min(
      (this.app.canvas.clientWidth - padding * 2) / bw,
      (this.app.canvas.clientHeight - padding * 2) / bh,
      5
    ));

    // Animate to target
    const startScale = this.scale;
    const startX = this.viewport.x;
    const startY = this.viewport.y;
    const targetX = this.app.canvas.clientWidth / 2 - cx * targetScale;
    const targetY = this.app.canvas.clientHeight / 2 - cy * targetScale;

    let progress = 0;
    const animate = () => {
      progress += 0.08;
      if (progress >= 1) {
        this.scale = targetScale;
        this.viewport.scale.set(this.scale);
        this.viewport.x = targetX;
        this.viewport.y = targetY;
        this.onZoom({ k: this.scale, x: this.viewport.x, y: this.viewport.y });
        return;
      }
      const t = 1 - Math.pow(1 - progress, 3);
      this.scale = startScale + (targetScale - startScale) * t;
      this.viewport.scale.set(this.scale);
      this.viewport.x = startX + (targetX - startX) * t;
      this.viewport.y = startY + (targetY - startY) * t;
      this.onZoom({ k: this.scale, x: this.viewport.x, y: this.viewport.y });
      requestAnimationFrame(animate);
    };
    animate();
  }

  // ── Cleanup ─────────────────────────────────────────────────────────────────

  resize() {
    if (!this.app || !this.app.renderer) return;
    this.app.renderer.resize(
      this.container.clientWidth,
      this.container.clientHeight
    );
    // Re-center viewport
    this.viewport.x = this.container.clientWidth / 2;
    this.viewport.y = this.container.clientHeight / 2;
  }

  destroy() {
    this._destroyed = true;

    if (this._abortController) {
      this._abortController.abort();
      this._abortController = null;
    }

    this._unbindEvents();
    this._destroyApp();

    this.nodes.clear();
    this.links.clear();
    this.nodeSprites = {};
    this.labelSprites = {};
  }
}
