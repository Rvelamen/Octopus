import React, { useState } from 'react';
import VariableTypeSelector from './index';

function VariableTypeSelectorExample() {
  const [selectedType, setSelectedType] = useState('String');

  return (
    <div style={{ padding: '24px', maxWidth: '700px', background: '#fff', borderRadius: '12px' }}>
      <h3 style={{ marginBottom: '24px', color: '#1D2433' }}>🎯 变量类型选择器 - Antd Cascader 级联版本</h3>

      <div style={{ marginBottom: '20px' }}>
        <label style={{
          display: 'block',
          marginBottom: '8px',
          fontWeight: 500,
          color: '#1D2433',
          fontSize: '14px'
        }}>
          基础用法（支持级联选择）
        </label>
        <VariableTypeSelector
          value={selectedType}
          onChange={setSelectedType}
          placeholder="请选择变量类型"
        />
      </div>

      <div style={{
        padding: '16px',
        background: '#F3F4F6',
        borderRadius: '8px',
        marginBottom: '20px',
        fontSize: '14px',
        color: '#4B5565'
      }}>
        <strong>当前选中值：</strong>
        <code style={{
          marginLeft: '8px',
          padding: '2px 8px',
          background: '#fff',
          borderRadius: '4px',
          fontFamily: 'monospace',
          color: '#B46A57'
        }}>
          {selectedType || '未选择'}
        </code>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div>
          <label style={{
            display: 'block',
            marginBottom: '8px',
            fontWeight: 500,
            color: '#1D2433',
            fontSize: '14px'
          }}>
            基础类型
          </label>
          <VariableTypeSelector
            value="Number"
            onChange={() => {}}
            size="small"
          />
        </div>

        <div>
          <label style={{
            display: 'block',
            marginBottom: '8px',
            fontWeight: 500,
            color: '#1D2433',
            fontSize: '14px'
          }}>
            Array 类型（级联）
          </label>
          <VariableTypeSelector
            value="Array<Object>"
            onChange={() => {}}
            size="small"
          />
        </div>

        <div>
          <label style={{
            display: 'block',
            marginBottom: '8px',
            fontWeight: 500,
            color: '#1D2433',
            fontSize: '14px'
          }}>
            File 类型（级联）
          </label>
          <VariableTypeSelector
            value="File<Doc>"
            onChange={() => {}}
            size="small"
          />
        </div>

        <div>
          <label style={{
            display: 'block',
            marginBottom: '8px',
            fontWeight: 500,
            color: '#1D2433',
            fontSize: '14px'
          }}>
            File Default
          </label>
          <VariableTypeSelector
            value="File"
            onChange={() => {}}
            size="small"
          />
        </div>
      </div>

      <div style={{
        marginTop: '24px',
        padding: '16px',
        border: '1px solid #E7E9EE',
        borderRadius: '8px',
        fontSize: '13px',
        lineHeight: '1.8'
      }}>
        <strong style={{ display: 'block', marginBottom: '8px', color: '#1D2433' }}>
          ✨ 使用 Ant Design Cascader 级联选择器的优势：
        </strong>
        <ul style={{ margin: 0, paddingLeft: '20px', color: '#4B5565' }}>
          <li>📂 <strong>多层级结构</strong>：基础类型 + Array/File 子类型，层次清晰</li>
          <li>🎯 <strong>更好的用户体验</strong>：同一浮层完成多级选择，无需多次点击</li>
          <li>🔍 <strong>内置搜索</strong>：支持模糊搜索所有层级的选项</li>
          <li>⚡ <strong>性能优秀</strong>：支持大数据量和懒加载</li>
          <li>🎨 <strong>自定义显示</strong>：通过 displayRender 实现缩写格式</li>
        </ul>
      </div>

      <div style={{
        marginTop: '16px',
        padding: '16px',
        background: '#F0FDF4',
        border: '1px solid #86EFAC',
        borderRadius: '8px',
        fontSize: '12px',
        lineHeight: '1.6',
        color: '#166534'
      }}>
        <strong>✅ 已集成到工作流节点：</strong>
        <ul style={{ margin: '8px 0 0', paddingLeft: '20px' }}>
          <li><strong>WorkflowStartForm</strong> - 工作流开始节点 ✨</li>
          <li><strong>WorkflowEndForm</strong> - 工作流结束节点 ✨</li>
        </ul>
        <p style={{ margin: '8px 0 0', fontSize: '11px' }}>
          💡 提示：鼠标悬停在 Array 或 File 上会自动展开子菜单！
        </p>
      </div>

      <div style={{
        marginTop: '16px',
        padding: '16px',
        border: '1px solid #E7E9EE',
        borderRadius: '8px',
        fontSize: '13px',
        lineHeight: '1.6'
      }}>
        <strong style={{ display: 'block', marginBottom: '8px', color: '#1D2433' }}>
          📋 支持的完整类型列表（共25种）：
        </strong>
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '8px' }}>
          <thead>
            <tr style={{ background: '#F3F4F6' }}>
              <th style={{ padding: '8px', textAlign: 'left', borderBottom: '2px solid #E7E9EE' }}>分类</th>
              <th style={{ padding: '8px', textAlign: 'left', borderBottom: '2px solid #E7E9EE' }}>数量</th>
              <th style={{ padding: '8px', textAlign: 'left', borderBottom: '2px solid #E7E9EE' }}>示例</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ padding: '8px', borderBottom: '1px solid #F3F4F6' }}><strong>基础类型</strong></td>
              <td style={{ padding: '8px', borderBottom: '1px solid #F3F4F6' }}>6种</td>
              <td style={{ padding: '8px', borderBottom: '1px solid #F3F4F6', fontFamily: 'monospace', fontSize: '12px' }}>
                str. String、num. Number、bool. Boolean...
              </td>
            </tr>
            <tr>
              <td style={{ padding: '8px', borderBottom: '1px solid #F3F4F6' }}><strong>Array 类型</strong></td>
              <td style={{ padding: '8px', borderBottom: '1px solid #F3F4F6' }}>6种</td>
              <td style={{ padding: '8px', borderBottom: '1px solid #F3F4F6', fontFamily: 'monospace', fontSize: '12px' }}>
                arr[str]. Array&lt;String&gt;、arr[obj]. Array&lt;Object&gt;
              </td>
            </tr>
            <tr>
              <td style={{ padding: '8px' }}><strong>File 类型</strong></td>
              <td style={{ padding: '8px' }}>13种</td>
              <td style={{ padding: '8px', fontFamily: 'monospace', fontSize: '12px' }}>
                file[img]. File&lt;Image&gt;、file[doc]. File&lt;Doc&gt;...
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default VariableTypeSelectorExample;
