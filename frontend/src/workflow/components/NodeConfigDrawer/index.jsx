import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  X,
  Save,
  Trash2,
  AlertCircle,
  Play,
} from 'lucide-react';
import { useWorkflowStore } from '../../hooks/useWorkflowStore';
import { createNodeConfigValidator } from '../../utils/validators';
import { NODE_TYPE_INFO, DEFAULT_NODE_TYPE_INFO } from '../../constants/nodeTypes';
import ConfirmDialog from '../common/ConfirmDialog';

import WorkflowStartForm from '../nodes/WorkflowStart/NodeConfigDrawer.jsx';
import WorkflowEndForm from '../nodes/WorkflowEnd/NodeConfigDrawer.jsx';
import CodeNodeForm from '../nodes/CodeNode/NodeConfigDrawer.jsx';
import SelectorNodeForm from '../nodes/SelectorNode/NodeConfigDrawer.jsx';
import LoopNodeForm from '../nodes/LoopNode/NodeConfigDrawer.jsx';
import InputNodeForm from '../nodes/InputNode/NodeConfigDrawer.jsx';
import OutputNodeForm from '../nodes/OutputNode/NodeConfigDrawer.jsx';
import LLMNodeForm from '../nodes/LLMNode/NodeConfigDrawer.jsx';
import HTTPNodeForm from '../nodes/HTTPNode/NodeConfigDrawer.jsx';
import TextNodeForm from '../nodes/TextNode/NodeConfigDrawer.jsx';
import JSONSerializeNodeForm from '../nodes/JSONSerializeNode/NodeConfigDrawer.jsx';
import JSONDeserializeNodeForm from '../nodes/JSONDeserializeNode/NodeConfigDrawer.jsx';
import ExpressionEditorField from '../common/ExpressionEditorField/index.jsx';

const NodeConfigDrawer = ({ isOpen, onClose }) => {
  const selectedNodeId = useWorkflowStore((state) => state.selectedNodeId);
  const selectedLoopChildNodeId = useWorkflowStore((state) => state.selectedLoopChildNodeId);
  const selectedLoopChildParentId = useWorkflowStore((state) => state.selectedLoopChildParentId);
  const nodes = useWorkflowStore((state) => state.nodes);
  const edges = useWorkflowStore((state) => state.edges);
  const updateNode = useWorkflowStore((state) => state.updateNode);
  const updateLoopChildNodeData = useWorkflowStore((state) => state.updateLoopChildNodeData);
  const getSelectedChildNode = useWorkflowStore((state) => state.getSelectedChildNode);
  const selectLoopChildNode = useWorkflowStore((state) => state.selectLoopChildNode);
  const removeNode = useWorkflowStore((state) => state.removeNode);
  const selectNode = useWorkflowStore((state) => state.selectNode);
  const moveNodeOutOfLoop = useWorkflowStore((state) => state.moveNodeOutOfLoop);
  const executionStatus = useWorkflowStore((state) => state.executionStatus);

  const [formValues, setFormValues] = useState({});
  const [errors, setErrors] = useState({});
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const setTestResultOpen = useWorkflowStore((state) => state.setTestResultOpen);

  // 判断是否正在编辑循环体内的子节点
  const isEditingChildNode = !!selectedLoopChildNodeId;

  const selectedNode = useMemo(() => {
    if (isEditingChildNode) {
      return getSelectedChildNode();
    }
    return nodes.find((n) => n.id === selectedNodeId);
  }, [nodes, selectedNodeId, isEditingChildNode, getSelectedChildNode]);

  const nodeExecution = selectedNodeId ? executionStatus[selectedNodeId] : null;

  const nodeType = useMemo(() => {
    return selectedNode?.data?.flowNodeType || selectedNode?.type;
  }, [selectedNode]);

  const nodeTypeInfo = useMemo(() => {
    return NODE_TYPE_INFO[nodeType] || DEFAULT_NODE_TYPE_INFO;
  }, [nodeType]);

  useEffect(() => {
    if (selectedNode?.data) {
      const values = {};
      const inputs = selectedNode.data.inputs || [];
      inputs.forEach((input) => {
        values[input.key] = selectedNode.data[input.key] !== undefined
          ? selectedNode.data[input.key]
          : input.value !== undefined
            ? input.value
            : input.defaultValue;
      });
      setFormValues(values);
      setErrors({});
    }
  }, [selectedNodeId]);

  const handleFormChange = useCallback((newValues) => {
    setFormValues(newValues);
    const newErrors = { ...errors };
    Object.keys(newValues).forEach((key) => {
      if (newErrors[key]) delete newErrors[key];
    });
    setErrors(newErrors);

    if (selectedNode) {
      const newData = { ...selectedNode.data, ...newValues };
      if (isEditingChildNode && selectedLoopChildParentId) {
        updateLoopChildNodeData(selectedLoopChildParentId, selectedNode.id, newData);
      } else {
        updateNode(selectedNode.id, newData);
      }
    }
  }, [errors, selectedNode, updateNode, isEditingChildNode, selectedLoopChildParentId, updateLoopChildNodeData]);

  const validateForm = useCallback(() => {
    const inputs = selectedNode?.data?.inputs || [];
    const validator = createNodeConfigValidator(nodeType, { inputs });
    const result = validator.validate(formValues);
    setErrors(result.errors);
    return result.valid;
  }, [selectedNode, nodeType, formValues]);

  const handleSave = useCallback(() => {
    if (!validateForm()) return;
    if (!selectedNode) return;

    // selectedNode.data may have been updated directly by node-specific forms
    // (e.g. LLMNodeForm uses updateNode directly), so it should take precedence
    // over the stale formValues to avoid overwriting user changes.
    const newData = {
      ...formValues,
      ...selectedNode.data,
    };

    if (isEditingChildNode && selectedLoopChildParentId) {
      updateLoopChildNodeData(selectedLoopChildParentId, selectedNode.id, newData);
    } else {
      updateNode(selectedNode.id, newData);
    }
    onClose?.();
  }, [validateForm, selectedNode, formValues, updateNode, updateLoopChildNodeData, isEditingChildNode, selectedLoopChildParentId, onClose]);

  const handleDelete = useCallback(() => {
    if (!selectedNode) return;
    if (selectedNode.data?.forbidDelete) return;
    setShowDeleteConfirm(true);
  }, [selectedNode]);

  const handleDeleteConfirmed = useCallback(() => {
    if (isEditingChildNode && selectedLoopChildParentId) {
      moveNodeOutOfLoop(selectedNode.id, selectedLoopChildParentId);
      selectLoopChildNode(null, null);
    } else {
      removeNode(selectedNode.id);
    }
    selectNode(null);
    setShowDeleteConfirm(false);
    onClose?.();
  }, [selectedNode, removeNode, selectNode, onClose, isEditingChildNode, selectedLoopChildParentId, moveNodeOutOfLoop, selectLoopChildNode]);

  const handleUpdateNodeName = useCallback((newName) => {
    if (!selectedNode) return;
    if (isEditingChildNode && selectedLoopChildParentId) {
      updateLoopChildNodeData(selectedLoopChildParentId, selectedNode.id, { ...selectedNode.data, name: newName });
    } else {
      updateNode(selectedNode.id, { ...selectedNode.data, name: newName });
    }
  }, [selectedNode, updateNode, isEditingChildNode, selectedLoopChildParentId, updateLoopChildNodeData]);

  const handleUpdateNodeIntro = useCallback((newIntro) => {
    if (!selectedNode) return;
    if (isEditingChildNode && selectedLoopChildParentId) {
      updateLoopChildNodeData(selectedLoopChildParentId, selectedNode.id, { ...selectedNode.data, intro: newIntro });
    } else {
      updateNode(selectedNode.id, { ...selectedNode.data, intro: newIntro });
    }
  }, [selectedNode, updateNode, isEditingChildNode, selectedLoopChildParentId, updateLoopChildNodeData]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      onClose?.();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      handleSave();
    }
  }, [onClose, handleSave]);

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleKeyDown]);

  const renderNodeForm = () => {
    const formProps = {
      values: formValues,
      onChange: handleFormChange,
      errors,
      nodes,
      edges,
      currentNodeId: selectedNodeId,
      nodeData: selectedNode?.data,
    };

    switch (nodeType) {
      case 'workflowStart':
        return <WorkflowStartForm {...formProps} />;
      case 'workflowEnd':
        return <WorkflowEndForm {...formProps} />;
      case 'code':
        return <CodeNodeForm {...formProps} />;
      case 'ifElseNode':
        return <SelectorNodeForm {...formProps} />;
      case 'loop':
        return <LoopNodeForm {...formProps} />;
      case 'inputNode':
        return <InputNodeForm {...formProps} />;
      case 'pluginOutput':
        return <OutputNodeForm {...formProps} />;
      case 'llm':
      case 'chatNode':
        return <LLMNodeForm {...formProps} />;
      case 'http':
        return <HTTPNodeForm {...formProps} />;
      case 'textEditor':
        return <TextNodeForm {...formProps} />;
      case 'jsonSerialize':
        return <JSONSerializeNodeForm {...formProps} />;
      case 'jsonDeserialize':
        return <JSONDeserializeNodeForm {...formProps} />;
      default:
        return null;
    }
  };

  if (!isOpen || !selectedNode) return null;

  const nodeData = selectedNode.data || {};
  const inputs = nodeData.inputs || [];

  return (
    <div
      style={{
        position: 'fixed',
        right: 0,
        top: 0,
        bottom: 0,
        width: '480px',
        maxWidth: '100vw',
        background: 'white',
        borderLeft: '1px solid #e5e7eb',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        animation: 'slideInRight 0.2s ease-out',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '12px 16px',
          borderBottom: '1px solid #f3f4f6',
          background: '#fafafa',
        }}
      >
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: `${nodeTypeInfo.color}15`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '18px',
            marginRight: '12px',
          }}
        >
          {nodeTypeInfo.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <input
            value={nodeData.name || ''}
            onChange={(e) => handleUpdateNodeName(e.target.value)}
            placeholder="节点名称"
            style={{
              fontSize: '15px',
              fontWeight: 600,
              border: 'none',
              background: 'transparent',
              outline: 'none',
              width: '100%',
              color: '#1f2937',
            }}
          />
          <div style={{ fontSize: '12px', color: '#6b7280' }}>
            {nodeTypeInfo.category} · {nodeTypeInfo.name}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {!nodeData.forbidDelete && (
            <button
              style={{
                padding: '6px',
                borderRadius: '6px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                color: '#9ca3af',
                display: 'flex',
                alignItems: 'center',
              }}
              onClick={handleDelete}
              title="删除节点"
            >
              <Trash2 size={16} />
            </button>
          )}
          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              borderRadius: '6px',
              border: 'none',
              background: '#3b82f6',
              color: 'white',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 500,
            }}
            onClick={handleSave}
          >
            <Save size={14} />
            保存
          </button>
          <button
            style={{
              padding: '6px',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
            onClick={onClose}
          >
            <X size={18} color="#6b7280" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          padding: '16px',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Description */}
          <div>
            <label style={{
              display: 'block',
              fontSize: '13px',
              fontWeight: 500,
              color: '#374151',
              marginBottom: '6px',
            }}>
              节点描述
            </label>
            <textarea
              value={nodeData.intro || ''}
              onChange={(e) => handleUpdateNodeIntro(e.target.value)}
              placeholder="描述此节点的功能..."
              rows={2}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                fontSize: '13px',
                resize: 'vertical',
                outline: 'none',
                background: '#fafafa',
              }}
            />
          </div>

          {/* Node Form */}
          {renderNodeForm()}


        </div>
      </div>

      {/* Footer */}
      {nodeExecution?.status ? (
        <div
          onClick={() => setTestResultOpen(true)}
          style={{
            padding: '10px 16px',
            borderTop: '1px solid #e5e7eb',
            background: '#6366f1',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'white', fontSize: '13px', fontWeight: 500 }}>
            <Play size={14} fill="white" />
            查看试运行结果
          </div>
          <X size={16} color="white" />
        </div>
      ) : (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 16px',
            borderTop: '1px solid #f3f4f6',
            background: '#fafafa',
          }}
        >
          <div style={{ fontSize: '12px', color: '#9ca3af' }}>
            按 <kbd style={{
              padding: '2px 6px',
              background: '#e5e7eb',
              borderRadius: '4px',
              fontSize: '11px',
            }}>Esc</kbd> 关闭 · <kbd style={{
              padding: '2px 6px',
              background: '#e5e7eb',
              borderRadius: '4px',
              fontSize: '11px',
            }}>Ctrl+S</kbd> 保存
          </div>
          {Object.keys(errors).length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#ef4444', fontSize: '12px' }}>
              <AlertCircle size={14} />
              请检查表单错误
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes slideInRight {
          from {
            transform: translateX(100%);
          }
          to {
            transform: translateX(0);
          }
        }
      `}</style>
      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleDeleteConfirmed}
        title="删除节点"
        message="确定要删除这个节点吗？此操作不可恢复。"
        confirmText="删除"
        cancelText="取消"
        variant="danger"
      />
    </div>
  );
};

export default NodeConfigDrawer;
