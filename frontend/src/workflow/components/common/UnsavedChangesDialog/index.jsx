/**
 * 未保存更改提示对话框
 * 提供三个选项：保存并返回 / 不保存返回 / 取消
 */
import React from 'react';
import { AlertTriangle, Save, ArrowLeft, X } from 'lucide-react';

const UnsavedChangesDialog = ({ isOpen, onSaveAndReturn, onDiscardAndReturn, onCancel }) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.4)',
      }}
      onClick={onCancel}
    >
      <div
        style={{
          background: 'white',
          borderRadius: '12px',
          width: '420px',
          boxShadow: '0 20px 25px -5px rgba(0,0,0,0.15)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: '24px', textAlign: 'center' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: '#fffbeb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 12px',
            }}
          >
            <AlertTriangle size={24} color="#f59e0b" />
          </div>
          <div style={{ fontSize: '16px', fontWeight: 600, color: '#1f2937', marginBottom: '8px' }}>
            有未保存的更改
          </div>
          <div style={{ fontSize: '14px', color: '#6b7280', lineHeight: 1.5 }}>
            当前工作流有未保存的修改，离开前是否需要保存？
          </div>
        </div>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            padding: '0 24px 20px',
          }}
        >
          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '10px',
              borderRadius: '8px',
              border: 'none',
              background: '#4f46e5',
              color: 'white',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
            }}
            onClick={onSaveAndReturn}
          >
            <Save size={16} />
            保存并返回
          </button>
          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '10px',
              borderRadius: '8px',
              border: '1px solid #e5e7eb',
              background: 'white',
              color: '#374151',
              fontSize: '14px',
              cursor: 'pointer',
            }}
            onClick={onDiscardAndReturn}
          >
            <ArrowLeft size={16} />
            不保存，直接返回
          </button>
          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '10px',
              borderRadius: '8px',
              border: 'none',
              background: 'transparent',
              color: '#6b7280',
              fontSize: '14px',
              cursor: 'pointer',
            }}
            onClick={onCancel}
          >
            <X size={16} />
            取消
          </button>
        </div>
      </div>
    </div>
  );
};

export default UnsavedChangesDialog;
