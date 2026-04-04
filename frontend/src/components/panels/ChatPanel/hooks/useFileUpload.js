import { useState, useCallback } from 'react';

export function useFileUpload(sendWSMessage, selectedInstance) {
  const [pendingImages, setPendingImages] = useState([]);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);

  const addPendingImage = useCallback((file) => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const newImage = {
          id: `temp-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          file: file,
          preview: e.target.result,
          name: file.name,
          type: file.type,
          size: file.size
        };
        setPendingImages(prev => [...prev, newImage]);
        resolve();
      };
      reader.readAsDataURL(file);
    });
  }, []);

  const addPendingFile = useCallback((file) => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const newFile = {
          id: `temp-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          file: file,
          data: e.target.result,
          name: file.name,
          type: file.type,
          size: file.size
        };
        setPendingFiles(prev => [...prev, newFile]);
        resolve();
      };
      reader.readAsDataURL(file);
    });
  }, []);

  const removePendingImage = useCallback((imageId) => {
    setPendingImages(prev => prev.filter(img => img.id !== imageId));
  }, []);

  const removePendingFile = useCallback((fileId) => {
    setPendingFiles(prev => prev.filter(f => f.id !== fileId));
  }, []);

  const uploadImage = useCallback(async (image) => {
    try {
      const response = await sendWSMessage('image_upload', {
        image_data: image.preview,
        file_name: image.name,
        mime_type: image.type,
        session_instance_id: selectedInstance?.id
      }, 30000);

      if (response.data?.success) {
        return {
          path: response.data.file_path,
          name: response.data.file_name,
          full_path: response.data.full_path
        };
      }
      throw new Error(response.data?.error || 'Upload failed');
    } catch (err) {
      console.error('Failed to upload image:', err);
      throw err;
    }
  }, [sendWSMessage, selectedInstance]);

  const uploadFile = useCallback(async (file) => {
    try {
      const response = await sendWSMessage('file_upload', {
        file_data: file.data,
        file_name: file.name,
        mime_type: file.type,
        session_instance_id: selectedInstance?.id
      }, 60000);

      if (response.data?.success) {
        return {
          path: response.data.file_path,
          name: response.data.file_name,
          originalName: response.data.original_name,
          mimeType: response.data.mime_type,
          size: response.data.size
        };
      }
      throw new Error(response.data?.error || 'Upload failed');
    } catch (err) {
      console.error('Failed to upload file:', err);
      throw err;
    }
  }, [sendWSMessage, selectedInstance]);

  const clearPendingFiles = useCallback(() => {
    setPendingImages([]);
    setPendingFiles([]);
  }, []);

  return {
    pendingImages,
    pendingFiles,
    isUploading,
    setIsUploading,
    addPendingImage,
    addPendingFile,
    removePendingImage,
    removePendingFile,
    uploadImage,
    uploadFile,
    clearPendingFiles
  };
}
