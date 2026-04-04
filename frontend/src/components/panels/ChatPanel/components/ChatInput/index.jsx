import React, { useState, useRef } from 'react';
import { 
  Image, FileText, Maximize2, Minimize2, Send, CirclePause, 
  Paperclip, GripVertical 
} from 'lucide-react';
import PendingImages from './PendingImages';
import PendingFiles from './PendingFiles';
import './ChatInput.css';

function ChatInput({
  inputValue,
  onInputChange,
  onSend,
  onStop,
  isProcessing,
  isUploading,
  disabled,
  pendingImages,
  pendingFiles,
  onRemoveImage,
  onRemoveFile,
  onImageClick,
  onSelectFile,
  onSelectImage,
  onGenerateImage,
  placeholder
}) {
  const [isInputExpanded, setIsInputExpanded] = useState(false);
  const [inputHeight, setInputHeight] = useState(120);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const fileUploadRef = useRef(null);

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleKeyDown = (e) => {
    if (e.nativeEvent?.isComposing || e.isComposing) {
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    const imageItems = Array.from(items).filter(item => item.type.startsWith('image/'));
    if (imageItems.length > 0) {
      e.preventDefault();
      imageItems.forEach(item => {
        const file = item.getAsFile();
        if (file && onSelectImage) {
          onSelectImage(file);
        }
      });
    }
  };

  return (
    <div className="chat-input-wrapper">
      <PendingImages
        images={pendingImages}
        onRemove={onRemoveImage}
        onImageClick={onImageClick}
      />
      
      <PendingFiles
        files={pendingFiles}
        onRemove={onRemoveFile}
        formatBytes={formatBytes}
      />

      <div className={`inputbar-container ${isInputExpanded ? 'expanded' : ''}`}>
        <div 
          className="inputbar-drag-handle"
          onMouseDown={(e) => {
            const startY = e.clientY;
            const startHeight = inputHeight;
            const handleMouseMove = (moveEvent) => {
              const deltaY = startY - moveEvent.clientY;
              const newHeight = Math.max(60, Math.min(300, startHeight + deltaY));
              setInputHeight(newHeight);
            };
            const handleMouseUp = () => {
              document.removeEventListener('mousemove', handleMouseMove);
              document.removeEventListener('mouseup', handleMouseUp);
            };
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
          }}
        >
          <GripVertical size={14} />
        </div>

        <div className="inputbar-textarea-wrapper">
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={placeholder}
            className="inputbar-textarea"
            disabled={isProcessing || isUploading || disabled}
            autoFocus
            style={{ height: isInputExpanded ? inputHeight : 60 }}
          />
        </div>

        <div className="inputbar-bottom-bar">
          <div className="inputbar-left-tools">
            <button
              className="inputbar-tool-btn"
              onClick={() => setIsInputExpanded(!isInputExpanded)}
              title={isInputExpanded ? "收起编辑区" : "展开编辑区"}
            >
              {isInputExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>
            
            <button
              className="inputbar-tool-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={isProcessing || isUploading || disabled}
              title="上传图片"
            >
              <Image size={16} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => {
                const files = Array.from(e.target.files);
                files.forEach(file => onSelectImage && onSelectImage(file));
                e.target.value = '';
              }}
              style={{ display: 'none' }}
            />
            
            <button
              className="inputbar-tool-btn"
              onClick={() => fileUploadRef.current?.click()}
              disabled={isProcessing || isUploading || disabled}
              title="上传文件"
            >
              <Paperclip size={16} />
            </button>
            <input
              ref={fileUploadRef}
              type="file"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.md,.json,.csv,.xml,.zip,.tar,.gz"
              multiple
              onChange={(e) => {
                const files = Array.from(e.target.files);
                files.forEach(file => onSelectFile && onSelectFile(file));
                e.target.value = '';
              }}
              style={{ display: 'none' }}
            />
            
            <button
              className="inputbar-tool-btn"
              onClick={onGenerateImage}
              disabled={isProcessing || isUploading || disabled}
              title="生成图片"
            >
              <FileText size={16} />
            </button>
          </div>
          
          <div className="inputbar-right-tools">
            {inputValue.length > 0 && (
              <span className="inputbar-char-count">{inputValue.length}</span>
            )}
            
            {isProcessing ? (
              <button
                className="inputbar-send-btn pause"
                onClick={onStop}
                title="停止生成"
              >
                <CirclePause size={18} />
              </button>
            ) : (
              <button
                className="inputbar-send-btn"
                onClick={onSend}
                disabled={isUploading || disabled || (!inputValue.trim() && pendingImages.length === 0 && pendingFiles.length === 0)}
                title="发送消息"
              >
                <Send size={18} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatInput;
