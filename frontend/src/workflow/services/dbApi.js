/**
 * Database API Service
 * WebSocket API wrapper for user-defined table operations
 */

import { useMemo } from 'react';
import { useWebSocket } from '../../contexts/WebSocketContext';

const MessageTypes = {
  TABLE_LIST: 'db_table_list',
  TABLE_CREATE: 'db_table_create',
  TABLE_GET: 'db_table_get',
  TABLE_UPDATE: 'db_table_update',
  TABLE_DELETE: 'db_table_delete',
  RECORD_LIST: 'db_record_list',
  RECORD_CREATE: 'db_record_create',
  RECORD_UPDATE: 'db_record_update',
  RECORD_DELETE: 'db_record_delete',
  RECORD_SEARCH: 'db_record_search',
};

export const createDBAPI = (sendMessage) => {
  const api = {
    // Table Management
    getTableList: async () => {
      const response = await sendMessage(MessageTypes.TABLE_LIST, {});
      return response.data?.tables || [];
    },

    createTable: async (name, description, fields) => {
      const response = await sendMessage(MessageTypes.TABLE_CREATE, {
        name,
        description,
        fields,
      });
      return response.data;
    },

    getTable: async (name) => {
      const response = await sendMessage(MessageTypes.TABLE_GET, { name });
      return response.data;
    },

    updateTable: async (id, updates) => {
      const response = await sendMessage(MessageTypes.TABLE_UPDATE, {
        id,
        ...updates,
      });
      return response.data;
    },

    deleteTable: async (name) => {
      const response = await sendMessage(MessageTypes.TABLE_DELETE, { name });
      return response.data;
    },

    // Record CRUD
    getRecords: async (tableName, page = 1, pageSize = 20, sortField = 'created_at', sortOrder = 'desc') => {
      const response = await sendMessage(MessageTypes.RECORD_LIST, {
        table_name: tableName,
        page,
        page_size: pageSize,
        sort_field: sortField,
        sort_order: sortOrder,
      });
      return response.data || { total: 0, page: 1, page_size: pageSize, records: [] };
    },

    createRecord: async (tableName, recordData) => {
      const response = await sendMessage(MessageTypes.RECORD_CREATE, {
        table_name: tableName,
        record_data: recordData,
      });
      return response.data;
    },

    updateRecord: async (id, recordData) => {
      const response = await sendMessage(MessageTypes.RECORD_UPDATE, {
        id,
        record_data: recordData,
      });
      return response.data;
    },

    deleteRecord: async (id) => {
      const response = await sendMessage(MessageTypes.RECORD_DELETE, { id });
      return response.data;
    },

    searchRecords: async (tableName, keyword, page = 1, pageSize = 20) => {
      const response = await sendMessage(MessageTypes.RECORD_SEARCH, {
        table_name: tableName,
        keyword,
        page,
        page_size: pageSize,
      });
      return response.data || { total: 0, page: 1, page_size: pageSize, records: [] };
    },
  };

  return api;
};

export const useDBAPI = () => {
  const { sendMessage } = useWebSocket();
  return useMemo(() => createDBAPI(sendMessage), [sendMessage]);
};

export default createDBAPI;
