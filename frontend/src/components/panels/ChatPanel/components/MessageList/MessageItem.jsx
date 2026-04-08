import React from 'react';
import { FileText, Sparkle, Copy, Check } from 'lucide-react';
import TTSPlayer from '../TTSPlayer';
import octopusAvatar from '../../../../../assets/images/octopus.png';

const API_BASE = 'http://localhost:18791';

function MessageItem({ 
  message, 
  ttsAudio, 
  onImageClick, 
  renderMessageContent,
  isStreaming = false,
  usage = null
}) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = React.useState(false);
  
  // Use prop usage if available, otherwise fall back to message.metadata.usage
  // Note: backend saves usage in metadata.metadata.usage (nested structure)
  const rawMetadata = message.metadata;
  const displayUsage = usage || rawMetadata?.usage || rawMetadata?.metadata?.usage;

  const formatTokenCount = (n) => {
    if (n == null || Number.isNaN(Number(n))) return '0';
    return Number(n).toLocaleString('zh-CN');
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    // 小于1分钟
    if (diff < 60000) return '刚刚';
    // 小于1小时
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    // 今天
    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    // 昨天
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) {
      return `昨天 ${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`;
    }
    // 其他
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  };

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const renderMessageImages = (metadata) => {
    const images = metadata?.images || metadata?.metadata?.images;
    if (!images || images.length === 0) return null;

    return (
      <div className="message-images">
        {images.map((img, idx) => (
          <div key={idx} className="message-image-item" onClick={() => onImageClick(img)}>
            <img
              src={img.path ? `${API_BASE}/workspace/${img.path}` : ''}
              alt={img.name || `Image ${idx + 1}`}
              onError={(e) => {
                console.log('Image load error, path:', img.path);
                e.target.src = '';
                e.target.style.display = 'none';
              }}
            />
            {img.name && <span className="message-image-name">{img.name}</span>}
          </div>
        ))}
      </div>
    );
  };

  const renderMessageFiles = (metadata) => {
    const files = metadata?.files || metadata?.metadata?.files;
    if (!files || files.length === 0) return null;
    
    return (
      <div className="message-files">
        {files.map((file, idx) => (
          <div key={idx} className="message-file-item">
            <FileText size={14} />
            <div className="file-info">
              <span className="file-name">{file.name || file.originalName || '未知文件'}</span>
              <span className="file-size">{formatBytes(file.size)}</span>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className={`message-row ${isUser ? 'message-row-user' : 'message-row-assistant'}`}>
      <div className={`message-bubble ${isUser ? 'message-bubble-user' : 'message-bubble-assistant'}`}>
        {/* Header */}
        <div className="message-bubble-header">
          <div className="message-bubble-avatar">
            {isUser ? (
              <div className="avatar-user">U</div>
            ) : (
              <img src={octopusAvatar} className="avatar-assistant-img" alt="Octopus" />
            )}
          </div>
          <div className="message-bubble-meta">
            <div className="message-bubble-author-row">
              <span className="message-bubble-author">{isUser ? 'You' : 'Octopus'}</span>
              {message.metadata?.useful && (
                <Sparkle size={14} className="useful-indicator" fill="var(--accent)" />
              )}
            </div>
            <div className="message-bubble-info">
              <span className="message-bubble-time">{formatTime(message.timestamp)}</span>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="message-bubble-content">
          {message.content ? renderMessageContent(message.content) : (
            message.metadata?.images ? <span className="image-placeholder">[图片]</span> : null
          )}
          {isStreaming && <span className="cursor-blink">▊</span>}
        </div>

        {/* Images & Files */}
        {renderMessageImages(message.metadata)}
        {renderMessageFiles(message.metadata)}

        {/* TTS Player */}
        {ttsAudio && !isUser && (
          <TTSPlayer 
            audioData={ttsAudio.audioData}
            format={ttsAudio.format}
            text={ttsAudio.text}
            durationMs={ttsAudio.durationMs}
            onClose={() => {}}
          />
        )}

        {!isUser && !isStreaming && message.content && (
          <div className="message-bubble-footer">
            <div className="message-bubble-footer-actions">
              <button
                type="button"
                className="message-action-btn"
                onClick={() => copyToClipboard(message.content)}
                title="复制内容"
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
              </button>
            </div>
            {displayUsage && (
              <span className="message-bubble-footer-tokens">
                Tokens:{' '}
                {formatTokenCount(
                  displayUsage.total_tokens != null
                    ? displayUsage.total_tokens
                    : (displayUsage.prompt_tokens || 0) + (displayUsage.completion_tokens || 0)
                )}{' '}
                ↑{formatTokenCount(displayUsage.prompt_tokens ?? 0)} ↓
                {formatTokenCount(displayUsage.completion_tokens ?? 0)}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default MessageItem;
