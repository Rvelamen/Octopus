import React, { useState, useEffect, useRef, memo, useMemo } from 'react';
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
  Eye,
  Bot,
  Clock,
  Coins,
} from 'lucide-react';
import { Modal } from 'antd';
import ReactMarkdown from 'react-markdown';

// 格式化为分秒显示（如 9m 48s）
const formatTotalTime = (ms) => {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
};

// 格式化为 xxxK 显示（如 124.3k）
const formatTokenNumber = (num) => {
  if (!num && num !== 0) return '0';
  const n = Number(num);
  if (Number.isNaN(n)) return '0';
  if (n >= 1000) {
    return `${(n / 1000).toFixed(1)}k`;
  }
  return n.toString();
};

const TokenUsage = memo(({ tokenUsage }) => {
  if (!tokenUsage) return null;

  const rawPromptTokens = tokenUsage.prompt_tokens ?? 0;
  const completionTokens = tokenUsage.completion_tokens ?? 0;
  const cachedTokens = tokenUsage.cached_tokens ?? 0;
  const totalTokens = rawPromptTokens + completionTokens + cachedTokens;

  if (totalTokens <= 0) return null;

  return (
    <span className="thought-token-usage">
      <Coins size={12} className="thought-token-icon" />
      <span className="thought-token-text">
        {formatTokenNumber(totalTokens)} tokens
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
        <Clock size={12} className="thought-time-icon" />
        <span className="thought-time-text">{formatTotalTime(elapsed)}</span>
      </span>
    );
  }
  if (totalMs == null) return null;
  if (totalMs < 0) return null;

  return (
    <span className="thought-total-time">
      <Clock size={12} className="thought-time-icon" />
      <span className="thought-time-text">{formatTotalTime(totalMs)}</span>
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

function stepKey(seg, idx, prefix = '') {
  const prefixStr = prefix ? `${prefix}-` : '';
  return seg.type === 'reasoning' ? `${prefixStr}r-${idx}` : `${prefixStr}t-${seg.toolCallId ?? idx}`;
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
  keyPrefix = '',
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
        <span className="thought-fold-meta">
          <ExecutionTime isExecuting={isRunning} totalMs={totalMs} />
          <TokenUsage tokenUsage={tokenUsage} />
        </span>
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
                const key = stepKey(seg, idx, keyPrefix);
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
              const key = stepKey(seg, idx, keyPrefix);
              const expandable = toolStepNeedsToggle(details, primary) || (tool.subagentCalls && tool.subagentCalls.length > 0);
              const open = openSteps.has(key);

              return (
                <div
                  key={key}
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
                          <div 
                            className="thought-step-row-actions"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {(tool.toolName === 'spawn' || tool.toolName === 'subagent') && (
                              <SpawnDetailButton
                                result={tool.result}
                                subagentCalls={tool.subagentCalls}
                                subagentLabel={tool.subagentCalls?.[0]?.subagentLabel}
                                streamingContent={tool.subagentStreamingContent}
                              />
                            )}
                            <span className="thought-step-row-chev" aria-hidden>
                              {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            </span>
                          </div>
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

// Spawn 工具详情按钮组件
function SpawnDetailButton({ result, subagentCalls, subagentLabel: propLabel, streamingContent }) {
  const [open, setOpen] = useState(false);

  // 优先使用 result 中的 iterations 数据，如果没有则使用 subagentCalls
  const subagentResult = useMemo(() => {
    if (result) {
      try {
        const parsed = JSON.parse(result);
        if (parsed.type === 'subagent_sync' && Array.isArray(parsed.iterations) && parsed.iterations.length > 0) {
          return parsed;
        }
      } catch {
        // not valid JSON
      }
    }
    return null;
  }, [result]);

  // 累积保存 subagentCalls 历史，避免第二次打开 Modal 时数据丢失
  const [subagentCallsHistory, setSubagentCallsHistory] = useState([]);
  useEffect(() => {
    if (subagentCalls && subagentCalls.length > 0) {
      setSubagentCallsHistory((prev) => {
        // 1) 先更新已有 call 的状态/结果等字段
        const merged = prev.map((oldCall) => {
          const newCall = subagentCalls.find((sc) => sc.id === oldCall.id);
          return newCall ? { ...oldCall, ...newCall } : oldCall;
        });
        // 2) 再追加全新的 call
        const newCalls = subagentCalls.filter(
          (newCall) => !prev.some((oldCall) => oldCall.id === newCall.id)
        );
        const next = [...merged, ...newCalls];
        return next;
      });
    }
  }, [subagentCalls]);

  // 使用累积的历史数据或实时数据
  const effectiveSubagentCalls = subagentResult?.iterations ? [] : subagentCallsHistory;
  const hasSubagentCalls = effectiveSubagentCalls.length > 0;

  // 提前计算所有派生值（在条件返回之前）
  const shouldShow = subagentResult || hasSubagentCalls || !!streamingContent;
  const label = subagentResult?.label || propLabel || 'Subagent';
  const status = subagentResult?.status || 'completed';
  const summary = subagentResult?.summary || '';
  const finalDuration = subagentResult?.duration || 0;
  const iterations = subagentResult?.iterations || [];

  // 判断是否正在运行中
  // 1) 有 subagentResult 时，按 result 中的 status 判断
  // 2) 没有 subagentResult 时，查看 subagentCalls 中是否还有未完成的步骤
  const isRunning = subagentResult
    ? status !== 'completed'
    : hasSubagentCalls;


  // 实时计算 token_usage
  const [liveTokenUsage, setLiveTokenUsage] = useState({ prompt_tokens: 0, completion_tokens: 0 });
  useEffect(() => {
    if (subagentResult?.token_usage) {
      setLiveTokenUsage(subagentResult.token_usage);
    } else if (hasSubagentCalls) {
      let promptTokens = 0;
      let completionTokens = 0;
      effectiveSubagentCalls.forEach((sc) => {
        if (sc.tokenUsage) {
          promptTokens += sc.tokenUsage.prompt_tokens || 0;
          completionTokens += sc.tokenUsage.completion_tokens || 0;
        }
      });
      setLiveTokenUsage({ prompt_tokens: promptTokens, completion_tokens: completionTokens });
    }
  }, [subagentResult, effectiveSubagentCalls, hasSubagentCalls]);

  // 实时计算 duration
  const [liveDuration, setLiveDuration] = useState(0);
  const startTimeRef = useRef(null);
  useEffect(() => {
    if (finalDuration > 0) {
      setLiveDuration(finalDuration);
      return;
    }
    if (isRunning && open) {
      startTimeRef.current = Date.now();
      const interval = setInterval(() => {
        setLiveDuration((Date.now() - startTimeRef.current) / 1000);
      }, 100);
      return () => clearInterval(interval);
    }
  }, [isRunning, open, finalDuration]);

  const token_usage = subagentResult?.token_usage || liveTokenUsage;
  const duration = finalDuration > 0 ? finalDuration : liveDuration;

  // 将 iterations 或 subagentCalls 转换为 segments
  // 生成唯一的 key 前缀，避免与外部 IterationFold 冲突
  const keyPrefixRef = useRef(`modal-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  const keyPrefix = keyPrefixRef.current;

  const detailSegments = useMemo(() => {
    // 优先使用 iterations（最终完整数据）
    if (iterations.length > 0) {
      const segments = [];
      for (const iter of iterations) {
        if (iter.reasoning) {
          segments.push({ type: 'reasoning', text: iter.reasoning, keyPrefix });
        }
        for (const tool of iter.tools || []) {
          segments.push({
            type: 'tool',
            toolCallId: `${keyPrefix}-${tool.toolCallId}`,
            toolName: tool.toolName,
            args: typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args || {}),
            result: tool.result,
            status: tool.status || 'completed',
            error: tool.status === 'error' ? tool.result : undefined,
          });
        }
      }
      return segments;
    }

    // 如果没有 iterations，使用 subagentCalls（历史数据）+ 实时 streamingContent
    // streamingContent 是当前正在生成的 reasoning，理应放在已完成的 tool calls 之后
    const segments = [];
    if (hasSubagentCalls) {
      segments.push(...effectiveSubagentCalls.map((sc) => ({
        type: 'tool',
        toolCallId: `${keyPrefix}-${sc.id}`,
        toolName: sc.tool,
        args: typeof sc.args === 'string' ? sc.args : JSON.stringify(sc.args || {}),
        result: sc.result,
        status: sc.status || 'running',
        error: sc.error,
      })));
    }
    if (streamingContent) {
      segments.push({ type: 'reasoning', text: streamingContent, keyPrefix });
    }
    return segments;
  }, [iterations, effectiveSubagentCalls, hasSubagentCalls, keyPrefix, streamingContent]);

  // 如果没有 result 数据也没有 subagentCalls，不显示按钮
  if (!shouldShow) return null;

  return (
    <>
      <button
        type="button"
        className="spawn-detail-btn"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        title="查看 ReAct 执行流程"
      >
        <Eye size={12} />
        <span>详情</span>
      </button>

      <Modal
        open={open}
        onCancel={() => setOpen(false)}
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Bot size={16} style={{ color: '#6366f1' }} />
            <span>{label} — ReAct 流程</span>
          </div>
        }
        width={720}
        footer={null}
        destroyOnClose
      >
        <div 
          style={{ maxHeight: '70vh', overflowY: 'auto', paddingRight: 4 }}
          onClick={(e) => e.stopPropagation()}
        >
          {detailSegments.length > 0 ? (
            <IterationFold
              status={isRunning ? 'running' : 'completed'}
              segments={detailSegments}
              totalMs={duration * 1000}
              tokenUsage={token_usage}
              keyPrefix={keyPrefix}
            />
          ) : isRunning ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#666' }}>
              <div style={{ marginBottom: 16 }}>
                <span className="processing-spinner" style={{
                  display: 'inline-block',
                  width: 24,
                  height: 24,
                  border: '2px solid #e5e7eb',
                  borderTop: '2px solid #6366f1',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite'
                }} />
              </div>
              <div style={{ fontSize: 14, color: '#666' }}>
                思考中
                <span className="processing-dots" style={{ marginLeft: 4 }}>
                  <span style={{ animation: 'dot 1.4s infinite', animationDelay: '0s' }}>.</span>
                  <span style={{ animation: 'dot 1.4s infinite', animationDelay: '0.2s' }}>.</span>
                  <span style={{ animation: 'dot 1.4s infinite', animationDelay: '0.4s' }}>.</span>
                </span>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#999' }}>
              暂无执行流程记录
            </div>
          )}
          {!isRunning && summary && (
            <div style={{ marginTop: 16, padding: 12, background: '#f5f5f5', borderRadius: 8, border: '1px solid #e0e0e0' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 8 }}>最终结果</div>
              <div style={{ fontSize: 13, lineHeight: 1.6, color: '#333' }}>
                <ReactMarkdown>{summary}</ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      </Modal>
    </>
  );
}

export default IterationFold;
