import React from 'react';
import { Modal, message } from 'antd';
import { Copy, FolderOpen, ExternalLink, Keyboard } from 'lucide-react';

// 本地工具（如 Chrome 扩展）的"快捷安装"引导模态框。
// MV3 未打包扩展无法被网页一键安装，必须用户手动在 chrome://extensions
// 选"加载已解压"。本组件提供：复制路径 / 打开文件夹 / 打开浏览器扩展页
// 三个动作，把安装成本压到 3 步。
export default function LocalToolSetupModal({ tool, onClose }) {
  if (!tool) return null;

  const { installPath, extensionUrl, browserName, shortcut, name } = tool;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(installPath);
      message.success('路径已复制');
    } catch (err) {
      // Electron renderer 默认允许 clipboard API；若失败则降级为选中文本
      const input = document.createElement('input');
      input.value = installPath;
      document.body.appendChild(input);
      input.select();
      try {
        document.execCommand('copy');
        message.success('路径已复制');
      } catch {
        message.error('复制失败，请手动选中路径');
      }
      document.body.removeChild(input);
    }
  };

  const handleOpenFolder = async () => {
    if (!window.electronAPI?.openFolder) {
      message.warning('当前环境不支持打开文件夹');
      return;
    }
    const res = await window.electronAPI.openFolder(installPath);
    if (res && res.success === false) {
      message.error('打开失败: ' + (res.error || 'unknown'));
    }
  };

  const handleOpenExtensionsPage = async () => {
    if (!window.electronAPI?.openExternal) {
      // 浏览器环境兜底
      window.open(extensionUrl, '_blank');
      return;
    }
    const res = await window.electronAPI.openExternal(extensionUrl);
    if (res && res.success === false) {
      message.error('打开失败: ' + (res.error || 'unknown'));
    }
  };

  return (
    <Modal
      open
      onCancel={onClose}
      footer={null}
      title={`Setup: ${name}`}
      width={560}
      destroyOnClose
    >
      <ol className="setup-steps">
        <li>
          在打开的 <b>{browserName}</b> 扩展页{' '}
          <code>{extensionUrl}</code> 开启右上角的「<b>开发者模式</b>」
        </li>
        <li>
          点击「<b>加载已解压的扩展程序</b>」
        </li>
        <li>粘贴或选择下方路径：</li>
      </ol>

      <div className="setup-path-row">
        <input
          className="setup-path-input"
          value={installPath}
          readOnly
          onFocus={(e) => e.target.select()}
        />
        <button className="setup-btn setup-btn-secondary" onClick={handleCopy} title="复制路径">
          <Copy size={14} />
          <span>复制</span>
        </button>
      </div>

      {shortcut && (
        <div className="setup-shortcut">
          <Keyboard size={14} />
          <span>
            快捷键：<kbd>{shortcut}</kbd> 一键剪藏当前页
          </span>
        </div>
      )}

      <div className="setup-actions">
        <button className="setup-btn setup-btn-secondary" onClick={handleOpenFolder}>
          <FolderOpen size={14} />
          <span>打开文件夹</span>
        </button>
        <button className="setup-btn setup-btn-primary" onClick={handleOpenExtensionsPage}>
          <ExternalLink size={14} />
          <span>打开 {browserName} 扩展页</span>
        </button>
      </div>
    </Modal>
  );
}
