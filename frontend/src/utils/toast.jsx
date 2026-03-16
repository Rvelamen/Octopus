import { message } from 'antd';

// 配置 message 全局配置
message.config({
  top: 24,
  duration: 3,
  maxCount: 5,
});

// 自定义样式配置，匹配项目现有的视觉风格
const customStyle = {
  success: {
    backgroundColor: '#dcfce7',
    borderColor: '#16a34a',
    color: '#14532d',
    boxShadow: '0 8px 24px rgba(17, 24, 39, 0.08)',
    border: '2px solid #16a34a',
    borderRadius: '14px',
    padding: '12px 16px',
    fontSize: '13px',
    fontWeight: 500,
  },
  error: {
    backgroundColor: '#fee2e2',
    borderColor: '#dc2626',
    color: '#7f1d1d',
    boxShadow: '0 8px 24px rgba(17, 24, 39, 0.08)',
    border: '2px solid #dc2626',
    borderRadius: '14px',
    padding: '12px 16px',
    fontSize: '13px',
    fontWeight: 500,
  },
  warning: {
    backgroundColor: '#ffedd5',
    borderColor: '#ea580c',
    color: '#7c2d12',
    boxShadow: '0 8px 24px rgba(17, 24, 39, 0.08)',
    border: '2px solid #ea580c',
    borderRadius: '14px',
    padding: '12px 16px',
    fontSize: '13px',
    fontWeight: 500,
  },
  info: {
    backgroundColor: '#dbeafe',
    borderColor: '#2563eb',
    color: '#1e3a8a',
    boxShadow: '0 8px 24px rgba(17, 24, 39, 0.08)',
    border: '2px solid #2563eb',
    borderRadius: '14px',
    padding: '12px 16px',
    fontSize: '13px',
    fontWeight: 500,
  },
  loading: {
    backgroundColor: '#f3f4f6',
    borderColor: '#6b7280',
    color: '#1f2937',
    boxShadow: '0 8px 24px rgba(17, 24, 39, 0.08)',
    border: '2px solid #6b7280',
    borderRadius: '14px',
    padding: '12px 16px',
    fontSize: '13px',
    fontWeight: 500,
  },
};

// 获取图标样式
const getIconStyle = (type) => {
  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '22px',
    height: '22px',
    borderRadius: '50%',
    fontSize: '12px',
    fontWeight: 700,
    marginRight: '12px',
    flexShrink: 0,
  };

  switch (type) {
    case 'success':
      return { ...baseStyle, backgroundColor: '#16a34a', color: '#ffffff' };
    case 'error':
      return { ...baseStyle, backgroundColor: '#dc2626', color: '#ffffff' };
    case 'warning':
      return { ...baseStyle, backgroundColor: '#ea580c', color: '#ffffff' };
    case 'info':
      return { ...baseStyle, backgroundColor: '#2563eb', color: '#ffffff' };
    case 'loading':
      return { ...baseStyle, backgroundColor: '#6b7280', color: '#ffffff' };
    default:
      return baseStyle;
  }
};

// 获取图标字符
const getIcon = (type) => {
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

// 创建自定义内容
const createContent = (msg, type) => {
  const iconStyle = getIconStyle(type);
  const icon = getIcon(type);

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <span style={iconStyle}>{icon}</span>
      <span>{msg}</span>
    </div>
  );
};

/**
 * Toast 工具函数 - 使用 antd message 组件
 * 保持与原有 Toast 组件相同的 API 接口
 */
export const toast = {
  /**
   * 显示成功提示
   * @param {string} msg - 提示消息
   * @param {number} duration - 显示时长(秒)，默认3秒
   */
  success: (msg, duration = 3) => {
    return message.success({
      content: createContent(msg, 'success'),
      duration,
      style: customStyle.success,
    });
  },

  /**
   * 显示错误提示
   * @param {string} msg - 提示消息
   * @param {number} duration - 显示时长(秒)，默认5秒
   */
  error: (msg, duration = 5) => {
    return message.error({
      content: createContent(msg, 'error'),
      duration,
      style: customStyle.error,
    });
  },

  /**
   * 显示警告提示
   * @param {string} msg - 提示消息
   * @param {number} duration - 显示时长(秒)，默认3秒
   */
  warning: (msg, duration = 3) => {
    return message.warning({
      content: createContent(msg, 'warning'),
      duration,
      style: customStyle.warning,
    });
  },

  /**
   * 显示信息提示
   * @param {string} msg - 提示消息
   * @param {number} duration - 显示时长(秒)，默认3秒
   */
  info: (msg, duration = 3) => {
    return message.info({
      content: createContent(msg, 'info'),
      duration,
      style: customStyle.info,
    });
  },

  /**
   * 显示加载提示
   * @param {string} msg - 提示消息
   * @param {number} duration - 显示时长(秒)，默认0秒(不自动关闭)
   */
  loading: (msg, duration = 0) => {
    return message.loading({
      content: createContent(msg, 'loading'),
      duration,
      style: customStyle.loading,
    });
  },

  /**
   * 关闭指定 key 的消息
   * @param {string} key - 消息 key
   */
  close: (key) => {
    message.destroy(key);
  },

  /**
   * 关闭所有消息
   */
  closeAll: () => {
    message.destroy();
  },
};

export default toast;
