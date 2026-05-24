import React, { useState, useEffect } from 'react';
import { FolderPlus } from 'lucide-react';
import { Modal, Input, TreeSelect, ColorPicker, Button, Form } from 'antd';

const PRESET_COLORS = [
  '#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#a0d911', '#2f54eb',
];

const LibraryCollectionModal = ({ open, onClose, onCreate, collections }) => {
  const [name, setName] = useState('');
  const [parentId, setParentId] = useState(null);
  const [color, setColor] = useState('#1890ff');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (open) {
      setName('');
      setParentId(null);
      setColor('#1890ff');
    }
  }, [open]);

  const treeData = collections
    .filter((c) => c.id !== 2) // Exclude Uncategorized
    .map((c) => ({
      value: c.id,
      title: c.name,
      children: c.children?.map((child) => ({
        value: child.id,
        title: child.name,
      })),
    }));

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await onCreate(name.trim(), parentId, color);
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setCreating(false);
    }
  };

  return (
    <Modal
      title={
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FolderPlus size={18} style={{ color: 'var(--accent)' }} />
          New Collection
        </span>
      }
      open={open}
      onCancel={onClose}
      onOk={handleCreate}
      okButtonProps={{ loading: creating, disabled: !name.trim() }}
      width={400}
    >
      <Form layout="vertical" style={{ marginTop: 12 }}>
        <Form.Item label="Name" required>
          <Input
            placeholder="e.g. Transformer Research"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onPressEnter={handleCreate}
            autoFocus
          />
        </Form.Item>

        <Form.Item label="Parent Collection">
          <TreeSelect
            style={{ width: '100%' }}
            treeData={treeData}
            placeholder="Root (no parent)"
            allowClear
            value={parentId}
            onChange={setParentId}
          />
        </Form.Item>

        <Form.Item label="Color">
          <ColorPicker
            value={color}
            onChange={(c) => setColor(c.toHexString())}
            presets={[
              {
                label: 'Presets',
                colors: PRESET_COLORS,
              },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default LibraryCollectionModal;
