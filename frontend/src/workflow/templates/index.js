/**
 * 预设工作流模板
 * 每个模板包含完整的 nodes 和 edges 定义
 */

export const WORKFLOW_TEMPLATES = [
  {
    id: 'simple-chat',
    name: '简单对话',
    description: '用户输入 → AI 回复 → 结束',
    category: 'general',
    nodes: [
      {
        id: 'start-1',
        type: 'workflowStart',
        position: { x: 100, y: 200 },
        data: {
          flowNodeType: 'workflowStart',
          name: '工作流开始',
          intro: '接收用户输入',
          avatar: '🚀',
          colorSchema: 'blue',
          inputs: [],
          outputs: [
            { key: 'userChatInput', label: '用户输入' },
            { key: 'userFiles', label: '用户文件' }
          ]
        }
      },
      {
        id: 'llm-1',
        type: 'llm',
        position: { x: 400, y: 200 },
        data: {
          flowNodeType: 'llm',
          name: '大模型',
          intro: '与大语言模型对话',
          avatar: '🤖',
          colorSchema: 'purple',
          model: 'gpt-4o-mini',
          systemPrompt: '',
          userPrompt: '{{start-1.userChatInput}}',
          inputs: [
            { id: 'input_1', name: 'input', type: 'string', value: '{{start-1.userChatInput}}' }
          ],
          outputs: [
            { id: 'default_out', name: 'output', type: 'string' }
          ]
        }
      },
      {
        id: 'end-1',
        type: 'workflowEnd',
        position: { x: 700, y: 200 },
        data: {
          flowNodeType: 'workflowEnd',
          name: '工作流结束',
          intro: '输出最终结果',
          avatar: '🔚',
          colorSchema: 'red',
          inputs: [
            { key: 'result', label: '最终结果', inputType: 'reference', value: '{{llm-1.output}}' }
          ],
          outputs: []
        }
      }
    ],
    edges: [
      {
        id: 'e1',
        source: 'start-1',
        target: 'llm-1',
        sourceHandle: 'start-1-source',
        targetHandle: 'llm-1-target'
      },
      {
        id: 'e2',
        source: 'llm-1',
        target: 'end-1',
        sourceHandle: 'llm-1-source',
        targetHandle: 'end-1-target'
      }
    ]
  },
  {
    id: 'conditional-branch',
    name: '条件分支',
    description: '用户输入 → 问题分类 → 条件判断 → AI回复 → 结束',
    category: 'automation',
    nodes: [
      {
        id: 'start-1',
        type: 'workflowStart',
        position: { x: 100, y: 300 },
        data: {
          flowNodeType: 'workflowStart',
          name: '工作流开始',
          intro: '接收用户输入',
          avatar: '🚀',
          colorSchema: 'blue',
          inputs: [],
          outputs: [
            { key: 'userChatInput', label: '用户输入' },
            { key: 'userFiles', label: '用户文件' }
          ]
        }
      },
      {
        id: 'classify-1',
        type: 'classifyQuestion',
        position: { x: 400, y: 300 },
        data: {
          flowNodeType: 'classifyQuestion',
          name: '问题分类',
          intro: '将问题分类到不同类别',
          avatar: '📊',
          colorSchema: 'orange',
          inputs: [
            { key: 'content', label: '问题内容', inputType: 'reference', value: '{{start-1.userChatInput}}' },
            { key: 'categories', label: '分类选项', inputType: 'textarea', value: '产品咨询,技术支持,投诉建议' }
          ],
          outputs: [
            { key: 'cqResult', label: '分类结果' }
          ]
        }
      },
      {
        id: 'ifelse-1',
        type: 'ifElseNode',
        position: { x: 700, y: 300 },
        data: {
          flowNodeType: 'ifElseNode',
          name: '条件分支',
          intro: '根据分类结果执行不同分支',
          avatar: '🔀',
          colorSchema: 'pink',
          inputs: [
            { key: 'condition', label: '条件表达式', inputType: 'input', value: '{{classify-1.cqResult}} == "技术支持"' }
          ],
          outputs: [
            { key: 'system_resultTrue', label: '真分支' },
            { key: 'system_resultFalse', label: '假分支' }
          ]
        }
      },
      {
        id: 'llm-1',
        type: 'llm',
        position: { x: 1000, y: 200 },
        data: {
          flowNodeType: 'llm',
          name: '大模型',
          intro: '技术支持回复',
          avatar: '🤖',
          colorSchema: 'purple',
          model: 'gpt-4o-mini',
          systemPrompt: '你是技术支持专家，请专业地回答用户问题。',
          userPrompt: '{{start-1.userChatInput}}',
          inputs: [
            { id: 'input_1', name: 'input', type: 'string', value: '{{start-1.userChatInput}}' }
          ],
          outputs: [
            { id: 'default_out', name: 'output', type: 'string' }
          ]
        }
      },
      {
        id: 'llm-2',
        type: 'llm',
        position: { x: 1000, y: 400 },
        data: {
          flowNodeType: 'llm',
          name: '大模型',
          intro: '通用回复',
          avatar: '🤖',
          colorSchema: 'purple',
          model: 'gpt-4o-mini',
          systemPrompt: '你是友好的客服助手，请热情地回答用户问题。',
          userPrompt: '{{start-1.userChatInput}}',
          inputs: [
            { id: 'input_1', name: 'input', type: 'string', value: '{{start-1.userChatInput}}' }
          ],
          outputs: [
            { id: 'default_out', name: 'output', type: 'string' }
          ]
        }
      },
      {
        id: 'end-1',
        type: 'workflowEnd',
        position: { x: 1300, y: 300 },
        data: {
          flowNodeType: 'workflowEnd',
          name: '工作流结束',
          intro: '输出最终结果',
          avatar: '🔚',
          colorSchema: 'red',
          inputs: [
            { key: 'result', label: '最终结果', inputType: 'reference', value: '' }
          ],
          outputs: []
        }
      }
    ],
    edges: [
      {
        id: 'e1',
        source: 'start-1',
        target: 'classify-1',
        sourceHandle: 'start-1-source-userChatInput',
        targetHandle: 'classify-1-target-content'
      },
      {
        id: 'e2',
        source: 'classify-1',
        target: 'ifelse-1',
        sourceHandle: 'classify-1-source-cqResult',
        targetHandle: 'ifelse-1-target-condition'
      },
      {
        id: 'e3',
        source: 'ifelse-1',
        target: 'llm-1',
        sourceHandle: 'ifelse-1-source-system_resultTrue',
        targetHandle: 'llm-1-target'
      },
      {
        id: 'e4',
        source: 'ifelse-1',
        target: 'llm-2',
        sourceHandle: 'ifelse-1-source-system_resultFalse',
        targetHandle: 'llm-2-target'
      },
      {
        id: 'e5',
        source: 'llm-1',
        target: 'end-1',
        sourceHandle: 'llm-1-source',
        targetHandle: 'end-1-target'
      },
      {
        id: 'e6',
        source: 'llm-2',
        target: 'end-1',
        sourceHandle: 'llm-2-source',
        targetHandle: 'end-1-target'
      }
    ]
  }
];

/**
 * 从节点模板创建节点数据对象
 * @param {Object} template - 节点模板（来自 NodeTemplates）
 * @param {Object} position - { x, y }
 * @returns {Object} 节点数据，可直接传给 useWorkflowStore.addNode
 */
export const createNodeFromTemplate = (template, position) => {
  const data = {
    flowNodeType: template.type,
    name: template.name,
    intro: template.intro || '',
    avatar: template.avatar || '📦',
    colorSchema: template.colorSchema || 'gray',
    inputs: template.inputs || [],
    outputs: template.outputs || [],
    showTargetHandle: template.showTargetHandle,
    showSourceHandle: template.showSourceHandle,
    forbidDelete: template.forbidDelete,
  };

  // Merge any extra default data fields defined in the template (e.g. model, systemPrompt, userPrompt)
  if (template.defaultData && typeof template.defaultData === 'object') {
    Object.assign(data, template.defaultData);
  }

  return {
    id: `${template.type}-${Date.now()}`,
    type: template.type,
    position,
    data,
  };
};
