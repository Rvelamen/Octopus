/**
 * 读取文件节点配置面板
 * 支持 textarea 多行 URL 输入，一次性下载
 */

import React, { useCallback, useState } from 'react';
import { Info, Link2 } from 'lucide-react';
import { Collapse, Tooltip, Switch, Select, Input } from 'antd';
import { useWorkflowStore } from '../../../hooks/useWorkflowStore';

const { TextArea } = Input;

const NodeConfigDrawer = ({
  nodes,
  edges,
  currentNodeId,
  nodeData,
}) => {
  const [activeKey, setActiveKey] = useState(['urls', 'options', 'output']);
  const updateNode = useWorkflowStore((state) => state.updateNode);

  const config = nodeData || {};

  const handleUpdate = useCallback((updates) => {
    updateNode(currentNodeId, { ...config, ...updates });
  }, [currentNodeId, config, updateNode]);

  const fileUrlList = config.fileUrlList || '';
  const encoding = config.encoding || 'utf-8';
  const maxFileSize = config.maxFileSize ?? 10;
  const concatContent = config.concatContent ?? true;
  const separator = config.separator || '\n\n--- 文件分隔 ---\n\n';
  const outputs = config.outputs || [];

  const urlCount = (typeof fileUrlList === 'string'
    ? fileUrlList.split('\n').filter(u => u.trim()).length
    : 0);

  const collapseItems = [
    {
      key: 'urls',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Link2 size={14} color="#eab308" />
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              文件 URL
            </span>
            <Tooltip title="每行输入一个 URL，支持 http:// 或 https://">
              <Info size={14} color="#9ca3af" style={{ cursor: 'pointer' }} />
            </Tooltip>
          </div>
          {urlCount > 0 && (
            <span style={{
              fontSize: '11px',
              color: '#eab308',
              background: '#fef3c7',
              padding: '1px 8px',
              borderRadius: '10px',
              fontWeight: 500,
            }}>
              {urlCount} 个
            </span>
          )}
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <div style={{
              fontSize: '12px',
              color: '#6b7280',
              marginBottom: '6px',
            }}>
              URL 列表（每行一个）
            </div>
            <TextArea
              value={typeof fileUrlList === 'string' ? fileUrlList : ''}
              onChange={(e) => handleUpdate({ fileUrlList: e.target.value })}
              placeholder={"https://example.com/file1.txt\nhttps://example.com/file2.txt"}
              rows={6}
              style={{
                fontSize: '13px',
                fontFamily: 'monospace',
                borderRadius: '8px',
              }}
            />
          </div>
          <div style={{
            fontSize: '11px',
            color: '#9ca3af',
            background: '#f9fafb',
            padding: '8px 10px',
            borderRadius: '6px',
            lineHeight: 1.5,
          }}>
            提示：也可以输入变量引用如 {'{{'}nodeId.output{'}}'}，运行时会被解析为 URL 列表
          </div>
        </div>
      ),
    },
    {
      key: 'options',
      label: (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              读取选项
            </span>
          </div>
        </div>
      ),
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* 编码 */}
          <div>
            <div style={{
              fontSize: '12px',
              color: '#6b7280',
              marginBottom: '6px',
            }}>
              文件编码
            </div>
            <Select
              value={encoding}
              onChange={(v) => handleUpdate({ encoding: v })}
              style={{ width: '100%' }}
              options={[
                { value: 'utf-8', label: 'UTF-8' },
                { value: 'gbk', label: 'GBK' },
                { value: 'gb2312', label: 'GB2312' },
                { value: 'auto', label: '自动检测' },
              ]}
            />
          </div>

          {/* 最大文件大小 */}
          <div>
            <div style={{
              fontSize: '12px',
              color: '#6b7280',
              marginBottom: '6px',
            }}>
              最大文件大小（MB）
            </div>
            <Input
              type="number"
              min={0.1}
              max={100}
              step={0.1}
              value={maxFileSize}
              onChange={(e) => handleUpdate({ maxFileSize: parseFloat(e.target.value) || 10 })}
              style={{ borderRadius: '8px' }}
            />
          </div>

          {/* 合并内容 */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 500, color: '#374151' }}>
                合并内容
              </div>
              <div style={{ fontSize: '11px', color: '#9ca3af' }}>
                将多个文件内容合并为一个输出
              </div>
            </div>
            <Switch
              checked={concatContent}
              onChange={(v) => handleUpdate({ concatContent: v })}
            />
          </div>

          {/* 分隔符 */}
          {concatContent && (
            <div>
              <div style={{
                fontSize: '12px',
                color: '#6b7280',
                marginBottom: '6px',
              }}>
                内容分隔符
              </div>
              <TextArea
                value={separator}
                onChange={(e) => handleUpdate({ separator: e.target.value })}
                rows={2}
                style={{
                  fontSize: '13px',
                  borderRadius: '8px',
                  fontFamily: 'monospace',
                }}
              />
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
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              输出
            </span>
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
                {output.name || output.key || 'output'}
              </span>
              <span style={{
                fontSize: '11px',
                color: '#9ca3af',
                marginLeft: 'auto',
              }}>
                {output.type || 'string'}
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
