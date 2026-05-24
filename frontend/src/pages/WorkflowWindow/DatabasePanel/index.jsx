import React, { useState, useEffect, useCallback } from 'react';
import { Button, message, Modal } from 'antd';
import { Plus, Database, Trash2, Edit3 } from 'lucide-react';
import { useDBAPI } from '../../../workflow/services/dbApi';
import TableList from './TableList';
import DataTable from './DataTable';
import TableDesignerModal from './TableDesignerModal';
import './DatabasePanel.css';

export default function DatabasePanel() {
  const api = useDBAPI();
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [records, setRecords] = useState([]);
  const [recordTotal, setRecordTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [designerOpen, setDesignerOpen] = useState(false);
  const [editingTable, setEditingTable] = useState(null);

  const loadTables = useCallback(async () => {
    try {
      const list = await api.getTableList();
      setTables(list);
      if (list.length > 0 && !selectedTable) {
        setSelectedTable(list[0]);
      }
    } catch (err) {
      message.error('加载表列表失败: ' + (err.message || '未知错误'));
    }
  }, [api, selectedTable]);

  const loadRecords = useCallback(async () => {
    if (!selectedTable) return;
    setLoading(true);
    try {
      const result = await api.getRecords(selectedTable.name, page, pageSize);
      setRecords(result.records || []);
      setRecordTotal(result.total || 0);
    } catch (err) {
      message.error('加载数据失败: ' + (err.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  }, [api, selectedTable, page, pageSize]);

  useEffect(() => {
    loadTables();
  }, [loadTables]);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  const handleTableSelect = (table) => {
    setSelectedTable(table);
    setPage(1);
  };

  const handleCreateTable = async (values) => {
    try {
      await api.createTable(values.name, values.description, values.fields);
      message.success('表创建成功');
      setDesignerOpen(false);
      setEditingTable(null);
      await loadTables();
    } catch (err) {
      message.error('创建失败: ' + (err.message || '未知错误'));
    }
  };

  const handleUpdateTable = async (values) => {
    try {
      await api.updateTable(editingTable.id, {
        name: values.name,
        description: values.description,
        fields: values.fields,
      });
      message.success('表更新成功');
      setDesignerOpen(false);
      setEditingTable(null);
      await loadTables();
      if (selectedTable && selectedTable.id === editingTable.id) {
        setSelectedTable(null);
      }
    } catch (err) {
      message.error('更新失败: ' + (err.message || '未知错误'));
    }
  };

  const handleDeleteTable = (table) => {
    Modal.confirm({
      title: '删除确认',
      content: `确定要删除表 "${table.name}" 吗？表内所有数据将被清空且无法恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.deleteTable(table.name);
          message.success('表已删除');
          if (selectedTable && selectedTable.id === table.id) {
            setSelectedTable(null);
          }
          await loadTables();
        } catch (err) {
          message.error('删除失败: ' + (err.message || '未知错误'));
        }
      },
    });
  };

  const handleCreateRecord = async (recordData) => {
    try {
      await api.createRecord(selectedTable.name, recordData);
      message.success('记录已添加');
      await loadRecords();
    } catch (err) {
      message.error('添加失败: ' + (err.message || '未知错误'));
    }
  };

  const handleUpdateRecord = async (id, recordData) => {
    try {
      await api.updateRecord(id, recordData);
      message.success('记录已更新');
      await loadRecords();
    } catch (err) {
      message.error('更新失败: ' + (err.message || '未知错误'));
    }
  };

  const handleDeleteRecord = async (id) => {
    Modal.confirm({
      title: '删除确认',
      content: '确定要删除这条记录吗？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.deleteRecord(id);
          message.success('记录已删除');
          await loadRecords();
        } catch (err) {
          message.error('删除失败: ' + (err.message || '未知错误'));
        }
      },
    });
  };

  return (
    <div className="database-panel">
      <div className="database-sidebar">
        <div className="database-sidebar-header">
          <h3>数据表</h3>
          <Button
            type="primary"
            size="small"
            icon={<Plus size={14} />}
            onClick={() => {
              setEditingTable(null);
              setDesignerOpen(true);
            }}
          >
            新建
          </Button>
        </div>
        <TableList
          tables={tables}
          selectedTable={selectedTable}
          onSelect={handleTableSelect}
          onEdit={(table) => {
            setEditingTable(table);
            setDesignerOpen(true);
          }}
          onDelete={handleDeleteTable}
        />
      </div>

      <div className="database-main">
        {selectedTable ? (
          <>
            <div className="database-main-header">
              <h2>{selectedTable.name}</h2>
              <div className="database-main-actions">
                <Button
                  size="small"
                  icon={<Edit3 size={14} />}
                  onClick={() => {
                    setEditingTable(selectedTable);
                    setDesignerOpen(true);
                  }}
                >
                  编辑结构
                </Button>
                <Button
                  size="small"
                  danger
                  icon={<Trash2 size={14} />}
                  onClick={() => handleDeleteTable(selectedTable)}
                >
                  删除表
                </Button>
              </div>
            </div>
            <DataTable
              table={selectedTable}
              records={records}
              total={recordTotal}
              page={page}
              pageSize={pageSize}
              loading={loading}
              onPageChange={setPage}
              onCreate={handleCreateRecord}
              onUpdate={handleUpdateRecord}
              onDelete={handleDeleteRecord}
              onRefresh={loadRecords}
            />
          </>
        ) : (
          <div className="database-empty">
            <Database size={48} strokeWidth={1.5} />
            <h3>选择一个数据表开始</h3>
            <p>在左侧创建新表或选择已有表</p>
          </div>
        )}
      </div>

      <TableDesignerModal
        open={designerOpen}
        onClose={() => {
          setDesignerOpen(false);
          setEditingTable(null);
        }}
        onSubmit={editingTable ? handleUpdateTable : handleCreateTable}
        initialValues={editingTable}
      />
    </div>
  );
}
