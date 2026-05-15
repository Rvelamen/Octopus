/**
 * 表单验证系统
 * 提供节点配置的验证功能
 */

/**
 * 验证结果
 */
export class ValidationResult {
  constructor(valid = true, errors = [], warnings = []) {
    this.valid = valid;
    this.errors = errors;
    this.warnings = warnings;
  }

  addError(field, message) {
    this.errors.push({ field, message });
    this.valid = false;
    return this;
  }

  addWarning(field, message) {
    this.warnings.push({ field, message });
    return this;
  }

  merge(other) {
    this.errors.push(...other.errors);
    this.warnings.push(...other.warnings);
    if (!other.valid) this.valid = false;
    return this;
  }
}

/**
 * 基础验证器
 */
export class BaseValidator {
  constructor(options = {}) {
    this.options = options;
  }

  validate(value) {
    return new ValidationResult();
  }

  required(message = '此字段为必填项') {
    this.options.required = true;
    this.options.requiredMessage = message;
    return this;
  }

  min(minValue, message) {
    this.options.min = minValue;
    this.options.minMessage = message;
    return this;
  }

  max(maxValue, message) {
    this.options.max = maxValue;
    this.options.maxMessage = message;
    return this;
  }

  pattern(regex, message) {
    this.options.pattern = regex;
    this.options.patternMessage = message;
    return this;
  }

  custom(validatorFn, message) {
    this.options.customValidator = validatorFn;
    this.options.customMessage = message;
    return this;
  }
}

/**
 * 字符串验证器
 */
export class StringValidator extends BaseValidator {
  validate(value) {
    const result = new ValidationResult();

    if (this.options.required && (value === undefined || value === null || value === '')) {
      return result.addError('value', this.options.requiredMessage || '此字段为必填项');
    }

    if (value === undefined || value === null || value === '') {
      return result;
    }

    if (typeof value !== 'string') {
      return result.addError('value', '必须是字符串类型');
    }

    if (this.options.minLength !== undefined && value.length < this.options.minLength) {
      result.addError('value', this.options.minLengthMessage || `长度不能少于 ${this.options.minLength} 个字符`);
    }

    if (this.options.maxLength !== undefined && value.length > this.options.maxLength) {
      result.addError('value', this.options.maxLengthMessage || `长度不能超过 ${this.options.maxLength} 个字符`);
    }

    if (this.options.pattern && !this.options.pattern.test(value)) {
      result.addError('value', this.options.patternMessage || '格式不正确');
    }

    if (this.options.customValidator) {
      const customResult = this.options.customValidator(value);
      if (customResult !== true) {
        result.addError('value', customResult || this.options.customMessage || '验证失败');
      }
    }

    return result;
  }

  minLength(length, message) {
    this.options.minLength = length;
    this.options.minLengthMessage = message;
    return this;
  }

  maxLength(length, message) {
    this.options.maxLength = length;
    this.options.maxLengthMessage = message;
    return this;
  }

  email(message = '请输入有效的邮箱地址') {
    this.options.pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    this.options.patternMessage = message;
    return this;
  }

  url(message = '请输入有效的 URL') {
    this.options.pattern = /^https?:\/\/.+/;
    this.options.patternMessage = message;
    return this;
  }
}

/**
 * 数字验证器
 */
export class NumberValidator extends BaseValidator {
  validate(value) {
    const result = new ValidationResult();

    if (this.options.required && (value === undefined || value === null || value === '')) {
      return result.addError('value', this.options.requiredMessage || '此字段为必填项');
    }

    if (value === undefined || value === null || value === '') {
      return result;
    }

    const numValue = Number(value);
    if (isNaN(numValue)) {
      return result.addError('value', '必须是有效的数字');
    }

    if (this.options.min !== undefined && numValue < this.options.min) {
      result.addError('value', this.options.minMessage || `不能小于 ${this.options.min}`);
    }

    if (this.options.max !== undefined && numValue > this.options.max) {
      result.addError('value', this.options.maxMessage || `不能大于 ${this.options.max}`);
    }

    if (this.options.integer && !Number.isInteger(numValue)) {
      result.addError('value', '必须是整数');
    }

    if (this.options.positive && numValue <= 0) {
      result.addError('value', '必须是正数');
    }

    if (this.options.customValidator) {
      const customResult = this.options.customValidator(numValue);
      if (customResult !== true) {
        result.addError('value', customResult || this.options.customMessage || '验证失败');
      }
    }

    return result;
  }

  integer(message = '必须是整数') {
    this.options.integer = true;
    this.options.integerMessage = message;
    return this;
  }

  positive(message = '必须是正数') {
    this.options.positive = true;
    this.options.positiveMessage = message;
    return this;
  }
}

/**
 * JSON 验证器
 */
export class JSONValidator extends BaseValidator {
  validate(value) {
    const result = new ValidationResult();

    if (this.options.required && (value === undefined || value === null || value === '')) {
      return result.addError('value', this.options.requiredMessage || '此字段为必填项');
    }

    if (value === undefined || value === null || value === '') {
      return result;
    }

    try {
      const parsed = typeof value === 'string' ? JSON.parse(value) : value;
      
      if (this.options.schema) {
        const schemaResult = this.validateSchema(parsed);
        result.merge(schemaResult);
      }

      if (this.options.customValidator) {
        const customResult = this.options.customValidator(parsed);
        if (customResult !== true) {
          result.addError('value', customResult || this.options.customMessage || '验证失败');
        }
      }
    } catch (e) {
      result.addError('value', `JSON 解析错误: ${e.message}`);
    }

    return result;
  }

  validateSchema(value) {
    const result = new ValidationResult();
    return result;
  }

  schema(schemaDef) {
    this.options.schema = schemaDef;
    return this;
  }
}

/**
 * 代码验证器
 */
export class CodeValidator extends BaseValidator {
  constructor(language = 'python') {
    super();
    this.options.language = language;
  }

  validate(value) {
    const result = new ValidationResult();

    if (this.options.required && (value === undefined || value === null || value === '')) {
      return result.addError('value', this.options.requiredMessage || '此字段为必填项');
    }

    if (value === undefined || value === null || value === '') {
      return result;
    }

    if (typeof value !== 'string') {
      return result.addError('value', '代码必须是字符串');
    }

    if (this.options.language === 'python') {
      const pythonResult = this.validatePython(value);
      result.merge(pythonResult);
    }

    if (this.options.customValidator) {
      const customResult = this.options.customValidator(value);
      if (customResult !== true) {
        result.addError('value', customResult || this.options.customMessage || '验证失败');
      }
    }

    return result;
  }

  validatePython(code) {
    const result = new ValidationResult();
    
    const lines = code.split('\n');
    let hasMainFunction = false;
    
    for (const line of lines) {
      if (line.trim().startsWith('def main(')) {
        hasMainFunction = true;
        break;
      }
    }

    if (!hasMainFunction) {
      result.addWarning('value', '建议定义 main 函数作为入口');
    }

    return result;
  }
}

/**
 * HTTP URL 验证器
 */
export class HttpUrlValidator extends StringValidator {
  validate(value) {
    const result = super.validate(value);

    if (value && !/^https?:\/\/.+/.test(value)) {
      result.addError('value', '请输入有效的 HTTP/HTTPS URL');
    }

    return result;
  }
}

/**
 * 数组验证器
 */
export class ArrayValidator extends BaseValidator {
  constructor(itemValidator) {
    super();
    this.itemValidator = itemValidator;
  }

  validate(value) {
    const result = new ValidationResult();

    if (this.options.required && (!value || value.length === 0)) {
      return result.addError('value', this.options.requiredMessage || '此字段为必填项');
    }

    if (!value) {
      return result;
    }

    if (!Array.isArray(value)) {
      return result.addError('value', '必须是数组类型');
    }

    if (this.options.minLength !== undefined && value.length < this.options.minLength) {
      result.addError('value', `至少需要 ${this.options.minLength} 项`);
    }

    if (this.options.maxLength !== undefined && value.length > this.options.maxLength) {
      result.addError('value', `最多只能有 ${this.options.maxLength} 项`);
    }

    if (this.itemValidator) {
      value.forEach((item, index) => {
        const itemResult = this.itemValidator.validate(item);
        itemResult.errors.forEach((err) => {
          result.addError(`[${index}].${err.field}`, err.message);
        });
      });
    }

    return result;
  }
}

/**
 * 表单验证器
 */
export class FormValidator {
  constructor() {
    this.fields = {};
  }

  field(name, validator) {
    this.fields[name] = validator;
    return this;
  }

  validate(data) {
    const result = new ValidationResult();
    const errors = {};

    Object.entries(this.fields).forEach(([fieldName, validator]) => {
      const value = data[fieldName];
      const fieldResult = validator.validate(value);
      
      if (!fieldResult.valid) {
        errors[fieldName] = fieldResult.errors.map((e) => e.message).join(', ');
      }
      
      result.merge(fieldResult);
    });

    return {
      valid: result.valid,
      errors,
      warnings: result.warnings,
    };
  }
}

/**
 * 创建验证器的工厂函数
 */
export const validators = {
  string: () => new StringValidator(),
  number: () => new NumberValidator(),
  json: () => new JSONValidator(),
  code: (language) => new CodeValidator(language),
  url: () => new HttpUrlValidator(),
  array: (itemValidator) => new ArrayValidator(itemValidator),
  form: () => new FormValidator(),
};

/**
 * 节点配置验证器工厂
 */
export function createNodeConfigValidator(nodeType, nodeInfo) {
  const formValidator = new FormValidator();
  const inputs = nodeInfo?.inputs || [];

  inputs.forEach((input) => {
    const key = input.key;
    let validator;

    switch (input.valueType || input.type) {
      case 'string':
        validator = validators.string();
        break;
      case 'number':
        validator = validators.number();
        break;
      case 'boolean':
        validator = validators.string();
        break;
      case 'object':
      case 'arrayObject':
        validator = validators.json();
        break;
      case 'arrayString':
      case 'arrayNumber':
        validator = validators.array();
        break;
      default:
        validator = validators.string();
    }

    if (input.required) {
      validator.required(input.requiredMessage || `${input.label || key} 为必填项`);
    }

    if (input.minLength !== undefined) {
      validator.minLength(input.minLength);
    }
    if (input.maxLength !== undefined) {
      validator.maxLength(input.maxLength);
    }
    if (input.min !== undefined) {
      validator.min(input.min);
    }
    if (input.max !== undefined) {
      validator.max(input.max);
    }

    formValidator.field(key, validator);
  });

  return formValidator;
}

export default validators;
