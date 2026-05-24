import React, { useState } from 'react';
import { Table, Button, Space, Pagination, Input, Modal, Form } from 'antd';
import { Plus, RefreshCw, Search } from 'lucide-react';
import RecordFormModal from './RecordFormModal';

const TYPE_MAP = {
  string: '文本',
  integer: '整数',
  decimal: '小数',
  boolean: '布尔',
  datetime: '日期时间',
  json: 'JSON',
};

export default function DataTable({
  table,
  records,
  total,
  page,
  pageSize,
  loading,
  onPageChange,
  onCreate,
  onUpdate,
  onDelete,
  onRefresh,
}) {
  const [searchKeyword, setSearchKeyword] = useState('');
  const [recordModalOpen, setRecordModalOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState(null);

  const fields = table.fields || [];

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: '__db_id',
      width: 60,
    },
    ...fields.map((field) => ({
      title: (
        <span>
          {field.name}
          <span style={{ marginLeft: 4, fontSize: 11, color: '#9ca3af' }}>
            ({TYPE_MAP[field.type] || field.type})
            {field.required && <span style={{ color: '#ef4444' }}>*</span>}
            {field.autoIncrement && <span style={{ color: '#f59e0b' }}>↑</span>}
          </span>
        </span>
      ),
      dataIndex: ['record_data', field.name],
      key: `field_${field.name}`,
      render: (value) => {
        if (value === null || value === undefined) return <span style={{ color: '#d1d5db' }}>NULL</span>;
        if (field.type === 'boolean') return value ? '是' : '否';
        if (field.type === 'json') {
          const text = typeof value === 'string' ? value : JSON.stringify(value);
          return (
            <span
              style={{
                fontFamily: 'monospace',
                fontSize: 12,
                color: '#6b7280',
                maxWidth: 200,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: 'inline-block',
                whiteSpace: 'nowrap',
              }}
              title={text}
            >
              {text}
            </span>
          );
        }
        if (field.autoIncrement) {
          return <span style={{ color: '#f59e0b', fontWeight: 500 }}>{String(value)}</span>;
        }
        return String(value);
      },
    })),
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            size="small"
            type="link"
            onClick={() => {
              setEditingRecord(record);
              setRecordModalOpen(true);
            }}
          >
            编辑
          </Button>
          <Button
            size="small"
            type="link"
            danger
            onClick={() => onDelete(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  const handleSearch = () => {
    // TODO: implement search via db_record_search
    onRefresh();
  };

  return (
    <>
      <div style={{ padding: '12px 20px', background: '#fff', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', gap: 12 }}>
        <Input
          placeholder="搜索数据..."
          prefix={<Search size={14} />}
          value={searchKeyword}
          onChange={(e) => setSearchKeyword(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 240 }}
          size="small"
        />
        <Button
          size="small"
          icon={<RefreshCw size={14} />}
          onClick={onRefresh}
          loading={loading}
        >
          刷新
        </Button>
        <div style={{ flex: 1 }} />
        <Button
          type="primary"
          size="small"
          icon={<Plus size={14} />}
          onClick={() => {
            setEditingRecord(null);
            setRecordModalOpen(true);
          }}
        >
          新增记录
        </Button>
      </div>

      <div className="database-table-wrapper">
        <Table
          columns={columns}
          dataSource={records}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
        />

        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            onChange={onPageChange}
            size="small"
            showTotal={(t) => `共 ${t} 条`}
          />
        </div>
      </div>

      <RecordFormModal
        open={recordModalOpen}
        onClose={() => {
          setRecordModalOpen(false);
          setEditingRecord(null);
        }}
        onSubmit={(data) => {
          if (editingRecord) {
            onUpdate(editingRecord.id, data);
          } else {
            onCreate(data);
          }
          setRecordModalOpen(false);
          setEditingRecord(null);
        }}
        fields={fields}
        initialValues={editingRecord?.record_data}
      />
    </>
  );
}
