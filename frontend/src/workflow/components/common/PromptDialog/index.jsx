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
  fields = null,
}) => {
  const isMulti = Array.isArray(fields) && fields.length > 0;

  const [values, setValues] = useState(() => {
    if (isMulti) {
      const init = {};
      fields.forEach((f) => (init[f.key] = f.defaultValue || ''));
      return init;
    }
    return { single: defaultValue };
  });

  const inputRefs = useRef([]);

  useEffect(() => {
    if (isOpen) {
      if (isMulti) {
        const init = {};
        fields.forEach((f) => (init[f.key] = f.defaultValue || ''));
        setValues(init);
        setTimeout(() => inputRefs.current[0]?.focus(), 100);
      } else {
        setValues({ single: defaultValue });
        setTimeout(() => inputRefs.current[0]?.focus(), 100);
      }
    }
  }, [isOpen, defaultValue, isMulti, fields]);

  const handleChange = (key, val) => {
    setValues((prev) => ({ ...prev, [key]: val }));
  };

  const canConfirm = isMulti
    ? fields.every((f) => !f.required || (values[f.key] || '').trim())
    : !!(values.single || '').trim();

  const handleConfirm = () => {
    if (isMulti) {
      const result = {};
      fields.forEach((f) => {
        result[f.key] = (values[f.key] || '').trim();
      });
      onConfirm(result);
    } else {
      onConfirm(values.single?.trim());
    }
  };

  const handleKeyDown = (e, index) => {
    if (e.key === 'Enter' && canConfirm && !loading) {
      if (isMulti && index < fields.length - 1) {
        inputRefs.current[index + 1]?.focus();
      } else {
        handleConfirm();
      }
    }
    if (e.key === 'Escape' && !loading) {
      onClose();
    }
  };

  if (!isOpen) return null;

  const renderFields = () => {
    if (isMulti) {
      return fields.map((f, idx) => (
        <div key={f.key} style={{ marginBottom: idx < fields.length - 1 ? '12px' : 0 }}>
          {f.label && (
            <div style={{ fontSize: '13px', color: '#374151', marginBottom: '6px', fontWeight: 500 }}>
              {f.label}
              {f.required && <span style={{ color: '#ef4444', marginLeft: 4 }}>*</span>}
            </div>
          )}
          <input
            ref={(el) => (inputRefs.current[idx] = el)}
            value={values[f.key] || ''}
            onChange={(e) => handleChange(f.key, e.target.value)}
            placeholder={f.placeholder || ''}
            onKeyDown={(e) => handleKeyDown(e, idx)}
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
      ));
    }

    return (
      <>
        {label && (
          <div style={{ fontSize: '13px', color: '#374151', marginBottom: '6px', fontWeight: 500 }}>{label}</div>
        )}
        <input
          ref={(el) => (inputRefs.current[0] = el)}
          value={values.single || ''}
          onChange={(e) => handleChange('single', e.target.value)}
          placeholder={placeholder}
          onKeyDown={(e) => handleKeyDown(e, 0)}
          style={{
            width: '100%',
            padding: '10px 12px',
            border: '1px solid #d1d5db',
            borderRadius: '8px',
            fontSize: '14px',
            outline: 'none',
          }}
        />
      </>
    );
  };

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
          {renderFields()}
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
              cursor: !canConfirm || loading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              color: 'white',
              opacity: !canConfirm || loading ? 0.6 : 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
            onClick={handleConfirm}
            disabled={!canConfirm || loading}
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