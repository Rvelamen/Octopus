import React, { useState, useEffect, useRef, memo } from 'react';
import {
  ChevronDown,
  ChevronUp,
  ChevronRight,
  FileText,
  FileEdit,
  FolderOpen,
  Terminal,
  Link2,
  ImageIcon,
  Cog,
  Circle,
  Loader2,
  CheckCircle2,
  Zap,
  CirclePause,
} from 'lucide-react';

const formatTotalTime = (ms) => {
  if (ms < 1000) return `${ms}ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${(seconds / 60).toFixed(1)}min`;
};

const formatTokenNumber = (num) => {
  if (!num && num !== 0) return null;
  const n = Number(num);
  if (Number.isNaN(n)) return null;
  return n.toLocaleString('zh-CN');
};

const TokenUsage = memo(({ tokenUsage }) => {
  if (!tokenUsage) return null;

  const promptTokens = tokenUsage.prompt_tokens ?? 0;
  const completionTokens = tokenUsage.completion_tokens ?? 0;
  const cachedTokens = tokenUsage.cached_tokens ?? 0;

  if (promptTokens <= 0 && completionTokens <= 0 && cachedTokens <= 0) return null;

  const cacheLabel = cachedTokens > 0 ? ` | 缓存命中: ${Number(cachedTokens).toLocaleString('zh-CN')}` : '';

  return (
    <span
      className="thought-token-usage"
      title={`输入: ${Number(promptTokens).toLocaleString('zh-CN')}${cacheLabel} | 输出: ${Number(completionTokens).toLocaleString('zh-CN')}`}
    >
      <Zap size={12} className="thought-token-icon" />
      <span className="thought-token-text">
        ↑{formatTokenNumber(promptTokens)}{cachedTokens > 0 && <span className="thought-token-cache">({formatTokenNumber(cachedTokens)} 缓存)</span>} ↓{formatTokenNumber(completionTokens)}
      </span>
    </span>
  );
});

const ExecutionTime = memo(({ isExecuting, totalMs }) => {
  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef(null);
  const rafRef = useRef(null);
  const lastUpdateRef = useRef(0);

  useEffect(() => {
    if (isExecuting) {
      startTimeRef.current = Date.now();
      setElapsed(0);
      const update = (timestamp) => {
        if (timestamp - lastUpdateRef.current >= 100) {
          setElapsed(Date.now() - startTimeRef.current);
          lastUpdateRef.current = timestamp;
        }
        rafRef.current = requestAnimationFrame(update);
      };
      rafRef.current = requestAnimationFrame(update);
    } else {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [isExecuting]);

  // 已完成：仅信 totalMs；缺失时不显示（避免竞态下误显 0ms）
  if (isExecuting) {
    if (elapsed <= 0) return null;
    return (
      <span className="thought-total-time">
        {formatTotalTime(elapsed)}
      </span>
    );
  }
  if (totalMs == null) return null;
  if (totalMs < 0) return null;

  return (
    <span className="thought-total-time">
      {formatTotalTime(totalMs)}
    </span>
  );
});

function parseArgs(args, partialArgs) {
  if (partialArgs && typeof partialArgs === 'object' && Object.keys(partialArgs).length > 0) {
    return partialArgs;
  }
  if (typeof args === 'string') {
    try {
      return JSON.parse(args || '{}');
    } catch {
      return {};
    }
  }
  return args && typeof args === 'object' ? args : {};
}

function basename(p) {
  if (!p || typeof p !== 'string') return '';
  const s = p.replace(/\\/g, '/');
  const i = s.lastIndexOf('/');
  return i >= 0 ? s.slice(i + 1) : s;
}

function truncate(str, max = 280) {
  if (!str) return '';
  const t = String(str).trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

function toolMeta(name) {
  const n = (name || '').toLowerCase();
  const map = {
    read_file: { Icon: FileText, verb: '查看了' },
    write_file: { Icon: FileEdit, verb: '写入了文件' },
    edit_file: { Icon: FileEdit, verb: '编辑了' },
    list_dir: { Icon: FolderOpen, verb: '浏览了目录' },
    exec: { Icon: Terminal, verb: '执行了命令' },
    web_fetch: { Icon: Link2, verb: '访问了链接' },
    image_understand: { Icon: ImageIcon, verb: '分析了图片' },
    image_generate: { Icon: ImageIcon, verb: '生成了图片' },
  };
  if (map[n]) return { ...map[n], key: n };
  return { Icon: Cog, verb: '执行了', key: n };
}

function buildPrimaryLine(toolName, parsed) {
  const { verb, key } = toolMeta(toolName);
  if (key === 'read_file' && parsed.path) {
    return `${verb} ${basename(parsed.path)}`;
  }
  if (key === 'write_file' && parsed.path) {
    return `${verb} ${basename(parsed.path)}`;
  }
  if (key === 'edit_file' && parsed.path) {
    return `${verb} ${basename(parsed.path)}`;
  }
  if (key === 'list_dir' && parsed.path) {
    return `${verb} ${basename(parsed.path) || parsed.path}`;
  }
  if (key === 'exec' && parsed.command) {
    return `${verb}`;
  }
  if (key === 'web_fetch' && (parsed.url || parsed.URL)) {
    return `${verb}`;
  }
  return `${verb} ${toolName || '工具'}`;
}

function buildDetailBlocks(toolName, parsed, result, error) {
  const blocks = [];
  const { key } = toolMeta(toolName);

  if (key === 'read_file' && parsed.path) {
    blocks.push({ type: 'path', text: parsed.path });
  } else if (key === 'write_file' && parsed.path) {
    blocks.push({ type: 'path', text: parsed.path });
  } else if (key === 'edit_file' && parsed.path) {
    blocks.push({ type: 'path', text: parsed.path });
  } else if (key === 'list_dir' && parsed.path) {
    blocks.push({ type: 'path', text: parsed.path });
  } else if (key === 'exec' && parsed.command) {
    blocks.push({ type: 'cmd', text: parsed.command });
  } else if (key === 'web_fetch' && (parsed.url || parsed.URL)) {
    blocks.push({ type: 'url', text: parsed.url || parsed.URL });
  } else if (Object.keys(parsed).length > 0) {
    try {
      blocks.push({ type: 'json', text: JSON.stringify(parsed, null, 2) });
    } catch {
      blocks.push({ type: 'text', text: String(parsed) });
    }
  }

  if (error) {
    blocks.push({ type: 'error', text: String(error) });
  } else if (result) {
    blocks.push({ type: 'result', text: truncate(result, 400) });
  }

  return blocks;
}

function StepIcon({ toolName, status }) {
  const { Icon } = toolMeta(toolName);
  const pending = status === 'pending' || status === 'streaming';
  const running = status === 'invoking' || status === 'running';
  const cancelled = status === 'cancelled';
  if (cancelled) {
    return <CirclePause size={14} className="thought-step-icon-svg thought-step-icon--cancelled" strokeWidth={1.75} />;
  }
  if (pending || running) {
    return <Loader2 size={14} className="thought-step-icon-svg spin" />;
  }
  return <Icon size={14} className="thought-step-icon-svg" strokeWidth={1.75} />;
}

function countSteps(segments) {
  return segments.filter((s) => s.type === 'tool').length;
}

function firstReasoningPreview(segments, maxLen = 56) {
  const r = segments.find((s) => s.type === 'reasoning' && s.text?.trim());
  if (!r) return '';
  const t = r.text.replace(/\s+/g, ' ').trim();
  return t.length <= maxLen ? t : `${t.slice(0, maxLen)}…`;
}

const REASONING_COLLAPSE_LEN = 44;
const PRIMARY_COLLAPSE_LEN = 40;

function reasoningNeedsToggle(text) {
  const t = (text || '').trim();
  return t.length > REASONING_COLLAPSE_LEN || t.includes('\n');
}

function toolStepNeedsToggle(details, primary) {
  if (details && details.length > 0) return true;
  const p = (primary || '').trim();
  return p.length > PRIMARY_COLLAPSE_LEN;
}

function stepKey(seg, idx) {
  return seg.type === 'reasoning' ? `r-${idx}` : `t-${seg.toolCallId ?? idx}`;
}

/**
 * 单用户回合内整段思考过程：无「第 N 轮」，仅「已完成思考 / 思考中…」
 * segments: { type:'reasoning', text } | { type:'tool', ... }
 */
function IterationFold({
  status = 'completed',
  segments = [],
  totalMs = null,
  tokenUsage = null,
  isExpanded: isExpandedProp,
  onToggleExpand,
}) {
  const [isExpandedInternal, setIsExpandedInternal] = useState(true);
  const [openSteps, setOpenSteps] = useState(() => new Set());
  const isExpanded = isExpandedProp !== undefined ? isExpandedProp : isExpandedInternal;
  const isRunning = status === 'active' || status === 'running';
  const isPaused = status === 'paused';

  const handleToggle = () => {
    if (onToggleExpand) onToggleExpand();
    else setIsExpandedInternal(!isExpandedInternal);
  };

  const toggleStep = (key) => {
    setOpenSteps((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const onStepRowKeyDown = (e, key) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleStep(key);
    }
  };

  const headerTitle = isRunning ? '思考中…' : isPaused ? '已暂停' : '已完成思考';
  const nTools = countSteps(segments);
  const preview =
    firstReasoningPreview(segments) ||
    (nTools > 0 ? `${nTools} 个步骤` : '');

  return (
    <div className={`thought-fold ${isRunning ? 'is-running' : isPaused ? 'is-paused' : 'is-done'}`}>
      <button type="button" className="thought-fold-header" onClick={handleToggle}>
        <span className="thought-fold-chevron">
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </span>
        {!isRunning && !isPaused && (
          <span className="thought-done-badge">
            <CheckCircle2 size={14} strokeWidth={2} />
          </span>
        )}
        {!isRunning && isPaused && (
          <span className="thought-paused-badge" title="用户已暂停生成">
            <CirclePause size={14} strokeWidth={2} />
          </span>
        )}
        <span
          className={`thought-fold-title ${isRunning ? 'thought-fold-title--thinking' : ''}`}
        >
          {headerTitle}
        </span>
        <ExecutionTime isExecuting={isRunning} totalMs={totalMs} />
        <TokenUsage tokenUsage={tokenUsage} />
        {!isExpanded && preview && (
          <span className="thought-fold-preview">{preview}</span>
        )}
      </button>

      {isExpanded && (
        <div className="thought-fold-body">
          <div className="thought-rail" aria-hidden />
          <div className="thought-steps">
            {segments.map((seg, idx) => {
              if (seg.type === 'reasoning') {
                const key = stepKey(seg, idx);
                const expandable = reasoningNeedsToggle(seg.text);
                const open = openSteps.has(key);

                return (
                  <div
                    key={key}
                    className={`thought-step ${expandable ? (open ? 'is-open' : 'is-collapsed') : 'is-static'}`}
                  >
                    <div className="thought-step-glyph">
                      <Circle size={6} className="thought-step-dot" fill="currentColor" />
                    </div>
                    <div className="thought-step-body">
                      {expandable ? (
                        <div
                          className="thought-step-row"
                          role="button"
                          tabIndex={0}
                          aria-expanded={open}
                          onClick={() => toggleStep(key)}
                          onKeyDown={(e) => onStepRowKeyDown(e, key)}
                        >
                          <p className="thought-step-text">{seg.text.trim()}</p>
                          <span className="thought-step-row-chev" aria-hidden>
                            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </span>
                        </div>
                      ) : (
                        <p className="thought-step-text">{seg.text.trim()}</p>
                      )}
                    </div>
                  </div>
                );
              }

              const tool = seg;
              const parsed = parseArgs(tool.args, tool.partialArgs);
              const primary = buildPrimaryLine(tool.toolName, parsed);
              const details = buildDetailBlocks(
                tool.toolName,
                parsed,
                tool.result,
                tool.error
              );
              const key = stepKey(seg, idx);
              const expandable = toolStepNeedsToggle(details, primary);
              const open = openSteps.has(key);

              return (
                <div
                  key={tool.toolCallId || `t-${idx}`}
                  className={`thought-step ${expandable ? (open ? 'is-open' : 'is-collapsed') : 'is-static'}`}
                >
                  <div className="thought-step-glyph">
                    <StepIcon toolName={tool.toolName} status={tool.status} />
                  </div>
                  <div className="thought-step-body">
                    {expandable ? (
                      <>
                        <div
                          className="thought-step-row"
                          role="button"
                          tabIndex={0}
                          aria-expanded={open}
                          onClick={() => toggleStep(key)}
                          onKeyDown={(e) => onStepRowKeyDown(e, key)}
                        >
                          <p className="thought-step-line">{primary}</p>
                          <span className="thought-step-row-chev" aria-hidden>
                            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </span>
                        </div>
                        {open &&
                          details.map((b, i) => (
                            <pre
                              key={i}
                              className={`thought-detail ${b.type === 'error' ? 'is-error' : ''}`}
                            >
                              {b.text}
                            </pre>
                          ))}
                      </>
                    ) : (
                      <>
                        <p className="thought-step-line">{primary}</p>
                        {details.map((b, i) => (
                          <pre
                            key={i}
                            className={`thought-detail ${b.type === 'error' ? 'is-error' : ''}`}
                          >
                            {b.text}
                          </pre>
                        ))}
                      </>
                    )}
                  </div>
                </div>
              );
            })}

            {isRunning && segments.length > 0 && (
              <div className="thought-step thought-pending-tail" aria-live="polite">
                <div className="thought-step-glyph thought-pending-tail__glyph">
                  <Circle size={6} className="thought-pending-tail__pulse" fill="currentColor" />
                </div>
                <div className="thought-step-body">
                  <p className="thought-pending-line">
                    <span className="thought-pending-text">继续处理</span>
                    <span className="thought-wave-dots" aria-hidden>
                      <span className="thought-wave-dots__dot" />
                      <span className="thought-wave-dots__dot" />
                      <span className="thought-wave-dots__dot" />
                    </span>
                  </p>
                </div>
              </div>
            )}

            {segments.length === 0 && (
              <div className="thought-step">
                <div className="thought-step-glyph">
                  <Circle size={6} className="thought-step-dot" fill="currentColor" />
                </div>
                <div className="thought-step-body">
                  <p className="thought-step-text thought-muted">暂无过程记录</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default IterationFold;
