import React, { useState } from 'react';
import { X } from 'lucide-react';

const API_BASE = 'http://localhost:18791';

function ImageModal({ image, onClose }) {
  const [imageLoading, setImageLoading] = useState(true);

  const handleClose = () => {
    setImageLoading(false);
    onClose();
  };

  return (
    <div className="image-modal-overlay" onClick={handleClose}>
      <div className="image-modal-content" onClick={e => e.stopPropagation()}>
        <button className="image-modal-close" onClick={handleClose}>
          <X size={24} />
        </button>
        {imageLoading && (
          <div className="image-modal-loading">
            <div className="loading-spinner-large"></div>
            <span>加载中...</span>
          </div>
        )}
        <img
          src={image.preview || (image.path ? `${API_BASE}/workspace/${image.path}` : '')}
          alt={image.name || 'Image'}
          className={`image-modal-img ${imageLoading ? 'loading' : 'loaded'}`}
          onLoad={() => setImageLoading(false)}
          onError={() => setImageLoading(false)}
        />
        {image.name && (
          <div className="image-modal-name">{image.name}</div>
        )}
      </div>
    </div>
  );
}

export default ImageModal;
