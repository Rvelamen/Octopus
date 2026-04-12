import React, { useState } from 'react';
import { X, Image } from 'lucide-react';

function GenerateImageModal({ isOpen, onClose, onGenerate }) {
  const [prompt, setPrompt] = useState('');
  const [size, setSize] = useState('1024x1024');
  const [quality, setQuality] = useState('standard');
  const [isGenerating, setIsGenerating] = useState(false);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    
    setIsGenerating(true);
    try {
      await onGenerate({ prompt, size, quality });
      setPrompt('');
      onClose();
    } catch (error) {
      console.error('Generate image error:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="image-modal-overlay" onClick={onClose}>
      <div className="image-modal-content generate-modal" onClick={e => e.stopPropagation()}>
        <div className="generate-modal-header">
          <h3>生成图片</h3>
          <button className="image-modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="generate-modal-body">
          <div className="form-group">
            <label>描述提示词</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="描述你想要生成的图片，例如：一只可爱的橘猫在草地上玩耍..."
              rows={4}
              className="pixel-textarea"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>尺寸</label>
              <select
                value={size}
                onChange={(e) => setSize(e.target.value)}
                className="pixel-select"
              >
                <option value="1024x1024">1024x1024 (方形)</option>
                <option value="1024x1792">1024x1792 (竖版)</option>
                <option value="1792x1024">1792x1024 (横版)</option>
                <option value="512x512">512x512 (小图)</option>
              </select>
            </div>

            <div className="form-group">
              <label>质量</label>
              <select
                value={quality}
                onChange={(e) => setQuality(e.target.value)}
                className="pixel-select"
              >
                <option value="standard">Standard (标准)</option>
                <option value="hd">HD (高清)</option>
              </select>
            </div>
          </div>
        </div>

        <div className="generate-modal-footer">
          <button
            className="pixel-button secondary"
            onClick={onClose}
            disabled={isGenerating}
          >
            取消
          </button>
          <button
            className="pixel-button primary"
            onClick={handleGenerate}
            disabled={isGenerating || !prompt.trim()}
          >
            {isGenerating ? (
              <>
                <span className="loading-spinner-small"></span>
                生成中...
              </>
            ) : (
              <>
                <Image size={16} />
                生成图片
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default GenerateImageModal;
