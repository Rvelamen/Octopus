/**
 * JSON 序列化节点配置面板
 * 参考设计：输入变量选择器 + 固定输出展示
 */

import React, { useCallback } from 'react';
import { Info } from 'lucide-react';
import { Collapse, Tooltip } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';
import ExpressionEditorField from '../../common/ExpressionEditorField/index.jsx';

const NodeConfigDrawer = ({
  nodes,
  edges,
  currentNodeId,
  nodeData,
}) => {
  const [activeKey, setActiveKey] = React.useState(['input', 'output']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  const inputs = nodeData?.inputs || [];
  const outputs = nodeData?.outputs || [];

  const handleUpdateInputs = useCallback((newInputs) => {
    updateNode(currentNodeId, { ...nodeData, inputs: newInputs });
  }, [currentNodeId, nodeData, updateNode]);

  const handleUpdateInputValue = useCallback((index, value) => {
    const newInputs = inputs.map((input, i) =>
      i === index ? { ...input, value } : input
    );
    handleUpdateInputs(newInputs);
  }, [inputs, handleUpdateInputs]);

  const collapseItems = [
    {
      key: 'input',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>输入</span>
            <Tooltip title="选择或引用要序列化为 JSON 字符串的变量">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {inputs.map((input, index) => (
            <div key={input.id || index}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                marginBottom: '6px',
              }}>
                <span style={{
                  fontSize: '12px',
                  color: '#6b7280',
                  background: '#f3f4f6',
                  padding: '1px 6px',
                  borderRadius: '4px',
                }}>
                  str.
                </span>
                <span style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>
                  {input.name || 'input'}
                </span>
              </div>
              <ExpressionEditorField
                fields={[{ name: input.name || 'input', value: input.value || '' }]}
                onChange={(newFields) => {
                  if (newFields.length > 0) {
                    handleUpdateInputValue(index, newFields[0].value);
                  }
                }}
                nodes={nodes}
                edges={edges}
                currentNodeId={currentNodeId}
                compact
                useDropdown
                canAdd={false}
              />
            </div>
          ))}
          {inputs.length === 0 && (
            <div style={{
              padding: '16px',
              textAlign: 'center',
              color: '#9ca3af',
              fontSize: '13px',
            }}>
              暂无输入变量
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'output',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>输出</span>
            <Tooltip title="序列化后的 JSON 字符串输出">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {outputs.map((output, index) => (
            <div
              key={output.id || index}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                background: '#f9fafb',
                borderRadius: '8px',
              }}
            >
              <span style={{
                fontSize: '12px',
                color: '#6b7280',
                background: '#f3f4f6',
                padding: '1px 6px',
                borderRadius: '4px',
              }}>
                str.
              </span>
              <span style={{ fontSize: '13px', color: '#374151' }}>
                {output.name || 'output'}
              </span>
              <span style={{
                fontSize: '11px',
                color: '#9ca3af',
                marginLeft: 'auto',
              }}>
                String
              </span>
            </div>
          ))}
          {outputs.length === 0 && (
            <div style={{
              padding: '16px',
              textAlign: 'center',
              color: '#9ca3af',
              fontSize: '13px',
            }}>
              暂无输出变量
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <Collapse
        ghost
        activeKey={activeKey}
        onChange={setActiveKey}
        items={collapseItems}
        style={{
          '--ant-collapse-header-padding': '10px 0',
          '--ant-collapse-content-padding': '0',
        }}
      />
    </div>
  );
};

export default NodeConfigDrawer;
