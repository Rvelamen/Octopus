import React from 'react';
import { X, AlertTriangle, Loader2 } from 'lucide-react';

const ConfirmDialog = ({
  isOpen,
  onClose,
  onConfirm,
  title = '确认操作',
  message = '确定要执行此操作吗？',
  confirmText = '确定',
  cancelText = '取消',
  variant = 'danger',
  loading = false,
}) => {
  if (!isOpen) return null;

  const getColors = () => {
    switch (variant) {
      case 'danger':
        return {
          icon: '#ef4444',
          bg: '#fef2f2',
          border: '#fca5a5',
          btnBg: '#ef4444',
          btnHover: '#dc2626',
        };
      case 'warning':
        return {
          icon: '#f59e0b',
          bg: '#fffbeb',
          border: '#fcd34d',
          btnBg: '#f59e0b',
          btnHover: '#d97706',
        };
      case 'primary':
        return {
          icon: '#3b82f6',
          bg: '#eff6ff',
          border: '#93c5fd',
          btnBg: '#3b82f6',
          btnHover: '#2563eb',
        };
      default:
        return {
          icon: '#6b7280',
          bg: '#f9fafb',
          border: '#d1d5db',
          btnBg: '#6b7280',
          btnHover: '#4b5563',
        };
    }
  };

  const colors = getColors();

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
        <div style={{ padding: '20px 24px', textAlign: 'center' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: colors.bg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 12px',
            }}
          >
            <AlertTriangle size={24} color={colors.icon} />
          </div>
          <div style={{ fontSize: '16px', fontWeight: 600, color: '#1f2937', marginBottom: '8px' }}>
            {title}
          </div>
          <div style={{ fontSize: '14px', color: '#6b7280', lineHeight: 1.5 }}>
            {message}
          </div>
        </div>
        <div
          style={{
            display: 'flex',
            gap: '8px',
            padding: '12px 24px',
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
              background: colors.btnBg,
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              color: 'white',
              opacity: loading ? 0.7 : 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;