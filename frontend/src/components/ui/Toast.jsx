import React, { useEffect, useState } from 'react';

/**
 * Toast 组件 - 轻量级通知提示
 * @param {string} message - 提示消息
 * @param {string} type - 类型: 'success' | 'error' | 'info' | 'warning'
 * @param {number} duration - 显示时长(毫秒), 默认3000ms
 * @param {function} onClose - 关闭回调
 */
function Toast({ message, type = 'info', duration = 3000, onClose }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // 触发进入动画
    const enterTimer = setTimeout(() => setVisible(true), 10);
    
    // 自动关闭
    const closeTimer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onClose?.(), 300); // 等待动画结束
    }, duration);

    return () => {
      clearTimeout(enterTimer);
      clearTimeout(closeTimer);
    };
  }, [duration, onClose]);

  const getIcon = () => {
    switch (type) {
      case 'success':
        return '✓';
      case 'error':
        return '✗';
      case 'warning':
        return '!';
      case 'loading':
        return '◌';
      case 'info':
      default:
        return 'i';
    }
  };

  return (
    <div className={`toast toast-${type} ${visible ? 'visible' : ''}`}>
      <span className="toast-icon">{getIcon()}</span>
      <span className="toast-message">{message}</span>
    </div>
  );
}

/**
 * ToastContainer 组件 - Toast容器
 */
export function ToastContainer({ toasts, removeToast }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
}

export default Toast;
