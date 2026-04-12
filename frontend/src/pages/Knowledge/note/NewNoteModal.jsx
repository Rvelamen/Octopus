import React from 'react';
import { Modal, Input } from 'antd';

export default function NewNoteModal({ visible, title, onTitleChange, onCreate, onCancel }) {
  return (
    <Modal
      title="New Note"
      open={visible}
      onOk={onCreate}
      onCancel={onCancel}
      okText="Create"
    >
      <Input
        placeholder="Note title"
        value={title}
        onChange={(e) => onTitleChange(e.target.value)}
        onPressEnter={onCreate}
        autoFocus
      />
      <p style={{ marginTop: 12, fontSize: 12, color: 'var(--text-2)' }}>
        A markdown note will be created in knowledge/notes/.
      </p>
    </Modal>
  );
}
