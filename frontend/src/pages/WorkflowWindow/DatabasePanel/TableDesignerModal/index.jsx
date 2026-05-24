import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Button, Select, Switch, Space, Divider } from 'antd';
import { Plus, Trash2 } from 'lucide-react';

const FIELD_TYPES = [
  { value: 'string', label: '文本 (String)' },
  { value: 'integer', label: '整数 (Integer)' },
  { value: 'decimal', label: '小数 (Decimal)' },
  { value: 'boolean', label: '布尔 (Boolean)' },
  { value: 'datetime', label: '日期时间 (DateTime)' },
  { value: 'json', label: 'JSON' },
];

export default function TableDesignerModal({ open, onClose, onSubmit, initialValues }) {
  const [form] = Form.useForm();
  const [fields, setFields] = useState([]);
  const isEdit = !!initialValues;

  useEffect(() => {
    if (open) {
      if (initialValues) {
        form.setFieldsValue({
          name: initialValues.name,
          description: initialValues.description,
        });
        setFields(initialValues.fields || []);
      } else {
        form.resetFields();
        setFields([
          { name: 'id', type: 'string', required: true },
          { name: 'name', type: 'string', required: true },
        ]);
      }
    }
  }, [open, initialValues, form]);

  const handleAddField = () => {
    setFields([...fields, { name: '', type: 'string', required: false }]);
  };

  const handleRemoveField = (index) => {
    setFields(fields.filter((_, i) => i !== index));
  };

  const handleFieldChange = (index, key, value) => {
    const newFields = [...fields];
    newFields[index] = { ...newFields[index], [key]: value };
    // Auto-set type to integer when enabling autoIncrement
    if (key === 'autoIncrement' && value === true) {
      newFields[index].type = 'integer';
    }
    setFields(newFields);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      // Validate fields
      const validFields = fields.filter((f) => f.name.trim());
      if (validFields.length === 0) {
        throw new Error('至少需要一个字段');
      }
      const names = validFields.map((f) => f.name.trim());
      if (new Set(names).size !== names.length) {
        throw new Error('字段名不能重复');
      }
      onSubmit({
        ...values,
        fields: validFields,
      });
    } catch (err) {
      if (err.errorFields) return;
      // message.error(err.message);
    }
  };

  return (
    <Modal
      title={isEdit ? '编辑表结构' : '新建数据表'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      width={640}
      okText={isEdit ? '保存' : '创建'}
      cancelText="取消"
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label="表名"
          rules={[{ required: true, message: '请输入表名' }]}
        >
          <Input placeholder="例如：customers" disabled={isEdit} />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} placeholder="可选，简要描述该表的用途" />
        </Form.Item>
      </Form>

      <Divider style={{ margin: '16px 0' }} />

      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 500 }}>字段定义</span>
        <Button size="small" icon={<Plus size={14} />} onClick={handleAddField}>
          添加字段
        </Button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {fields.map((field, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: 8,
              background: '#f9fafb',
              borderRadius: 6,
              border: '1px solid #e5e7eb',
            }}
          >
            <Input
              placeholder="字段名"
              value={field.name}
              onChange={(e) => handleFieldChange(index, 'name', e.target.value)}
              style={{ width: 140 }}
              size="small"
            />
            <Select
              value={field.type}
              onChange={(value) => handleFieldChange(index, 'type', value)}
              options={FIELD_TYPES}
              style={{ width: 160 }}
              size="small"
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#4b5563' }}>
              <Switch
                size="small"
                checked={field.required}
                onChange={(checked) => handleFieldChange(index, 'required', checked)}
              />
              必填
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#4b5563' }}>
              <Switch
                size="small"
                checked={field.autoIncrement}
                onChange={(checked) => handleFieldChange(index, 'autoIncrement', checked)}
              />
              自增
            </div>
            <Input
              placeholder="默认值（可选）"
              value={field.default || ''}
              onChange={(e) => handleFieldChange(index, 'default', e.target.value)}
              style={{ flex: 1 }}
              size="small"
            />
            <Button
              size="small"
              danger
              type="text"
              icon={<Trash2 size={14} />}
              onClick={() => handleRemoveField(index)}
            />
          </div>
        ))}
        {fields.length === 0 && (
          <div style={{ textAlign: 'center', color: '#9ca3af', padding: 16 }}>
            点击上方按钮添加字段
          </div>
        )}
      </div>
    </Modal>
  );
}
