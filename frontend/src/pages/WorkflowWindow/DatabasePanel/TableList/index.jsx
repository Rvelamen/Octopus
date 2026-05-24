import React from 'react';
import { Table2, Trash2, Edit3 } from 'lucide-react';
import { Popconfirm, Tooltip } from 'antd';

export default function TableList({ tables, selectedTable, onSelect, onEdit, onDelete }) {
  if (tables.length === 0) {
    return (
      <div style={{ padding: 16, color: '#9ca3af', fontSize: 13, textAlign: 'center' }}>
        暂无数据表
      </div>
    );
  }

  return (
    <div className="database-table-list">
      {tables.map((table) => (
        <div
          key={table.id}
          className={`database-table-item ${selectedTable?.id === table.id ? 'active' : ''}`}
          onClick={() => onSelect(table)}
        >
          <Table2 size={16} className="table-icon" />
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {table.name}
          </span>
          <div style={{ display: 'flex', gap: 4, opacity: 0, transition: 'opacity 0.15s' }}
            className="table-actions"
            onClick={(e) => e.stopPropagation()}
          >
            <Tooltip title="编辑">
              <span
                style={{ cursor: 'pointer', padding: 2, borderRadius: 4 }}
                onClick={() => onEdit(table)}
              >
                <Edit3 size={12} />
              </span>
            </Tooltip>
            <Popconfirm
              title="删除表"
              description={`确定删除 "${table.name}"？数据不可恢复。`}
              onConfirm={() => onDelete(table)}
              okText="删除"
              cancelText="取消"
              okType="danger"
            >
              <Tooltip title="删除">
                <span style={{ cursor: 'pointer', padding: 2, borderRadius: 4, color: '#ef4444' }}>
                  <Trash2 size={12} />
                </span>
              </Tooltip>
            </Popconfirm>
          </div>
        </div>
      ))}
      <style>{`
        .database-table-item:hover .table-actions {
          opacity: 1 !important;
        }
      `}</style>
    </div>
  );
}
