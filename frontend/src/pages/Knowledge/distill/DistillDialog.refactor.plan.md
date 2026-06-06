# DistillDialog 改造规划(方案A:保留 Vault,移除 Folder)

## 一、需求分析

### 1.1 现状
- `DistillDialog` 同时提供两个输出位置选择器:
  - **Target Vault**: 顶层 vault 选择(对应 `knowledge/notes/{vault}/` 根目录)
  - **Save to (click to select folder)**: vault 内的子目录树选择
- 两者在交互上**级联且冗余**: 切换 vault 时,`selectedDir` 会被强制重置到新 vault 的根目录
- 后端 `handleStartDistill` 在父组件 `KnowledgePanel.jsx` 接收的字段:
  ```js
  ({ prompt, template, taskId, targetPath, vault = 'default', sources })
  ```
  其中 `targetPath` 是**父目录**,后端会拼上 `/{timestamp}_{safeName}.md`;`vault` 是 vault 名(写入存储隔离上下文)

### 1.2 用户诉求
- 选择方案 A:**保留 Vault 选择器,移除 Folder 子目录选择器**
- 蒸馏产物直接保存到当前 vault 的根目录(`knowledge/notes/{vault}/`)

### 1.3 改造收益
- 交互步骤从"先选 vault,再展开目录树选 folder"简化为"选 vault"
- 移除约 100 行与目录树相关的 state/逻辑/UI
- 输出位置语义更清晰:"输出到哪个 vault"

### 1.4 范围边界
- ✅ 修改文件:`frontend/src/pages/Knowledge/distill/DistillDialog.jsx`
- ❌ 不修改:`KnowledgePanel.jsx`(后端接口签名保持兼容)
- ❌ 不修改:后端 `knowledge_distill` 协议(`target_path` 仍接受父目录路径,后端行为不变)
- ⚠️ 兼容性:`DistillDialog` 的 `onStartDistill` 回调仍然传 `targetPath` 字段(由 vault 根目录计算),父组件无感知

---

## 二、实现思路

### 2.1 删除项
- `DirectoryTree` 内部组件(整段)
- state: `selectedDir`、`expandedPaths`、`treeItems`
- 派生值: `rootPath`、`effectiveRoot`
- callback: `loadDirectory`、`handleToggle`
- UI 区块: 整个"Save to (click to select folder)" 卡片
- imports: `Folder`、`ChevronDown`、`ChevronRight` 图标(`useCallback` 也可一并清理)

### 2.2 保留/修改项
- 保留: `TEMPLATES`、`slugify`、Vault 选择器、Template 选择器、Prompt 输入、Footer 按钮
- 保留: `selectedVault` state + `reset()` 中相关重置
- 保留: `addTask`、`onStartDistill` 调用
- 修改: `handleStart` 中:
  - 旧:`const targetPath = ${selectedDir}/${timestamp}_${safe}.md;`
  - 新:`const rootDir = knowledge/notes/${selectedVault || 'default'}; await onStartDistill({ ..., targetPath: rootDir, ... });`
  - 父组件 `handleStartDistill` 内部已自行拼 `/{timestamp}_{safe}.md`,所以传根目录即可
- 修改: Vault 区块标签文案,补充"输出将保存到此 vault 根目录"的说明
- 修改: 删除 `reset()` 中 `selectedDir`/`expandedPaths` 相关

### 2.3 UI 调整
- 在 Vault 选择器下方增加一行辅助说明文字(`fontSize: 11, color: var(--text-3)`),提示:
  > "Distilled output will be saved to the vault root."

---

## 三、模块拆分

| 模块 | 操作 | 位置 |
|------|------|------|
| Imports | 清理未使用符号 | `DistillDialog.jsx` L1-4 |
| `DirectoryTree` 组件 | 删除 | L9-65 |
| `slugify` | 保留 | L67-72 |
| `DistillDialog` 主体 | 改造 state/handlers/UI | L74-end |
|  └─ state 清理 | 删除 `selectedDir`/`expandedPaths`/`treeItems` | L88-91 |
|  └─ `loadDirectory`/`handleToggle`/`rootPath`/`effectiveRoot` | 删除 | L107-145 |
|  └─ `reset` | 清理 | L97-105 |
|  └─ `handleStart` | 改用 vault 根目录 | L137-156 |
|  └─ JSX 移除 | 删除 "Save to" 区块;Vault 区块加说明 | L271-300 |

---

## 四、关键逻辑说明

### 4.1 输出目录计算
```js
// 蒸馏文件最终路径(由父组件拼):
//   `${targetPath}/${timestamp}_${safeName}.md`
// 我们传:
//   targetPath = `knowledge/notes/${selectedVault || 'default'}`
// → 父目录 = vault 根目录,与改造前选择 vault 根目录行为完全一致
```

### 4.2 状态重置
- `reset()` 保留 `selectedVault = ''`(回到 default),其余 vault 相关 state 一并清空
- 取消/启动成功后调用 `reset()` + `onCancel()`,与原行为一致

### 4.3 父组件契约
- `onStartDistill({ prompt, template, taskId, targetPath, vault, sources })` 签名不变
- `targetPath` 现在固定为 `knowledge/notes/{vault}/`,父组件无需任何改动

---

## 五、任务清单

- [x] T1 输出开发规划文档
- [x] T2 改造 `DistillDialog.jsx`:
  - [x] T2.1 清理 imports
  - [x] T2.2 删除 `DirectoryTree` 组件
  - [x] T2.3 删除目录树相关 state/callback
  - [x] T2.4 改造 `handleStart` 使用 vault 根目录
  - [x] T2.5 UI 移除"Save to"区块,Vault 区块加说明
- [x] T3 自检:无未使用变量、无悬空 state
- [x] T4 同步勾选本文档
- [x] T5 输出后续优化与迭代计划文档

## 六、变更记录

| 项 | 原 | 现 |
|----|----|----|
| 文件行数 | 385 | 255(减少约 34%) |
| state 数量 | 7 (template/prompt/isStarting/selectedVault/selectedDir/expandedPaths/treeItems) | 4 (template/prompt/isStarting/selectedVault) |
| 内部组件 | 1 (`DirectoryTree`) | 0 |
| 异步回调 | `loadDirectory` + `handleToggle` | 仅 `handleStart` |
| 派生值 | `rootPath` + `effectiveRoot` | `vaultRootPath` |
| 图标 import | 5 (Sparkles/Check/X/Folder/ChevronDown/ChevronRight) | 2 (Sparkles/X) |
| React hook | `useState` + `useEffect` + `useCallback` | 仅 `useState` |
| `useDistillTasks` | 引入 | 保留(行为未变) |
| `KnowledgePanel.jsx` | 传 `sourceTitle` + `sendWSMessage` | 已移除这两个 props |

## 七、契约对照

`onStartDistill` 回调签名(改造前后完全兼容):

```js
{
  prompt: string,
  template: 'summary' | 'qa' | 'methodology' | 'mindmap' | 'custom',
  taskId: undefined,           // 仍传 undefined,后端自行生成
  targetPath: string,           // 改造前 = 用户选择的子目录;改造后 = vault 根目录
  vault: 'default' | string,    // 保持不变
  sources: string[],            // 保持不变
}
```

父组件 `KnowledgePanel.handleStartDistill` 内部自行拼 `${targetPath}/${timestamp}_${safeName}.md`,因此 `targetPath` 语义由"具体子目录"变为"vault 根目录"对后端透明。
