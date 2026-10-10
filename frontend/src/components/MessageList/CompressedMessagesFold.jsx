import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Archive, ChevronRight } from 'lucide-react';

/**
 * 显示一组已压缩的历史消息（折叠面板）。
 *
 * - Collapsed: 居中卡片 + Archive 图标 + 「已压缩 N 条消息 · 压缩于 HH:MM」+ chevron
 * - Expanded:  内联展示原始消息（只读、淡色），与正常消息复用 renderMessageContent
 *
 * 数据完全由父组件 buildDisplayList 注入，无后端调用。
 */
function CompressedMessagesFold({
  count,
  compressedAt,
  messages = [],
  formatTime,
  renderMessageContent,
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  const handleToggle = () => {
    setExpanded((prev) => !prev);
  };

  // 折叠态文案：已压缩 N 条消息 · 压缩于 HH:MM
  const headerLabel = t('chat.compressed.label', { count });
  const headerTime = compressedAt ? formatTime(compressedAt) : '';

  return (
    <div className="compressed-fold-wrapper">
      <div className={`compressed-fold-card ${expanded ? 'is-expanded' : ''}`}>
        <button
          type="button"
          className="compressed-fold-header"
          onClick={handleToggle}
          aria-expanded={expanded}
        >
          <Archive size={14} className="compressed-fold-icon" />
          <span className="compressed-fold-label">{headerLabel}</span>
          {headerTime && (
            <span className="compressed-fold-time">
              {t('chat.compressed.compressedAt', { time: headerTime })}
            </span>
          )}
          <span className={`compressed-fold-chevron ${expanded ? 'expanded' : ''}`}>
            <ChevronRight size={14} />
          </span>
        </button>

        {expanded && (
          <div className="compressed-fold-body">
            {messages.length === 0 ? (
              <div className="compressed-fold-empty">
                {t('chat.compressed.collapse')}
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={msg.id ?? idx}
                  className="compressed-fold-message"
                  data-role={msg.role}
                >
                  <div className="compressed-fold-message-meta">
                    <span className="compressed-fold-message-role">{msg.role}</span>
                    {msg.timestamp && (
                      <span className="compressed-fold-message-time">
                        {formatTime(msg.timestamp)}
                      </span>
                    )}
                  </div>
                  <div className="compressed-fold-message-content">
                    {renderMessageContent
                      ? renderMessageContent(msg.content || '')
                      : msg.content}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default CompressedMessagesFold;