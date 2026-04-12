import React from 'react';
import {
  Folder,
  FileText,
  FileType,
  Image,
  Archive,
  Code2,
  Table,
  FileSpreadsheet,
  Presentation,
  Film,
  Music,
  File,
  FileCode,
  Database,
  FileJson,
} from 'lucide-react';

const FILE_TYPE_CONFIG = {
  folder: { Icon: Folder, color: '#FFBF2B', bgColor: 'rgba(255, 191, 43, 0.12)' },
  md: { Icon: FileText, color: '#51CF66', bgColor: 'rgba(81, 207, 102, 0.12)' },
  pdf: { Icon: FileType, color: '#FF6B6B', bgColor: 'rgba(255, 107, 107, 0.12)' },
  image: { Icon: Image, color: '#CC5DE8', bgColor: 'rgba(204, 93, 232, 0.12)' },
  archive: { Icon: Archive, color: '#FD7E14', bgColor: 'rgba(253, 126, 20, 0.12)' },
  code: { Icon: Code2, color: '#339AF0', bgColor: 'rgba(51, 154, 240, 0.12)' },
  table: { Icon: FileSpreadsheet, color: '#40C057', bgColor: 'rgba(64, 192, 87, 0.12)' },
  document: { Icon: FileText, color: '#228BE6', bgColor: 'rgba(34, 139, 230, 0.12)' },
  presentation: { Icon: Presentation, color: '#F76707', bgColor: 'rgba(247, 103, 7, 0.12)' },
  video: { Icon: Film, color: '#E64980', bgColor: 'rgba(230, 73, 128, 0.12)' },
  audio: { Icon: Music, color: '#F06595', bgColor: 'rgba(240, 101, 149, 0.12)' },
  data: { Icon: Database, color: '#845EF7', bgColor: 'rgba(132, 94, 247, 0.12)' },
  json: { Icon: FileJson, color: '#FAB005', bgColor: 'rgba(250, 176, 5, 0.12)' },
  default: { Icon: File, color: '#868E96', bgColor: 'rgba(134, 142, 150, 0.08)' },
};

const EXT_MAP = {
  md: 'md',
  markdown: 'md',
  pdf: 'pdf',
  png: 'image',
  jpg: 'image',
  jpeg: 'image',
  gif: 'image',
  webp: 'image',
  svg: 'image',
  bmp: 'image',
  ico: 'image',
  zip: 'archive',
  tar: 'archive',
  rar: 'archive',
  '7z': 'archive',
  gz: 'archive',
  bz2: 'archive',
  js: 'code',
  jsx: 'code',
  ts: 'code',
  tsx: 'code',
  py: 'code',
  go: 'code',
  rs: 'code',
  java: 'code',
  c: 'code',
  cpp: 'code',
  h: 'code',
  cs: 'code',
  rb: 'code',
  php: 'code',
  swift: 'code',
  kt: 'code',
  scala: 'code',
  rust: 'code',
  html: 'code',
  htm: 'code',
  css: 'code',
  scss: 'code',
  less: 'code',
  sass: 'code',
  xml: 'code',
  yaml: 'code',
  yml: 'code',
  sh: 'code',
  bash: 'code',
  zsh: 'code',
  sql: 'code',
  r: 'code',
  lua: 'code',
  vue: 'code',
  svelte: 'code',
  xlsx: 'table',
  xls: 'table',
  csv: 'table',
  ods: 'table',
  docx: 'document',
  doc: 'document',
  odt: 'document',
  rtf: 'document',
  txt: 'default',
  log: 'default',
  pptx: 'presentation',
  ppt: 'presentation',
  odp: 'presentation',
  mp4: 'video',
  mov: 'video',
  avi: 'video',
  mkv: 'video',
  webm: 'video',
  mp3: 'audio',
  wav: 'audio',
  flac: 'audio',
  ogg: 'audio',
  aac: 'audio',
  sqlite: 'data',
  db: 'data',
  json: 'json',
};

function getFileType(name, isDirectory) {
  if (isDirectory) return 'folder';
  const ext = name.split('.').pop()?.toLowerCase() || '';
  return EXT_MAP[ext] || 'default';
}

export default function FileIcon({ name, isDirectory, size = 48 }) {
  const type = getFileType(name, isDirectory);
  const config = FILE_TYPE_CONFIG[type] || FILE_TYPE_CONFIG.default;
  const { Icon, color, bgColor } = config;

  if (type === 'folder') {
    return (
      <div
        style={{
          width: size,
          height: size,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Icon size={size} style={{ color }} strokeWidth={1.5} />
      </div>
    );
  }

  const iconSize = Math.round(size * 0.55);

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 10,
        background: `linear-gradient(145deg, ${bgColor}, rgba(255,255,255,0.6))`,
        border: `1.5px solid ${color}22`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: `0 1px 3px ${color}15, inset 0 1px 0 rgba(255,255,255,0.7)`,
      }}
    >
      <Icon size={iconSize} style={{ color }} strokeWidth={1.8} />
    </div>
  );
}

export { FILE_TYPE_CONFIG, getFileType };
