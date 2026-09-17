import React, { memo, useMemo } from 'react';
import octopusAvatar from '@assets/images/octopus.png';

/**
 * StreamingMessageContent — 独立子树，负责流式 assistant 消息渲染。
 *
 * 设计要点：
 * 1. `memo` 包裹：仅当 content / renderMessageContent 引用变化才重渲染。
 *    父级 MessageList 的其他状态变化（messages、toolCalls 等）不会触发本组件重渲染。
 * 2. 增量边界检测：用 useMemo 在 streaming content 里寻找最近一个"稳定点"
 *    （双换行、闭合的代码块），仅对稳定段走 ReactMarkdown，末段作为等宽
 *    纯文本渲染，避免每次刷新都重新解析整段 markdown。
 * 3. 光标独立：`_` 通过 CSS `step-end` 闪烁，DOM 节点不重新创建。
 */
function StreamingMessageContentImpl({ content, renderMessageContent }) {
  const { stableText, tailText } = useMemo(() => {
    if (!content) return { stableText: '', tailText: '' };

    // 找最后一个稳定边界：双换行（段落结束）OR 配对的代码块围栏
    let boundary = -1;

    const paras = [...content.matchAll(/\n\n/g)];
    if (paras.length > 0) {
      boundary = Math.max(boundary, paras[paras.length - 1].index);
    }

    // 至少需要偶数个 ```\n 才算配对
    const fences = [...content.matchAll(/```\n/g)];
    if (fences.length >= 2) {
      boundary = Math.max(boundary, fences[fences.length - 1].index);
    }

    if (boundary < 0) {
      // 还没有任何稳定边界——整段都按纯文本渲染
      return { stableText: '', tailText: content };
    }

    return {
      stableText: content.slice(0, boundary + 2),
      tailText: content.slice(boundary + 2),
    };
  }, [content]);

  return (
    <div className="message-row message-row-assistant streaming">
      <div className="message-bubble message-bubble-assistant">
        <div className="message-bubble-header">
          <div className="message-bubble-avatar">
            <img
              src={octopusAvatar}
              className="avatar-assistant-img"
              alt="Octopus"
            />
          </div>
          <div className="message-bubble-meta">
            <span className="message-bubble-author">Octopus</span>
            <span className="message-bubble-time streaming-indicator">
              <span className="blink">streaming</span>
            </span>
          </div>
        </div>
        <div className="message-bubble-content">
          {stableText && renderMessageContent(stableText)}
          {tailText && <pre className="md-tail-pending">{tailText}</pre>}
          <span className="cursor-blink" aria-hidden="true">_</span>
        </div>
      </div>
    </div>
  );
}

export default memo(StreamingMessageContentImpl);
