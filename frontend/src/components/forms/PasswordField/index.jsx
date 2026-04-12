import React, { useState } from 'react';

/**
 * PasswordField 组件 - 密码输入框（带显示/隐藏切换）
 */
function PasswordField({ label, value, onChange, placeholder = '' }) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="form-field">
      <label className="form-label">{label}</label>
      <div className="password-input-wrapper">
        <input
          type={showPassword ? 'text' : 'password'}
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="pixel-input form-input"
        />
        <button
          type="button"
          className="toggle-password-btn"
          onClick={() => setShowPassword(!showPassword)}
        >
          {showPassword ? '[隐藏]' : '[显示]'}
        </button>
      </div>
    </div>
  );
}

export default PasswordField;
