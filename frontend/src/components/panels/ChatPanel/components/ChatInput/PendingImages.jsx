import React from 'react';
import { X } from 'lucide-react';

function PendingImages({ images, onRemove, onImageClick }) {
  if (!images || images.length === 0) return null;

  return (
    <div className="pending-images-container">
      {images.map((image) => (
        <div key={image.id} className="pending-image-item" onClick={() => onImageClick(image)}>
          <img
            src={image.preview}
            alt={image.name}
            className="pending-image-preview"
          />
          <button
            className="remove-image-btn"
            onClick={(e) => {
              e.stopPropagation();
              onRemove(image.id);
            }}
            title="移除图片"
          >
            <X size={12} />
          </button>
          <span className="pending-image-name" title={image.name}>
            {image.name.length > 15 ? image.name.substring(0, 12) + '...' : image.name}
          </span>
        </div>
      ))}
    </div>
  );
}

export default PendingImages;
