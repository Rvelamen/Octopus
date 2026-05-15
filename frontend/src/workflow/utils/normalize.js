/**
 * Workflow data normalization utilities.
 *
 * Ensures consistent camelCase field naming between frontend and backend.
 * Frontend stores node data; backend expects snake_case in DB but camelCase
 * when serialized over WebSocket.
 */

/**
 * Convert a snake_case string to camelCase.
 * @param {string} str
 * @returns {string}
 */
export const snakeToCamel = (str) =>
  str.replace(/_([a-z])/g, (_, c) => c.toUpperCase());

/**
 * Convert a camelCase string to snake_case.
 * @param {string} str
 * @returns {string}
 */
export const camelToSnake = (str) =>
  str.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);

/**
 * Recursively convert all keys in an object from snake_case to camelCase.
 * @param {any} obj
 * @returns {any}
 */
export const keysToCamel = (obj) => {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(keysToCamel);
  if (typeof obj !== 'object') return obj;
  return Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [snakeToCamel(k), keysToCamel(v)])
  );
};

/**
 * Recursively convert all keys in an object from camelCase to snake_case.
 * @param {any} obj
 * @returns {any}
 */
export const keysToSnake = (obj) => {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(keysToSnake);
  if (typeof obj !== 'object') return obj;
  return Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [camelToSnake(k), keysToSnake(v)])
  );
};

/**
 * Normalize a node object from frontend format to backend API format.
 * @param {Object} node - Frontend node
 * @returns {Object} Backend-formatted node
 */
export const normalizeNodeForBackend = (node) => ({
  id: node.id,
  type: node.type,
  label: node.data?.name || node.data?.label || node.type,
  position: {
    x: node.position?.x ?? 0,
    y: node.position?.y ?? 0,
  },
  width: node.width || node.data?.width || 240,
  height: node.height || node.data?.height || 120,
  config: {
    ...(node.data?.config || {}),
    inputs: node.data?.inputs || [],
    outputs: node.data?.outputs || [],
    flowNodeType: node.data?.flowNodeType || node.type,
    name: node.data?.name,
    intro: node.data?.intro,
    avatar: node.data?.avatar,
    colorSchema: node.data?.colorSchema,
    providerId: node.data?.providerId,
    modelId: node.data?.modelId,
    showTargetHandle: node.data?.showTargetHandle,
    showSourceHandle: node.data?.showSourceHandle,
    forbidDelete: node.data?.forbidDelete,
  },
  timeout_seconds: node.data?.timeoutSeconds ?? node.data?.timeout_seconds ?? 60,
  max_retries: node.data?.maxRetries ?? node.data?.max_retries ?? 0,
});

/**
 * Normalize an edge object from frontend format to backend API format.
 * @param {Object} edge - Frontend edge
 * @returns {Object} Backend-formatted edge
 */
export const normalizeEdgeForBackend = (edge) => ({
  id: edge.id,
  source: edge.source,
  target: edge.target,
  sourceHandle: edge.sourceHandle,
  targetHandle: edge.targetHandle,
  label: edge.label,
  condition: edge.condition,
});

/**
 * Parse a backend node into frontend React Flow node format.
 * @param {Object} bNode - Backend node
 * @returns {Object} Frontend node
 */
export const parseNodeFromBackend = (bNode) => ({
  id: bNode.id,
  type: bNode.type,
  position: { x: bNode.position?.x ?? bNode.positionX ?? 0, y: bNode.position?.y ?? bNode.positionY ?? 0 },
  data: {
    flowNodeType: bNode.type,
    label: bNode.label,
    ...(bNode.config || {}),
    name: bNode.config?.name || bNode.label || bNode.type,
    width: bNode.width,
    height: bNode.height,
    timeoutSeconds: bNode.timeout_seconds ?? bNode.timeoutSeconds,
    maxRetries: bNode.max_retries ?? bNode.maxRetries,
  },
});

/**
 * Parse a backend edge into frontend React Flow edge format.
 * @param {Object} bEdge - Backend edge
 * @returns {Object} Frontend edge
 */
export const parseEdgeFromBackend = (bEdge) => ({
  id: bEdge.id,
  source: bEdge.source,
  target: bEdge.target,
  sourceHandle: bEdge.sourceHandle ?? bEdge.source_handle,
  targetHandle: bEdge.targetHandle ?? bEdge.target_handle,
  label: bEdge.label,
  condition: bEdge.condition,
});
