import React, { useMemo } from 'react';
import { Cascader } from 'antd';
import './VariableTypeSelector.css';

const VARIABLE_TYPE_OPTIONS = [
  {
    value: 'String',
    label: 'String',
    abbr: 'str',
  },
  {
    value: 'Integer',
    label: 'Integer',
    abbr: 'int',
  },
  {
    value: 'Number',
    label: 'Number',
    abbr: 'num',
  },
  {
    value: 'Boolean',
    label: 'Boolean',
    abbr: 'bool',
  },
  {
    value: 'Time',
    label: 'Time',
    abbr: 'time',
  },
  {
    value: 'Object',
    label: 'Object',
    abbr: 'obj',
  },
  {
    value: 'Array',
    label: 'Array',
    abbr: 'arr',
    children: [
      { value: 'String', label: 'String', abbr: 'str' },
      { value: 'Integer', label: 'Integer', abbr: 'int' },
      { value: 'Number', label: 'Number', abbr: 'num' },
      { value: 'Boolean', label: 'Boolean', abbr: 'bool' },
      { value: 'Time', label: 'Time', abbr: 'time' },
      { value: 'Object', label: 'Object', abbr: 'obj' },
    ],
  },
  {
    value: 'File',
    label: 'File',
    abbr: 'file',
    children: [
      { value: 'Default', label: 'Default', abbr: '' },
      { value: 'Image', label: 'Image', abbr: 'img' },
      { value: 'Svg', label: 'Svg', abbr: 'svg' },
      { value: 'Audio', label: 'Audio', abbr: 'audio' },
      { value: 'Video', label: 'Video', abbr: 'video' },
      { value: 'Voice', label: 'Voice', abbr: 'voice' },
      { value: 'Doc', label: 'Doc', abbr: 'doc' },
      { value: 'PPT', label: 'PPT', abbr: 'ppt' },
      { value: 'Excel', label: 'Excel', abbr: 'xls' },
      { value: 'Txt', label: 'Txt', abbr: 'txt' },
      { value: 'Code', label: 'Code', abbr: 'code' },
      { value: 'Zip', label: 'Zip', abbr: 'zip' },
    ],
  },
];

function formatDisplayValue(selectedOptions) {
  if (!selectedOptions || selectedOptions.length === 0) return '';

  const firstOption = selectedOptions[0];
  if (!firstOption) return '';

  if (selectedOptions.length === 1) {
    return (
      <span className="type-display">
        <span className="type-abbr">{firstOption.abbr || ''}</span>
        <span className="type-separator">. </span>
        <span className="type-full">{firstOption.label || ''}</span>
      </span>
    );
  }

  if (selectedOptions.length === 2) {
    const parent = selectedOptions[0];
    const child = selectedOptions[1];

    if (!parent || !child) return '';

    if (parent.value === 'File' && child.value === 'Default') {
      return (
        <span className="type-display">
          <span className="type-abbr">{parent.abbr || ''}</span>
          <span className="type-separator">. </span>
          <span className="type-full">{parent.label || ''}</span>
        </span>
      );
    }

    const childAbbr = child.abbr || child.label?.toLowerCase() || '';
    return (
      <span className="type-display">
        <span className="type-abbr">{(parent.abbr || '')}[{childAbbr}]</span>
        <span className="type-separator">. </span>
        <span className="type-full">{parent.value || ''}&lt;{child.label || ''}&gt;</span>
      </span>
    );
  }

  return '';
}

function VariableTypeSelector({
  value,
  onChange,
  placeholder = '请选择变量类型',
  disabled = false,
  size = 'middle',
  style = {},
  className = '',
  allowClear = true,
}) {
  const displayValue = useMemo(() => {
    if (!value) return [];

    if (value.includes('<')) {
      const match = value.match(/(\w+)<(.+)>/);
      if (match) {
        const [, parent, child] = match;
        return [parent, child];
      }
    }

    return [value];
  }, [value]);

  const handleChange = (selectedValue, selectedOptions) => {
    if (!selectedValue || selectedValue.length === 0) {
      onChange?.(undefined);
      return;
    }

    if (selectedValue.length === 1) {
      onChange?.(selectedValue[0]);
    } else if (selectedValue.length === 2) {
      const parent = selectedValue[0];
      const child = selectedValue[1];

      if (parent === 'File' && child === 'Default') {
        onChange?.('File');
      } else {
        onChange?.(`${parent}<${child}>`);
      }
    }
  };

  return (
    <Cascader
      options={VARIABLE_TYPE_OPTIONS}
      value={displayValue}
      onChange={handleChange}
      placeholder={placeholder}
      disabled={disabled}
      size={size}
      style={{ width: '100%', ...style }}
      className={`variable-type-selector ${className}`}
      allowClear={allowClear}
      changeOnSelect
      expandTrigger="hover"
      displayRender={(labels, selectedOptions) => [
        formatDisplayValue(selectedOptions),
      ]}
      dropdownStyle={{ maxHeight: 'none', overflow: 'visible' }}
      dropdownMenuColumnStyle={{ maxHeight: 'none', height: 'auto', overflow: 'visible' }}
      dropdownClassName="variable-type-selector-dropdown"
      showSearch={{
        filter: (inputValue, path) =>
          path.some((option) =>
            option.label.toLowerCase().includes(inputValue.toLowerCase())
          ),
      }}
    />
  );
}

export default VariableTypeSelector;

export { VARIABLE_TYPE_OPTIONS };
