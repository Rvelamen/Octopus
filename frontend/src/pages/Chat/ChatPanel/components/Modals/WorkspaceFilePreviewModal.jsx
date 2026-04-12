import React, { useEffect, useState, useCallback } from 'react';
import { FileEditor } from '@pages/Workspace';
import { toWorkspaceRelativePath } from '../../utils/workspacePathUtils';
import './WorkspaceFilePreviewModal.css';

function WorkspaceFilePreviewModal({ sendWSMessage, pathInput, onClose }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [file, setFile] = useState(null);
  const [content, setContent] = useState('');

  const load = useCallback(async () => {
    if (!sendWSMessage || !pathInput) return;
    setLoading(true);
    setError(null);
    setFile(null);
    setContent('');
    try {
      const rootRes = await sendWSMessage('workspace_get_root', {}, 15000);
      const root = rootRes.data?.root || '';
      const rel = toWorkspaceRelativePath(pathInput, root);
      if (!rel) {
        setError('无法将该路径解析到当前工作区内，请确认文件在工作区目录下。');
        return;
      }
      const readRes = await sendWSMessage('workspace_read', { path: rel }, 120000);
      const d = readRes.data;
      if (!d?.name) {
        setError('读取文件失败。');
        return;
      }
      setFile({
        path: d.path,
        name: d.name,
        encoding: d.encoding,
        size: d.size,
      });
      setContent(d.content ?? '');
    } catch (e) {
      setError(e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [sendWSMessage, pathInput]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="workspace-file-preview-overlay" onClick={onClose} role="presentation">
      <div
        className="workspace-file-preview-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="工作区文件预览"
      >
        {loading && (
          <div className="workspace-file-preview-status">正在加载文件…</div>
        )}
        {!loading && error && (
          <div className="workspace-file-preview-status is-error">{error}</div>
        )}
        {!loading && !error && file && (
          <FileEditor
            file={file}
            content={content}
            onSave={() => {}}
            onClose={onClose}
            isSaving={false}
            readOnly
            sendWSMessage={sendWSMessage}
          />
        )}
      </div>
    </div>
  );
}

export default WorkspaceFilePreviewModal;
