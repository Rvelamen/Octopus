/**
 * 工作流 IO 类型定义
 */

// 选中的知识库类型
export const createSelectedDatasetType = (data = {}) => ({
  datasetId: data.datasetId,
  avatar: data.avatar,
  name: data.name,
  vectorModel: data.vectorModel || { model: '' }
});

// 自定义字段配置类型
export const createCustomFieldConfigType = (data = {}) => ({
  selectValueTypeList: data.selectValueTypeList,
  showDefaultValue: data.showDefaultValue,
  showDescription: data.showDescription
});

// 输入组件属性类型
export const createInputComponentPropsType = (data = {}) => ({
  key: data.key,
  label: data.label,
  valueType: data.valueType,
  required: data.required,
  defaultValue: data.defaultValue,
  referencePlaceholder: data.referencePlaceholder,
  isRichText: data.isRichText,
  placeholder: data.placeholder,
  maxLength: data.maxLength,
  minLength: data.minLength,
  list: data.list,
  markList: data.markList,
  step: data.step,
  max: data.max,
  min: data.min,
  precision: data.precision,
  canSelectFile: data.canSelectFile,
  canSelectImg: data.canSelectImg,
  canSelectVideo: data.canSelectVideo,
  canSelectAudio: data.canSelectAudio,
  canSelectCustomFileExtension: data.canSelectCustomFileExtension,
  customFileExtensionList: data.customFileExtensionList,
  canLocalUpload: data.canLocalUpload,
  canUrlUpload: data.canUrlUpload,
  maxFiles: data.maxFiles,
  timeGranularity: data.timeGranularity,
  timeRangeStart: data.timeRangeStart,
  timeRangeEnd: data.timeRangeEnd,
  datasetOptions: data.datasetOptions,
  customInputConfig: data.customInputConfig,
  enums: data.enums
});

// 输入配置类型
export const createInputConfigType = (data = {}) => ({
  key: data.key,
  label: data.label,
  description: data.description,
  required: data.required,
  inputType: data.inputType,
  value: data.value,
  list: data.list
});

// 工作流节点输入项类型
export const createFlowNodeInputItemType = (data = {}) => ({
  ...createInputComponentPropsType(data),
  selectedTypeIndex: data.selectedTypeIndex,
  renderTypeList: data.renderTypeList || [],
  valueDesc: data.valueDesc,
  value: data.value,
  debugLabel: data.debugLabel,
  description: data.description,
  toolDescription: data.toolDescription,
  enum: data.enum,
  inputList: data.inputList,
  canEdit: data.canEdit,
  isPro: data.isPro,
  isToolOutput: data.isToolOutput,
  deprecated: data.deprecated
});

// 工作流节点输出项类型
export const createFlowNodeOutputItemType = (data = {}) => ({
  id: data.id,
  key: data.key,
  type: data.type,
  valueType: data.valueType,
  valueDesc: data.valueDesc,
  value: data.value,
  label: data.label,
  description: data.description,
  defaultValue: data.defaultValue,
  required: data.required,
  invalid: data.invalid,
  customFieldConfig: data.customFieldConfig,
  deprecated: data.deprecated
});

// 引用值类型
export const createReferenceItemValueType = (data = {}) => [
  data.nodeId || '',
  data.outputKey || ''
];

// HTTP 参数和头部项类型
export const createHttpParamAndHeaderItemType = (data = {}) => ({
  key: data.key,
  type: data.type,
  value: data.value
});
