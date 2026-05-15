/**
 * Workflow API Service
 * WebSocket API wrapper for workflow operations
 */

import { useMemo } from 'react';
import { useWebSocket } from '../../contexts/WebSocketContext';

// Message type constants matching backend handlers
const MessageTypes = {
  // Workflow CRUD
  LIST: 'workflow_list',
  GET: 'workflow_get',
  SAVE: 'workflow_save',
  UPDATE: 'workflow_update',
  DELETE: 'workflow_delete',

  // Version Management
  VERSION_CREATE: 'workflow_version_create',
  VERSION_LIST: 'workflow_version_list',
  PUBLISH: 'workflow_publish',

  // Definition Management
  DEFINITION_GET: 'workflow_definition_get',
  DEFINITION_SAVE: 'workflow_definition_save',

  // Execution Control
  RUN: 'workflow_run',
  RUN_STATUS: 'workflow_run_status',
  RUN_LIST: 'workflow_run_list',
  RUN_DETAIL: 'workflow_run_detail',
  RUN_CANCEL: 'workflow_run_cancel',
  RUN_DELETE: 'workflow_run_delete',
  RUN_LIST_DELETE: 'workflow_run_list_delete',

  // Import/Export
  EXPORT: 'workflow_export',
  IMPORT: 'workflow_import',

  // Node Registry
  GET_NODE_REGISTRY: 'workflow_get_node_registry',

  // Model Management
  GET_PROVIDERS: 'model_get_providers',
  GET_MODELS: 'model_get_models',
};

/**
 * Create workflow API instance
 * @param {Function} sendMessage - WebSocket sendMessage function
 * @param {Function} subscribe - WebSocket subscribe function
 */
export const createWorkflowAPI = (sendMessage, subscribe) => {
  const api = {
    // ========== Workflow CRUD ==========

    /**
     * Get workflow list
     * @param {Object} params - Filter parameters
     * @param {string} params.category - Workflow category
     * @param {string} params.status - Workflow status
     */
    getWorkflowList: async (params = {}) => {
      const response = await sendMessage(MessageTypes.LIST, params);
      return response.data?.workflows || [];
    },

    /**
     * Get workflow details
     * @param {string} workflowId - Workflow ID
     */
    getWorkflow: async (workflowId) => {
      const response = await sendMessage(MessageTypes.GET, { workflow_id: workflowId });
      return response.data;
    },

    /**
     * Save workflow (create or update)
     * @param {Object} data - Workflow data
     * @param {string} data.workflow_id - Workflow ID (for update)
     * @param {string} data.name - Workflow name
     * @param {string} data.description - Workflow description
     * @param {string} data.category - Workflow category
     */
    saveWorkflow: async (data) => {
      const response = await sendMessage(MessageTypes.SAVE, data);
      return response.data;
    },

    /**
     * Update workflow
     * @param {string} workflowId - Workflow ID
     * @param {Object} updates - Fields to update
     */
    updateWorkflow: async (workflowId, updates) => {
      const response = await sendMessage(MessageTypes.UPDATE, {
        workflow_id: workflowId,
        ...updates,
      });
      return response.data;
    },

    /**
     * Delete workflow
     * @param {string} workflowId - Workflow ID
     */
    deleteWorkflow: async (workflowId) => {
      const response = await sendMessage(MessageTypes.DELETE, { workflow_id: workflowId });
      return response.data;
    },

    // ========== Version Management ==========

    /**
     * Get version list
     * @param {string} workflowId - Workflow ID
     */
    getVersionList: async (workflowId) => {
      const response = await sendMessage(MessageTypes.VERSION_LIST, { workflow_id: workflowId });
      return response.data?.versions || [];
    },

    /**
     * Create new version
     * @param {string} workflowId - Workflow ID
     * @param {number} version - Version number
     * @param {string} name - Version name
     * @param {string} description - Version description
     */
    createVersion: async (workflowId, version, name, description = '') => {
      const response = await sendMessage(MessageTypes.VERSION_CREATE, {
        workflow_id: workflowId,
        version,
        name,
        description,
      });
      return response.data;
    },

    /**
     * Publish version
     * @param {string} versionId - Version ID
     */
    publishVersion: async (versionId) => {
      const response = await sendMessage(MessageTypes.PUBLISH, { version_id: versionId });
      return response.data;
    },

    // ========== Definition Management ==========

    /**
     * Get workflow definition
     * @param {string} versionId - Version ID
     */
    getDefinition: async (versionId) => {
      const response = await sendMessage(MessageTypes.DEFINITION_GET, { version_id: versionId });
      return response.data;
    },

    /**
     * Save workflow definition
     * @param {string} versionId - Version ID
     * @param {Array} nodes - Node definitions
     * @param {Array} edges - Edge definitions
     * @param {Array} variables - Variable definitions
     */
    saveDefinition: async (versionId, nodes, edges, variables = []) => {
      const response = await sendMessage(MessageTypes.DEFINITION_SAVE, {
        version_id: versionId,
        nodes,
        edges,
        variables,
      });
      return response.data;
    },

    // ========== Execution Control ==========

    /**
     * Run workflow
     * @param {string} workflowId - Workflow ID
     * @param {Object} options - Run options
     * @param {string} options.version_id - Version ID (optional)
     * @param {Object} options.input_variables - Input variables
     */
    runWorkflow: async (workflowId, options = {}) => {
      const response = await sendMessage(MessageTypes.RUN, {
        workflow_id: workflowId,
        version_id: options.version_id,
        input_variables: options.input_variables || {},
        test_mode: options.test_mode || false,
      }, 120000);
      return response.data;
    },

    /**
     * Get run status
     * @param {string} runId - Run ID
     */
    getRunStatus: async (runId) => {
      const response = await sendMessage(MessageTypes.RUN_STATUS, { run_id: runId });
      return response.data;
    },

    /**
     * Get run list
     * @param {Object} params - Filter parameters
     * @param {string} params.workflow_id - Workflow ID
     * @param {string} params.status - Run status
     * @param {number} params.limit - Limit
     * @param {number} params.offset - Offset
     */
    getRunList: async (params = {}) => {
      const response = await sendMessage(MessageTypes.RUN_LIST, params);
      return response.data?.runs || [];
    },

    /**
     * Get run detail
     * @param {string} runId - Run ID
     */
    getRunDetail: async (runId) => {
      const response = await sendMessage(MessageTypes.RUN_DETAIL, { run_id: runId });
      return response.data;
    },

    /**
     * Cancel run
     * @param {string} runId - Run ID
     */
    cancelRun: async (runId) => {
      const response = await sendMessage(MessageTypes.RUN_CANCEL, { run_id: runId });
      return response.data;
    },

    /**
     * Delete a single run
     * @param {string} runId - Run ID
     */
    deleteRun: async (runId) => {
      const response = await sendMessage(MessageTypes.RUN_DELETE, { run_id: runId });
      return response.data;
    },

    /**
     * Delete all runs for a workflow
     * @param {string} workflowId - Workflow ID
     */
    deleteWorkflowRuns: async (workflowId) => {
      const response = await sendMessage(MessageTypes.RUN_LIST_DELETE, { workflow_id: workflowId });
      return response.data;
    },

    // ========== Import/Export ==========

    /**
     * Export workflow
     * @param {string} workflowId - Workflow ID
     */
    exportWorkflow: async (workflowId) => {
      const response = await sendMessage(MessageTypes.EXPORT, { workflow_id: workflowId });
      return response.data;
    },

    /**
     * Import workflow
     * @param {Object} data - Import data
     */
    importWorkflow: async (data) => {
      const response = await sendMessage(MessageTypes.IMPORT, { data });
      return response.data;
    },

    // ========== Node Registry ==========

    /**
     * Get node registry
     */
    getNodeRegistry: async () => {
      const response = await sendMessage(MessageTypes.GET_NODE_REGISTRY);
      return response.data;
    },

    // ========== Model Management ==========

    /**
     * Get available providers
     */
    getProviders: async () => {
      const response = await sendMessage(MessageTypes.GET_PROVIDERS);
      return response.data?.providers || [];
    },

    /**
     * Get available models
     * @param {string} providerId - Provider ID (optional)
     */
    getModels: async (providerId = null) => {
      const params = providerId ? { provider_id: providerId } : {};
      const response = await sendMessage(MessageTypes.GET_MODELS, params);
      return response.data?.models || [];
    },

    // ========== Real-time Updates ==========

    /**
     * Subscribe to run status updates
     * @param {string} runId - Run ID
     * @param {Function} callback - Status update callback
     * @returns {Function} Unsubscribe function
     */
    subscribeRunStatus: (runId, callback) => {
      const unsubscribe = subscribe('workflow_run_status_update', (data) => {
        if (data.run_id === runId) {
          callback(data);
        }
      });
      return unsubscribe;
    },

    /**
     * Subscribe to node execution updates
     * @param {string} runId - Run ID
     * @param {Function} callback - Node update callback
     * @returns {Function} Unsubscribe function
     */
    subscribeNodeUpdates: (runId, callback) => {
      const unsubscribe = subscribe('workflow_node_update', (data) => {
        if (data.run_id === runId) {
          callback(data);
        }
      });
      return unsubscribe;
    },
  };

  return api;
};

// Hook for using workflow API
export const useWorkflowAPI = () => {
  const { sendMessage, subscribe } = useWebSocket();
  return useMemo(() => createWorkflowAPI(sendMessage, subscribe), [sendMessage, subscribe]);
};

export default createWorkflowAPI;
