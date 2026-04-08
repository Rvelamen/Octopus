/**
 * 判断代码块内单行文本是否像「工作区内的文件路径」（可点击预览）。
 */
export function looksLikeWorkspaceFilePath(raw) {
  const t = String(raw ?? '').trim();
  if (!t || t.length > 4096 || t.includes('\n')) return false;
  if (/^https?:\/\//i.test(t)) return false;

  const lastSeg = t.split(/[/\\]/).pop() || '';
  if (!lastSeg.includes('.')) return false;
  const ext = lastSeg.split('.').pop();
  if (!ext || ext.length > 15) return false;

  if (t.startsWith('/')) return t.length > 1;
  if (/^[A-Za-z]:[\\/]/.test(t)) return true;
  if (t.includes('..')) return false;
  return /^[\w.\s/\\-]+$/.test(t);
}

function normalizePath(p) {
  return String(p || '')
    .replace(/\\/g, '/')
    .replace(/\/+$/, '');
}

/**
 * 将用户消息里的绝对路径或相对路径转为 workspace_read 使用的相对路径。
 */
export function toWorkspaceRelativePath(input, rootPath) {
  const line = String(input ?? '').trim();
  if (!line) return null;

  const root = normalizePath(rootPath);
  if (!root) return null;

  let abs = normalizePath(line);

  if (!abs.startsWith('/') && !/^[A-Za-z]:/.test(abs)) {
    if (line.includes('..')) return null;
    return line.replace(/\\/g, '/');
  }

  let rootCmp = root;
  let absCmp = abs;
  if (/^[A-Za-z]:/.test(absCmp)) {
    absCmp = absCmp.charAt(0).toUpperCase() + absCmp.slice(1);
  }
  if (/^[A-Za-z]:/.test(rootCmp)) {
    rootCmp = rootCmp.charAt(0).toUpperCase() + rootCmp.slice(1);
  }

  const prefix = `${rootCmp}/`;
  if (absCmp.startsWith(prefix)) {
    return abs.slice(prefix.length).replace(/\\/g, '/');
  }
  if (absCmp === rootCmp) {
    return '.';
  }

  const marker = '/workspace/';
  const i = abs.indexOf(marker);
  if (i >= 0) {
    const rel = abs.slice(i + marker.length);
    if (!rel.includes('..')) return rel;
  }

  return null;
}
