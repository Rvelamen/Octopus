/**
 * 节点模板 - 底部悬浮弹窗
 * Coze 风格：两列网格、纯图标+名称、无折叠分类标题
 */

import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  Search,
  Bot,
  Puzzle,
  Code,
  BrainCircuit,
  Layers,
  Timer,
  GitFork,
  RefreshCw,
  Combine,
  ArrowRightCircle,
  ArrowLeftCircle,
  HelpCircle,
  Type,
  Globe,
  Braces,
  MessageSquare,
  GitMerge,
} from 'lucide-react';
import { FlowNodeTypeEnum } from '../../constants';

// 节点分类和模板数据
const nodeTemplates = [
  {
    category: '常用',
    nodes: [
      { type: FlowNodeTypeEnum.workflowStart, name: '工作流开始', icon: Bot, color: '#1a1a2e', inputs: [], outputs: [{ key: 'userChatInput', label: '用户输入' }, { key: 'userFiles', label: '用户文件' }], showTargetHandle: false, forbidDelete: true },
      { type: FlowNodeTypeEnum.llm, name: '大模型', icon: MessageSquare, color: '#7c3aed', inputs: [], outputs: [{ key: 'output', label: '输出' }], defaultData: { model: 'gpt-4o-mini', systemPrompt: '', userPrompt: '', outputs: [{ id: 'default_out', name: 'output', type: 'string' }] } },
      { type: FlowNodeTypeEnum.workflowEnd, name: '工作流结束', icon: GitMerge, color: '#ef4444', inputs: [{ key: 'result', label: '最终结果' }], outputs: [], showSourceHandle: false, forbidDelete: true },
      { type: FlowNodeTypeEnum.answerNode, name: '直接回复', icon: MessageSquare, color: '#22c55e', inputs: [{ key: 'text', label: '回复内容' }], outputs: [], showSourceHandle: false },
    ]
  },
  {
    category: '业务逻辑',
    nodes: [
      { type: FlowNodeTypeEnum.code, name: '代码', icon: Code, color: '#06b6d4' },
      { type: FlowNodeTypeEnum.ifElseNode, name: '选择器', icon: GitFork, color: '#06b6d4' },
      { type: FlowNodeTypeEnum.classifyQuestion, name: '意图识别', icon: BrainCircuit, color: '#06b6d4' },
      { type: FlowNodeTypeEnum.loop, name: '循环', icon: RefreshCw, color: '#06b6d4' },
      { type: FlowNodeTypeEnum.contentExtract, name: '批处理', icon: Layers, color: '#06b6d4' },
      { type: FlowNodeTypeEnum.variableUpdate, name: '变量聚合', icon: Combine, color: '#06b6d4' },
      { type: FlowNodeTypeEnum.readFiles, name: '异步任务', icon: Timer, color: '#06b6d4' },
    ]
  },
  {
    category: '输入&输出',
    nodes: [
      { type: FlowNodeTypeEnum.inputNode, name: '输入', icon: ArrowLeftCircle, color: '#6366f1' },
      { type: FlowNodeTypeEnum.pluginOutput, name: '输出', icon: ArrowRightCircle, color: '#6366f1' },
    ]
  },
  {
    category: '组件',
    nodes: [
      { type: FlowNodeTypeEnum.answerNode, name: '问答', icon: HelpCircle, color: '#6366f1' },
      { type: FlowNodeTypeEnum.textEditor, name: '文本处理', icon: Type, color: '#6366f1' },
      { type: FlowNodeTypeEnum.http, name: 'HTTP 请求', icon: Globe, color: '#3b82f6', inputs: [{ key: 'url', label: '请求地址' }, { key: 'method', label: '请求方法' }], outputs: [{ key: 'body', label: '响应体' }, { key: 'statusCode', label: '状态码' }, { key: 'headers', label: '响应头' }] },
      { type: FlowNodeTypeEnum.jsonSerialize, name: 'JSON 序列化', icon: Braces, color: '#6366f1' },
      { type: FlowNodeTypeEnum.jsonDeserialize, name: 'JSON 反序列化', icon: Braces, color: '#6366f1' },
    ]
  },
];

// 20px 图标 - Coze 风格：圆角背景 + 白色图标
const NodeIcon = ({ icon: Icon, color }) => {
  return (
    <div
      style={{
        width: '20px',
        height: '20px',
        borderRadius: '5px',
        background: color,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <Icon size={12} color="white" strokeWidth={2.5} />
    </div>
  );
};

// 节点项 - 两列网格中的单格：图标 + 名称
const NodeItem = ({ node, onSelect }) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 8px',
        borderRadius: '6px',
        cursor: 'pointer',
        transition: 'background 0.1s',
      }}
      className="node-template-item"
      onClick={() => onSelect(node)}
      title={node.name}
    >
      <NodeIcon icon={node.icon || Puzzle} color={node.color || '#666'} />
      <span
        style={{
          fontSize: '13px',
          color: '#374151',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          lineHeight: '20px',
        }}
      >
        {node.name}
      </span>
    </div>
  );
};

const CategorySection = ({ category, nodes, search, onSelectNode }) => {
  const filteredNodes = useMemo(() => {
    if (!search) return nodes;
    const q = search.toLowerCase();
    return nodes.filter((n) => n.name.toLowerCase().includes(q));
  }, [nodes, search]);

  if (search && filteredNodes.length === 0) return null;

  return (
    <div style={{ marginBottom: '12px' }}>
      {/* 分类标题 - 纯文本无交互 */}
      <div
        style={{
          fontSize: '14px',
          fontWeight: 500,
          color: '#6b7280',
          padding: '6px 8px',
          lineHeight: '20px',
        }}
      >
        {category}
      </div>

      {/* 两列网格 */}
      <div style={{ display: 'flex', flexWrap: 'wrap', padding: '0 4px' }}>
        {filteredNodes.map((node, idx) => (
          <div key={idx} style={{ flex: '0 0 50%', maxWidth: '50%' }}>
            <NodeItem node={node} onSelect={onSelectNode} />
          </div>
        ))}
      </div>
    </div>
  );
};

const NodeTemplates = ({ isOpen, onClose, onSelectNode }) => {
  const [search, setSearch] = useState('');
  const panelRef = useRef(null);

  // 点击面板外部关闭
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        onClose?.();
      }
    };
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  // 打开时重置搜索
  useEffect(() => {
    if (isOpen) {
      setSearch('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      {/* 透明遮罩层：点击外部关闭 */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 19,
        }}
        onClick={onClose}
      />
      <div
        ref={panelRef}
        style={{
          position: 'fixed',
          bottom: '90px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 20,
          width: '480px',
          minWidth: '480px',
          maxHeight: '60vh',
          background: 'white',
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
          border: '1px solid #e5e7eb',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 搜索框 */}
        <div style={{ padding: '12px', borderBottom: '1px solid #f3f4f6', flexShrink: 0 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              background: '#f9fafb',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '8px 12px',
              transition: 'all 0.15s',
            }}
          >
            <Search size={14} color="#9ca3af" />
            <input
              placeholder="搜索节点、插件、工作流"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                padding: 0,
                background: 'transparent',
                border: 'none',
                borderRadius: 0,
                color: '#374151',
                fontSize: '13px',
                flex: 1,
                outline: 'none',
                height: '28px',
              }}
            />
          </div>
        </div>

        {/* 分类列表 */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '8px',
          }}
        >
          {nodeTemplates.map(({ category, nodes }) => (
            <CategorySection
              key={category}
              category={category}
              nodes={nodes}
              search={search}
              onSelectNode={onSelectNode}
            />
          ))}
        </div>
      </div>
    </>
  );
};

export default NodeTemplates;
