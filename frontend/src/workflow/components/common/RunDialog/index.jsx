import React, { useState, useMemo, useEffect } from 'react';
import { Play, Loader2, X } from 'lucide-react';

const RunDialog = ({
  isOpen,
  onClose,
  onConfirm,
  workflowName,
  inputVariables = [],
  isRunning = false,
}) => {
  const [values, setValues] = useState({});

  useEffect(() => {
    if (isOpen) {
      const initial = {};
      inputVariables.forEach((v) => {
        initial[v.name] = '';
      });
      setValues(initial);
    }
  }, [isOpen, inputVariables]);

  const handleChange = (name, value) => {
    setValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleConfirm = () => {
    const filled = {};
    inputVariables.forEach((v) => {
      filled[v.name] = values[v.name] || '';
    });
    onConfirm(filled);
  };

  const getTypePlaceholder = (type) => {
    if (!type) return '请输入...';
    const t = typeof type === 'string' ? type.toLowerCase() : 'string';
    const placeholders = {
      string: '文本内容...',
      number: '0',
      integer: '0',
      boolean: 'true / false',
    };
    return placeholders[t] || '请输入...';
  };

  const hasRequired = inputVariables.some((v) => v.required);
  const isValid = !hasRequired || inputVariables.every((v) => !v.required || (values[v.name] && values[v.name].trim() !== ''));

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
      onClick={isRunning ? undefined : onClose}
    >
      <div
        style={{
          background: 'white',
          borderRadius: '12px',
          width: '480px',
          maxHeight: '80vh',
          boxShadow: '0 20px 25px -5px rgba(0,0,0,0.15)',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
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
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: '#f0fdf4',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Play size={16} color="#22c55e" />
            </div>
            <div>
              <div style={{ fontSize: '15px', fontWeight: 600, color: '#1f2937' }}>
                运行工作流
              </div>
              <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '1px' }}>
                {workflowName || '未命名工作流'}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isRunning}
            style={{
              width: '28px',
              height: '28px',
              border: 'none',
              background: 'transparent',
              cursor: isRunning ? 'not-allowed' : 'pointer',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#9ca3af',
              opacity: isRunning ? 0.5 : 1,
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* 输入变量区域 */}
        <div style={{ padding: '16px 20px', overflow: 'auto', flex: 1 }}>
          {inputVariables.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <div style={{ fontSize: '14px', color: '#6b7280' }}>
                此工作流没有输入变量
              </div>
              <div style={{ fontSize: '12px', color: '#9ca3af', marginTop: '4px' }}>
                点击运行将直接执行
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: 500 }}>
                请输入以下变量
                {hasRequired && <span style={{ color: '#ef4444', marginLeft: '4px' }}>*必填</span>}
              </div>
              {inputVariables.map((variable) => (
                <div key={variable.name}>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '12px',
                      fontWeight: 500,
                      color: '#374151',
                      marginBottom: '4px',
                    }}
                  >
                    {variable.name}
                    {variable.required && <span style={{ color: '#ef4444', marginLeft: '2px' }}>*</span>}
                    <span
                      style={{
                        marginLeft: '8px',
                        fontSize: '11px',
                        color: '#9ca3af',
                        fontWeight: 400,
                      }}
                    >
                      {variable.type || 'String'}
                    </span>
                  </label>
                  <input
                    type="text"
                    value={values[variable.name] || ''}
                    onChange={(e) => handleChange(variable.name, e.target.value)}
                    placeholder={getTypePlaceholder(variable.type)}
                    disabled={isRunning}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                      fontSize: '13px',
                      outline: 'none',
                      color: '#374151',
                      background: isRunning ? '#f9fafb' : 'white',
                      transition: 'border-color 0.15s',
                      boxSizing: 'border-box',
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = '#3b82f6';
                      e.target.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.1)';
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = '#e5e7eb';
                      e.target.style.boxShadow = 'none';
                    }}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        <div
          style={{
            display: 'flex',
            gap: '8px',
            padding: '12px 20px',
            borderTop: '1px solid #f3f4f6',
          }}
        >
          <button
            onClick={onClose}
            disabled={isRunning}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '8px',
              border: '1px solid #e5e7eb',
              background: 'white',
              cursor: isRunning ? 'not-allowed' : 'pointer',
              fontSize: '13px',
              color: '#6b7280',
              opacity: isRunning ? 0.5 : 1,
            }}
          >
            取消
          </button>
          <button
            onClick={handleConfirm}
            disabled={isRunning || (!isValid && inputVariables.length > 0)}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '8px',
              border: 'none',
              background: isRunning || (!isValid && inputVariables.length > 0) ? '#d1d5db' : '#22c55e',
              cursor: isRunning || (!isValid && inputVariables.length > 0) ? 'not-allowed' : 'pointer',
              fontSize: '13px',
              fontWeight: 500,
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            {isRunning ? (
              <>
                <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                运行中...
              </>
            ) : (
              <>
                <Play size={14} />
                {inputVariables.length === 0 ? '直接运行' : '确认运行'}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RunDialog;