import React, { useEffect } from 'react';
import { Modal, Form, Input, InputNumber, Switch, DatePicker } from 'antd';
import dayjs from 'dayjs';

const TYPE_COMPONENTS = {
  string: ({ value, onChange }) => (
    <Input value={value} onChange={(e) => onChange(e.target.value)} />
  ),
  integer: ({ value, onChange }) => (
    <InputNumber value={value} onChange={onChange} style={{ width: '100%' }} precision={0} />
  ),
  decimal: ({ value, onChange }) => (
    <InputNumber value={value} onChange={onChange} style={{ width: '100%' }} />
  ),
  boolean: ({ value, onChange }) => (
    <Switch checked={!!value} onChange={onChange} />
  ),
  datetime: ({ value, onChange }) => (
    <DatePicker
      showTime
      value={value ? dayjs(value) : null}
      onChange={(date) => onChange(date ? date.toISOString() : null)}
      style={{ width: '100%' }}
    />
  ),
  json: ({ value, onChange }) => {
    const text = typeof value === 'object' ? JSON.stringify(value, null, 2) : value;
    return (
      <Input.TextArea
        value={text}
        onChange={(e) => {
          try {
            const parsed = JSON.parse(e.target.value);
            onChange(parsed);
          } catch {
            onChange(e.target.value);
          }
        }}
        rows={4}
        placeholder='{"key": "value"}'
      />
    );
  },
};

export default function RecordFormModal({ open, onClose, onSubmit, fields, initialValues }) {
  const [form] = Form.useForm();
  const isEdit = !!initialValues;

  useEffect(() => {
    if (open) {
      if (initialValues) {
        // Convert values for form
        const formValues = {};
        fields.forEach((field) => {
          const value = initialValues[field.name];
          if (field.type === 'datetime' && value) {
            formValues[field.name] = dayjs(value);
          } else {
            formValues[field.name] = value;
          }
        });
        form.setFieldsValue(formValues);
      } else {
        const defaults = {};
        fields.forEach((field) => {
          if (field.type === 'boolean') {
            defaults[field.name] = field.default === 'true' || field.default === true;
          } else if (field.type === 'integer' || field.type === 'decimal') {
            defaults[field.name] = field.default ? Number(field.default) : undefined;
          } else {
            defaults[field.name] = field.default || undefined;
          }
        });
        form.setFieldsValue(defaults);
      }
    }
  }, [open, initialValues, fields, form]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      // Convert dayjs to ISO string for datetime
      const result = {};
      fields.forEach((field) => {
        // Skip auto-increment fields on create
        if (!isEdit && field.autoIncrement) {
          return;
        }
        const value = values[field.name];
        if (field.type === 'datetime' && value && typeof value.toISOString === 'function') {
          result[field.name] = value.toISOString();
        } else if (field.type === 'json' && typeof value === 'string') {
          try {
            result[field.name] = JSON.parse(value);
          } catch {
            result[field.name] = value;
          }
        } else {
          result[field.name] = value;
        }
      });
      onSubmit(result);
    } catch {
      // validation error
    }
  };

  return (
    <Modal
      title={isEdit ? '编辑记录' : '新增记录'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      width={520}
      okText={isEdit ? '保存' : '添加'}
      cancelText="取消"
    >
      <Form form={form} layout="vertical">
        {fields.map((field) => {
          const Component = TYPE_COMPONENTS[field.type] || TYPE_COMPONENTS.string;
          const isAutoIncrement = field.autoIncrement;
          return (
            <Form.Item
              key={field.name}
              name={field.name}
              label={
                <span>
                  {field.name}
                  {field.required && <span style={{ color: '#ef4444', marginLeft: 4 }}>*</span>}
                  {isAutoIncrement && (
                    <span style={{ color: '#f59e0b', marginLeft: 4, fontSize: 11 }}>(自增)</span>
                  )}
                </span>
              }
              rules={
                !isAutoIncrement && field.required
                  ? [{ required: true, message: `请输入 ${field.name}` }]
                  : undefined
              }
              valuePropName={field.type === 'boolean' ? 'checked' : 'value'}
            >
              {isAutoIncrement ? (
                <Input
                  disabled
                  placeholder={isEdit ? String(initialValues?.[field.name] ?? '') : '系统自动分配'}
                />
              ) : (
                <Component />
              )}
            </Form.Item>
          );
        })}]
      </Form>
    </Modal>
  );
}
