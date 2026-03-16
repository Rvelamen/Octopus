import React from 'react';

/**
 * SwitchField 组件 - 开关按钮
 */
function SwitchField({ label, checked, onChange }) {
  return (
    <div className="form-field switch-field">
      <label className="form-label">{label}</label>
      <button
        type="button"
        className={`pixel-switch ${checked ? 'active' : ''}`}
        onClick={() => onChange(!checked)}
      >
        <span className="switch-indicator">{checked ? '[ON]' : '[OFF]'}</span>
      </button>
    </div>
  );
}

export default SwitchField;
