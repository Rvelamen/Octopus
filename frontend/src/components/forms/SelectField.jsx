import React from 'react';

/**
 * SelectField 组件 - 下拉选择框
 */
function SelectField({ label, value, onChange, options, disabled }) {
  return (
    <div className="form-field">
      <label className="form-label">{label}</label>
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        className="pixel-select form-input"
        disabled={disabled}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export default SelectField;
