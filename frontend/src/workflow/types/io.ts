/**
 * 工作流 IO 类型定义
 */

export interface VectorModel {
  model: string;
}

export interface SelectedDataset {
  datasetId?: string;
  avatar?: string;
  name?: string;
  vectorModel?: VectorModel;
}

export interface CustomFieldConfig {
  selectValueTypeList?: unknown[];
  showDefaultValue?: boolean;
  showDescription?: boolean;
}

export interface InputComponentProps {
  key?: string;
  label?: string;
  valueType?: string;
  required?: boolean;
  defaultValue?: unknown;
  referencePlaceholder?: string;
  isRichText?: boolean;
  placeholder?: string;
  maxLength?: number;
  minLength?: number;
  list?: unknown[];
  markList?: unknown[];
  step?: number;
  max?: number;
  min?: number;
  precision?: number;
  canSelectFile?: boolean;
  canSelectImg?: boolean;
  canSelectVideo?: boolean;
  canSelectAudio?: boolean;
  canSelectCustomFileExtension?: boolean;
  customFileExtensionList?: string[];
  canLocalUpload?: boolean;
  canUrlUpload?: boolean;
  maxFiles?: number;
  timeGranularity?: string;
  timeRangeStart?: string;
  timeRangeEnd?: string;
  datasetOptions?: unknown[];
  customInputConfig?: unknown;
  enums?: unknown[];
}

export interface InputConfig {
  key?: string;
  label?: string;
  description?: string;
  required?: boolean;
  inputType?: string;
  value?: unknown;
  list?: unknown[];
}

export interface FlowNodeInputItem extends InputComponentProps {
  selectedTypeIndex?: number;
  renderTypeList: string[];
  valueDesc?: string;
  value?: unknown;
  debugLabel?: string;
  description?: string;
  toolDescription?: string;
  enum?: unknown[];
  inputList?: unknown[];
  canEdit?: boolean;
  isPro?: boolean;
  isToolOutput?: boolean;
  deprecated?: boolean;
}

export interface FlowNodeOutputItem {
  id?: string;
  key?: string;
  type?: string;
  valueType?: string;
  valueDesc?: string;
  value?: unknown;
  label?: string;
  description?: string;
  defaultValue?: unknown;
  required?: boolean;
  invalid?: boolean;
  customFieldConfig?: CustomFieldConfig;
  deprecated?: boolean;
}

export interface ReferenceItemValue {
  nodeId: string;
  outputKey: string;
}

export interface HttpParamAndHeaderItem {
  key?: string;
  type?: string;
  value?: string;
}

export const createSelectedDatasetType = (data: Partial<SelectedDataset> = {}): SelectedDataset => ({
  datasetId: data.datasetId,
  avatar: data.avatar,
  name: data.name,
  vectorModel: data.vectorModel || { model: "" },
});

export const createCustomFieldConfigType = (data: Partial<CustomFieldConfig> = {}): CustomFieldConfig => ({
  selectValueTypeList: data.selectValueTypeList,
  showDefaultValue: data.showDefaultValue,
  showDescription: data.showDescription,
});

export const createInputComponentPropsType = (data: Partial<InputComponentProps> = {}): InputComponentProps => ({
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
  enums: data.enums,
});

export const createInputConfigType = (data: Partial<InputConfig> = {}): InputConfig => ({
  key: data.key,
  label: data.label,
  description: data.description,
  required: data.required,
  inputType: data.inputType,
  value: data.value,
  list: data.list,
});

export const createFlowNodeInputItemType = (data: Partial<FlowNodeInputItem> = {}): FlowNodeInputItem => ({
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
  deprecated: data.deprecated,
});

export const createFlowNodeOutputItemType = (data: Partial<FlowNodeOutputItem> = {}): FlowNodeOutputItem => ({
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
  deprecated: data.deprecated,
});

export const createReferenceItemValueType = (data: Partial<ReferenceItemValue> = {}): [string, string] => [
  data.nodeId || "",
  data.outputKey || "",
];

export const createHttpParamAndHeaderItemType = (data: Partial<HttpParamAndHeaderItem> = {}): HttpParamAndHeaderItem => ({
  key: data.key,
  type: data.type,
  value: data.value,
});
