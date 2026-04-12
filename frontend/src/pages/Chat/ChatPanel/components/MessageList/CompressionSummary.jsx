import React from 'react';
import { FileText } from 'lucide-react';

function CompressionSummary({ message, compressionInfo, formatTime, renderMessageContent }) {
  return (
    <div className="compression-summary-wrapper">
      <div className="compression-summary-card">
        <div className="compression-summary-header">
          <FileText size={16} />
          <span>对话摘要</span>
          {compressionInfo.compressed_count && (
            <span className="compression-badge">
              已压缩 {compressionInfo.compressed_count} 条消息
            </span>
          )}
        </div>
        <div className="compression-summary-content">
          {renderMessageContent(message.content)}
        </div>
        {compressionInfo.compressed_at && (
          <div className="compression-summary-footer">
            <span>压缩时间: {formatTime(compressionInfo.compressed_at)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default CompressionSummary;
