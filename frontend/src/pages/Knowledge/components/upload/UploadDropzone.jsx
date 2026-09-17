import React, { useRef } from 'react';
import { Plus } from 'lucide-react';

export default function UploadDropzone({
  activeTab,
  isUploading,
  uploadProgress,
  onFileSelect,
  compact = false,
}) {
  const fileInputRef = useRef(null);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files || []);
    for (const file of files) {
      onFileSelect(file);
    }
    e.target.value = null;
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const files = Array.from(e.dataTransfer.files || []);
    for (const file of files) {
      onFileSelect(file);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  if (compact) {
    return (
      <>
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: 'none' }}
          onChange={handleFileChange}
          multiple
        />
        <button
          onClick={handleUploadClick}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          disabled={isUploading}
          style={{
            padding: '8px 14px',
            borderRadius: 6,
            border: '1.5px dashed var(--accent)',
            background: 'transparent',
            color: isUploading ? 'var(--text-3)' : 'var(--accent)',
            fontSize: 12,
            cursor: isUploading ? 'not-used' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            whiteSpace: 'nowrap',
            opacity: isUploading ? 0.6 : 1,
            transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => !isUploading && (e.currentTarget.style.background = 'var(--accent-soft)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <Plus size={15} />
          {isUploading ? `Uploading ${uploadProgress}%` : 'Upload File'}
        </button>
      </>
    );
  }

  return (
    <>
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
      <div style={{ margin: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {activeTab === 'documents' ? (
          <div
            onClick={handleUploadClick}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            style={{
              padding: '16px 12px',
              border: '2px dashed var(--accent)',
              borderRadius: 8,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              cursor: 'pointer',
              color: 'var(--accent)',
              fontSize: 12,
              transition: 'background 0.15s',
              opacity: isUploading ? 0.6 : 1,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-soft)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <Plus size={20} />
            {isUploading ? (
              <>
                <span>Uploading {uploadProgress}%</span>
                <div style={{ width: '100%', height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${uploadProgress}%`, height: '100%', background: 'var(--accent)', transition: 'width 0.2s' }} />
                </div>
              </>
            ) : (
              <span>Drop or click to upload</span>
            )}
          </div>
        ) : (
          <div style={{ padding: '14px 12px', borderRadius: 8, fontSize: 12, color: 'var(--text-2)', textAlign: 'center' }}>
            Select a note to center the graph
          </div>
        )}
      </div>
    </>
  );
}