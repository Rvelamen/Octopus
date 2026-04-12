import React from 'react';

/**
 * InputField 组件 - 文本输入框
 */
function InputField({ label, value, onChange, type = 'text', placeholder = '', disabled = false }) {
  return (
    <div className="form-field">
      <label className="form-label">{label}</label>
      <input
        type={type}
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="pixel-input form-input"
      />
    </div>
  );
}

export default InputField;
