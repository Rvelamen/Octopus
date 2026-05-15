/**
 * 版本对比组件
 * 对比两个工作流版本的差异
 */

import React, { useState, useMemo } from 'react';
import {
  X,
  GitCompare,
  Plus,
  Minus,
  ArrowRight,
  AlertTriangle,
} from 'lucide-react';

const VersionCompare = ({ isOpen, onClose, versions = [] }) => {
  const [baseVersion, setBaseVersion] = useState('');
  const [compareVersion, setCompareVersion] = useState('');

  const sortedVersions = useMemo(() => {
    return [...versions].sort((a, b) => {
      const versionA = parseFloat(a.version || '0');
      const versionB = parseFloat(b.version || '0');
      return versionB - versionA;
    });
  }, [versions]);

  const baseData = useMemo(() => {
    return versions.find((v) => v.version === baseVersion);
  }, [versions, baseVersion]);

  const compareData = useMemo(() => {
    return versions.find((v) => v.version === compareVersion);
  }, [versions, compareVersion]);

  const differences = useMemo(() => {
    if (!baseData || !compareData) return [];

    const diffs = [];

    // 对比节点数量
    const baseNodes = baseData.nodes || [];
    const compareNodes = compareData.nodes || [];

    if (baseNodes.length !== compareNodes.length) {
      diffs.push({
        type: 'node_count',
        label: '节点数量',
        old: `${baseNodes.length} 个`,
        new: `${compareNodes.length} 个`,
        change: baseNodes.length < compareNodes.length ? 'added' : 'removed',
      });
    }

    // 对比节点名称
    baseNodes.forEach((baseNode) => {
      const compareNode = compareNodes.find((n) => n.id === baseNode.id);
      if (!compareNode) {
        diffs.push({
          type: 'node_removed',
          label: `节点删除: ${baseNode.data?.name || baseNode.id}`,
          old: '存在',
          new: '已删除',
          change: 'removed',
        });
      } else if (baseNode.data?.name !== compareNode.data?.name) {
        diffs.push({
          type: 'node_renamed',
          label: `节点重命名: ${baseNode.data?.name || baseNode.id}`,
          old: baseNode.data?.name || '未命名',
          new: compareNode.data?.name || '未命名',
          change: 'modified',
        });
      }
    });

    compareNodes.forEach((compareNode) => {
      const baseNode = baseNodes.find((n) => n.id === compareNode.id);
      if (!baseNode) {
        diffs.push({
          type: 'node_added',
          label: `节点新增: ${compareNode.data?.name || compareNode.id}`,
          old: '不存在',
          new: '已添加',
          change: 'added',
        });
      }
    });

    // 对比边数量
    const baseEdges = baseData.edges || [];
    const compareEdges = compareData.edges || [];

    if (baseEdges.length !== compareEdges.length) {
      diffs.push({
        type: 'edge_count',
        label: '连接数量',
        old: `${baseEdges.length} 条`,
        new: `${compareEdges.length} 条`,
        change: baseEdges.length < compareEdges.length ? 'added' : 'removed',
      });
    }

    return diffs;
  }, [baseData, compareData]);

  const getChangeIcon = (change) => {
    switch (change) {
      case 'added':
        return <Plus size={14} color="#22c55e" />;
      case 'removed':
        return <Minus size={14} color="#ef4444" />;
      case 'modified':
        return <AlertTriangle size={14} color="#f59e0b" />;
      default:
        return null;
    }
  };

  const getChangeColor = (change) => {
    switch (change) {
      case 'added':
        return '#f0fdf4';
      case 'removed':
        return '#fef2f2';
      case 'modified':
        return '#fffbeb';
      default:
        return '#f9fafb';
    }
  };

  const getChangeBorderColor = (change) => {
    switch (change) {
      case 'added':
        return '#86efac';
      case 'removed':
        return '#fca5a5';
      case 'modified':
        return '#fcd34d';
      default:
        return '#e5e7eb';
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.5)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'white',
          borderRadius: '12px',
          width: '600px',
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid #f3f4f6',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <GitCompare size={20} color="#4b5563" />
            <span style={{ fontSize: '18px', fontWeight: 600 }}>
              版本对比
            </span>
          </div>
          <button
            style={{
              padding: '4px',
              borderRadius: '4px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
            }}
            onClick={onClose}
            title="关闭"
          >
            <X size={20} />
          </button>
        </div>

        {/* 版本选择 */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid #f3f4f6',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
              基准版本
            </div>
            <select
              value={baseVersion}
              onChange={(e) => setBaseVersion(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid #e5e7eb',
                borderRadius: '6px',
                fontSize: '14px',
                background: 'white',
                outline: 'none',
              }}
            >
              <option value="">选择版本</option>
              {sortedVersions.map((v) => (
                <option key={v.version} value={v.version}>
                  v{v.version} {v.name ? `- ${v.name}` : ''}
                </option>
              ))}
            </select>
          </div>

          <div style={{ padding: '0 8px', color: '#9ca3af' }}>
            <ArrowRight size={20} />
          </div>

          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
              对比版本
            </div>
            <select
              value={compareVersion}
              onChange={(e) => setCompareVersion(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid #e5e7eb',
                borderRadius: '6px',
                fontSize: '14px',
                background: 'white',
                outline: 'none',
              }}
            >
              <option value="">选择版本</option>
              {sortedVersions.map((v) => (
                <option key={v.version} value={v.version}>
                  v{v.version} {v.name ? `- ${v.name}` : ''}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* 差异列表 */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 20px',
          }}
        >
          {!baseVersion || !compareVersion ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
              <GitCompare size={32} style={{ margin: '0 auto 12px' }} />
              <div style={{ fontSize: '14px' }}>请选择两个版本进行对比</div>
            </div>
          ) : differences.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
              <CheckCircle size={32} style={{ margin: '0 auto 12px', color: '#22c55e' }} />
              <div style={{ fontSize: '14px' }}>两个版本完全一致</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {differences.map((diff, index) => (
                <div
                  key={index}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px',
                    borderRadius: '8px',
                    background: getChangeColor(diff.change),
                    border: `1px solid ${getChangeBorderColor(diff.change)}`,
                  }}
                >
                  {getChangeIcon(diff.change)}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: '13px',
                        fontWeight: 500,
                        color: '#1f2937',
                      }}
                    >
                      {diff.label}
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginTop: '4px',
                        fontSize: '12px',
                      }}
                    >
                      <span style={{ color: '#6b7280', textDecoration: 'line-through' }}>
                        {diff.old}
                      </span>
                      <ArrowRight size={12} color="#9ca3af" />
                      <span style={{ color: '#374151', fontWeight: 500 }}>
                        {diff.new}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default VersionCompare;
