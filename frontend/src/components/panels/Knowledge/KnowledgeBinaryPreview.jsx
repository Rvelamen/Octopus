import React from 'react';
import {
  ImageViewer,
  PdfViewer,
  XlsxViewer,
  DocxViewer,
  PptxViewer,
  BinaryViewer,
} from '../FileViewers';

export default function KnowledgeBinaryPreview({ fileName, content, encoding }) {
  const fileExt = fileName.split('.').pop()?.toLowerCase() || '';
  const fileObj = { name: fileName, path: '', encoding };
  const isImage = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(fileExt);
  const isPptx = ['pptx', 'ppt'].includes(fileExt);
  const isDocx = ['docx', 'doc'].includes(fileExt);

  if (isImage) return <ImageViewer file={fileObj} content={content} fileExt={fileExt} />;
  if (fileExt === 'pdf') return <PdfViewer file={fileObj} content={content} />;
  if (['xlsx', 'xls'].includes(fileExt)) return <XlsxViewer file={fileObj} content={content} />;
  if (isPptx) return <PptxViewer file={fileObj} content={content} />;
  if (isDocx) return <DocxViewer file={fileObj} content={content} />;
  return <BinaryViewer file={fileObj} content={content} />;
}
