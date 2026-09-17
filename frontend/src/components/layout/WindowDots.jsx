import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * WindowDots — 窗口控制按钮组
 *
 * 两种使用模式：
 * - 装饰模式（默认，interactive=false）：用纯视觉的圆点呈现，不响应点击。
 *   适用于卡片头部等不需要真正关闭窗口的场景。
 * - 交互模式（interactive=true）：圆点是真实按钮，触发 Electron 主进程的
 *   窗口最小化 / 最大化 / 关闭。需要 window.electronAPI 暴露相应 IPC。
 */
function WindowDots({ interactive = false }) {
  const { t } = useTranslation();
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    if (!interactive) return undefined;
    if (!window.electronAPI?.windowIsMaximized) return undefined;

    let cancelled = false;
    window.electronAPI.windowIsMaximized().then((v) => {
      if (!cancelled) setIsMaximized(Boolean(v));
    });

    let unsubscribe = window.electronAPI.onWindowMaximizeChange
      ? window.electronAPI.onWindowMaximizeChange((v) => {
          if (!cancelled) setIsMaximized(Boolean(v));
        })
      : () => {};

    return () => {
      cancelled = true;
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  }, [interactive]);

  if (!interactive) {
    return (
      <div className="window-dots" aria-hidden="true">
        <span className="dot red" />
        <span className="dot yellow" />
        <span className="dot green" />
      </div>
    );
  }

  const handleMinimize = () => window.electronAPI?.windowMinimize?.();
  const handleMaximize = () => window.electronAPI?.windowMaximize?.();
  const handleClose = () => window.electronAPI?.windowClose?.();
  const tooltipMaximize = isMaximized ? t('window.restore') : t('window.maximize');

  return (
    <div className="window-dots" role="group" aria-label="Window controls">
      <button
        type="button"
        className="dot red"
        onClick={handleClose}
        title={t('window.close')}
        aria-label="Close window"
      />
      <button
        type="button"
        className="dot yellow"
        onClick={handleMinimize}
        title={t('window.minimize')}
        aria-label="Minimize window"
      />
      <button
        type="button"
        className={`dot green ${isMaximized ? 'is-maximized' : ''}`}
        onClick={handleMaximize}
        title={tooltipMaximize}
        aria-label={tooltipMaximize}
      />
    </div>
  );
}

export default WindowDots;
