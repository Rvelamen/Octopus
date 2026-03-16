/**
 * 链接处理工具函数
 */

// URL 正则表达式 - 匹配 http/https 链接
const URL_REGEX = /(https?:\/\/[^\s<>"{}|\^`\[\]]+)/g;

/**
 * 将文本中的 URL 转换为可点击的链接元素
 * @param {string} text - 原始文本
 * @returns {Array} - 返回包含文本和链接元素的数组
 */
export function parseLinks(text) {
  if (!text) return [];

  const parts = [];
  let lastIndex = 0;
  let match;

  // 复制正则表达式以避免全局标志问题
  const regex = new RegExp(URL_REGEX.source, 'g');

  while ((match = regex.exec(text)) !== null) {
    // 添加 URL 之前的文本
    if (match.index > lastIndex) {
      parts.push({
        type: 'text',
        content: text.slice(lastIndex, match.index)
      });
    }

    // 添加 URL 链接
    const url = match[1];
    parts.push({
      type: 'link',
      url: url,
      displayText: url
    });

    lastIndex = match.index + match[0].length;
  }

  // 添加剩余的文本
  if (lastIndex < text.length) {
    parts.push({
      type: 'text',
      content: text.slice(lastIndex)
    });
  }

  return parts.length > 0 ? parts : [{ type: 'text', content: text }];
}

/**
 * 检查文本是否包含 URL
 * @param {string} text - 要检查的文本
 * @returns {boolean} - 是否包含 URL
 */
export function containsUrl(text) {
  if (!text) return false;
  return URL_REGEX.test(text);
}
