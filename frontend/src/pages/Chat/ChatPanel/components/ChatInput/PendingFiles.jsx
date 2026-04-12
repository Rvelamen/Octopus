import React from 'react';
import { FileText, X } from 'lucide-react';

function PendingFiles({ files, onRemove, formatBytes }) {
  if (!files || files.length === 0) return null;

  return (
    <div className="pending-files-container">
      {files.map((file) => (
        <div key={file.id} className="pending-file-item">
          <FileText size={16} />
          <div className="pending-file-info">
            <span className="pending-file-name" title={file.name}>
              {file.name.length > 20 ? file.name.substring(0, 17) + '...' : file.name}
            </span>
            <span className="pending-file-size">
              {formatBytes(file.size)}
            </span>
          </div>
          <button
            className="remove-file-btn"
            onClick={() => onRemove(file.id)}
            title="移除文件"
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}

export default PendingFiles;
