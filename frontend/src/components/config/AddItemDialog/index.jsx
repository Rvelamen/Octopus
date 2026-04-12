import React, { useState } from 'react';

/**
 * AddItemDialog 组件 - 添加新配置项对话框
 */
function AddItemDialog({ isOpen, onClose, onConfirm, title, placeholder }) {
  const [value, setValue] = useState('');

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (value.trim()) {
      onConfirm(value.trim());
      setValue('');
      onClose();
    }
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <span>{title}</span>
        </div>
        <div className="dialog-body">
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            className="pixel-input form-input"
            autoFocus
            onKeyDown={(e) => e.key === 'Enter' && handleConfirm()}
          />
        </div>
        <div className="dialog-footer">
          <button className="pixel-button small" onClick={onClose}>
            [取消]
          </button>
          <button className="pixel-button small save-btn" onClick={handleConfirm}>
            [确认]
          </button>
        </div>
      </div>
    </div>
  );
}

export default AddItemDialog;
