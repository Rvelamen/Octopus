# Agent 执行可视化实现计划

## 概述
按照方案 A（扩展现有事件系统）实现 Agent 执行可视化功能。

## 任务列表

### ✅ Task 1: 增强工具调用详情（耗时、错误、输入输出）
- **状态**: ✅ 已完成并已修复
- **后端改动**:
  - ✅ 在 `backend/agent/loop.py` 中记录工具执行时间
  - ✅ 增强 `agent_tool_result` 事件数据，添加 `elapsed_ms`、`success`、`error`、`result_full`
  - ✅ 错误信息包含 message、type、traceback
  - ✅ **修复**: 添加 `import time` 到文件顶部，避免运行时导入问题
- **前端改动**:
  - ✅ 更新 `App.jsx` 中的工具调用状态处理，支持新字段
  - ✅ **修复**: `success` 为 `undefined` 时默认为 `true`，避免误判为错误
  - ✅ 在 `ChatPanel.jsx` 的 `renderToolCard` 中显示耗时、错误详情
  - ✅ 添加错误展示区域，支持 traceback 折叠查看
  - ✅ 添加执行时间显示区域
- **修改文件**:
  - ✅ `backend/agent/loop.py` - 添加时间记录和错误详情，修复 import
  - ✅ `frontend/src/App.jsx` - 更新事件处理，修复 success 默认值
  - ✅ `frontend/src/components/panels/ChatPanel.jsx` - 增强工具卡片显示
  - ✅ `frontend/src/pixel-theme.css` - 添加新样式
- **修复的问题**:
  - 工具执行成功但显示为失败：`success` 为 `undefined` 时被误判为 `false`
  - `import time` 在循环内部导致的时间计算问题
- **新增功能**:
  - 工具调用卡片显示执行耗时（⏱️ 1.2s）
  - 失败时显示红色错误区域，展示错误信息
  - 可展开查看完整 traceback
  - 展开详情显示完整执行时间

### ✅ Task 2: 添加迭代时间线
- **状态**: ✅ 已完成
- **后端改动**:
  - ✅ 在 `backend/agent/loop.py` 中添加 `agent_iteration_start` 和 `agent_iteration_end` 事件
  - ✅ 记录每次迭代的开始/结束时间
  - ✅ 迭代结束时发送 elapsed_ms
- **前端改动**:
  - ✅ 创建新的 `IterationTimeline` 组件
  - ✅ 在 `App.jsx` 中添加 iterations 状态和事件处理
  - ✅ 在 `ChatPanel.jsx` 中集成时间线
  - ✅ 添加 CSS 样式
- **修改文件**:
  - ✅ `backend/agent/loop.py` - 添加迭代事件
  - ✅ `frontend/src/App.jsx` - 添加 iterations 状态和事件处理
  - ✅ `frontend/src/components/panels/ChatPanel.jsx` - 集成时间线组件
  - ✅ `frontend/src/components/panels/IterationTimeline.jsx` (新) - 时间线组件
  - ✅ `frontend/src/pixel-theme.css` - 添加时间线样式
- **新增功能**:
  - 垂直时间线展示每次迭代
  - 显示迭代编号 (Iteration 1/20)
  - 显示迭代耗时 (⏱️ 1.2s)
  - 状态指示器（运行中/已完成）
  - 可展开查看迭代详情

### ✅ Task 3: 实时 Token 统计
- **状态**: ✅ 已完成
- **后端改动**:
  - ✅ 在每次 LLM 调用后发送 `agent_token_usage` 事件
  - ✅ 包含 prompt_tokens、completion_tokens、total_tokens
  - ✅ 在 `agent_finish` 事件中发送累计 token 统计
  - ✅ Token 数据已入库（`token_usage` 表）
- **前端改动**:
  - ✅ 在 `App.jsx` 中处理 token 使用事件
  - ✅ 在流式消息的右下角显示实时 token 统计
  - ✅ 在最终回复中显示累计 token 总数
  - ✅ 显示格式：`streaming · 1,234 tokens` → 完成后显示最终总数
- **修改文件**:
  - ✅ `backend/agent/loop.py` - 添加 token 使用事件发送，agent_finish 携带累计统计
  - ✅ `frontend/src/App.jsx` - 处理 agent_token_usage 和 agent_finish 事件
  - ✅ `frontend/src/components/panels/ChatPanel.jsx` - 在消息右下角显示 token 统计
  - ✅ `frontend/src/pixel-theme.css` - 添加 message-token-count 样式
- **显示效果**:
  - 位置：消息气泡的右下角，时间戳旁边
  - 流式中：`streaming · 1,234 tokens`
  - 完成后：`1,234 tokens`（显示累计总数）
  - 数据持久化：已入库，可按需查询历史统计

### ⏳ Task 4: SubAgent 状态可视化
- **状态**: 待实现
- **后端改动**:
  - SubAgent 启动/完成/失败时发送事件到主 WebSocket
  - 包含任务描述、状态、耗时、结果摘要
- **前端改动**:
  - 创建 `SubAgentStatus` 组件
  - 在主聊天面板中显示 SubAgent 状态
  - 支持展开查看详细结果
- **预计影响文件**:
  - `backend/agent/subagent.py`
  - `backend/agent/loop.py`
  - `frontend/src/App.jsx`
  - `frontend/src/components/panels/SubAgentStatus.jsx` (新)

### ⏳ Task 5: 上下文压缩可视化
- **状态**: 待实现
- **后端改动**:
  - 上下文压缩时发送 `agent_context_compression` 事件
  - 包含压缩前后的 token 数、压缩率、原因
- **前端改动**:
  - 在聊天流中显示压缩通知卡片
  - 显示压缩效果对比
- **预计影响文件**:
  - `backend/agent/context.py` 或 `backend/agent/loop.py`
  - `frontend/src/App.jsx`
  - `frontend/src/components/panels/ChatPanel.jsx`

### ⏳ Task 6: 性能分析面板
- **状态**: 待实现
- **后端改动**:
  - 迭代结束时发送 `agent_performance` 事件
  - 包含各阶段时间分布
- **前端改动**:
  - 创建 `PerformancePanel` 组件
  - 显示时间分布饼图/柱状图
- **预计影响文件**:
  - `backend/agent/loop.py`
  - `frontend/src/App.jsx`
  - `frontend/src/components/panels/PerformancePanel.jsx` (新)

## 实施原则

1. **向后兼容**: 新增事件不影响现有功能
2. **渐进式**: 每个 Task 独立完成，可单独测试
3. **最小改动**: 优先利用现有代码结构
4. **用户体验**: 默认简洁，详细信息可展开

## 下一步

### 已完成 Task 1-3，下一步是 Task 4: SubAgent 状态可视化

**Task 4 计划**：
1. 后端：SubAgent 启动/完成/失败时发送事件到主 WebSocket
2. 前端：创建 `SubAgentStatus` 组件
3. 前端：在主聊天面板或迭代时间线中显示 SubAgent 状态
4. 支持展开查看详细结果

**预期效果**：
- 显示 SubAgent 任务列表
- 实时状态更新（排队中/执行中/完成/失败）
- 显示耗时和结果摘要
- 可点击查看完整结果
