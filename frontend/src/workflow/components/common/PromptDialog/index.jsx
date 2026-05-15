import React, { useState, useEffect, useRef } from 'react';
import { X, Type, Loader2 } from 'lucide-react';

const PromptDialog = ({
  isOpen,
  onClose,
  onConfirm,
  title = '输入',
  message = '',
  label = '',
  defaultValue = '',
  placeholder = '',
  confirmText = '确定',
  cancelText = '取消',
  loading = false,
}) => {
  const [value, setValue] = useState(defaultValue);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      setValue(defaultValue);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, defaultValue]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.4)',
      }}
      onClick={loading ? undefined : onClose}
    >
      <div
        style={{
          background: 'white',
          borderRadius: '12px',
          width: '400px',
          boxShadow: '0 20px 25px -5px rgba(0,0,0,0.15)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid #f3f4f6',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Type size={18} color="#4b5563" />
            <span style={{ fontSize: '16px', fontWeight: 600 }}>{title}</span>
          </div>
          <button
            style={{ padding: '4px', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer' }}
            onClick={onClose}
            disabled={loading}
          >
            <X size={18} />
          </button>
        </div>
        <div style={{ padding: '20px' }}>
          {message && (
            <div style={{ fontSize: '13px', color: '#6b7280', marginBottom: '12px' }}>{message}</div>
          )}
          {label && (
            <div style={{ fontSize: '13px', color: '#374151', marginBottom: '6px', fontWeight: 500 }}>{label}</div>
          )}
          <input
            ref={inputRef}
            value={value || ''}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && value?.trim() && !loading) {
                onConfirm(value.trim());
              }
              if (e.key === 'Escape' && !loading) {
                onClose();
              }
            }}
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              fontSize: '14px',
              outline: 'none',
            }}
          />
        </div>
        <div
          style={{
            display: 'flex',
            gap: '8px',
            padding: '12px 20px',
            borderTop: '1px solid #f3f4f6',
          }}
        >
          <button
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '6px',
              border: '1px solid #e5e7eb',
              background: 'white',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              color: '#6b7280',
              opacity: loading ? 0.5 : 1,
            }}
            onClick={onClose}
            disabled={loading}
          >
            {cancelText}
          </button>
          <button
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '6px',
              border: 'none',
              background: '#3b82f6',
              cursor: !value?.trim() || loading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              color: 'white',
              opacity: !value?.trim() || loading ? 0.6 : 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
            onClick={() => onConfirm(value?.trim())}
            disabled={!value?.trim() || loading}
          >
            {loading && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PromptDialog;