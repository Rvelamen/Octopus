# DistillDialog 后续优化与迭代计划

> 本文档对应改造 `frontend/src/pages/Knowledge/distill/DistillDialog.jsx` (方案A)
> 当前文件行数:255(由 385 行精简而来)

---

## 一、已识别的可优化项(按优先级排序)

### P1 · 用户体验类

#### 1.1 Vault 下拉改 chips/标签样式
- **现状**: `<select>` 原生下拉,样式与项目 pixel 风格不统一
- **方案**: 复用 `vaults` 列表渲染成水平 chip 列表,选中态使用 `--accent`
- **收益**: 视觉一致,触摸设备更友好,可显示 vault 图标/数量等元信息
- **工作量**: 0.5 人时

#### 1.2 输出路径支持"自定义 vault 内子目录"配置项(可选)
- **现状**: 蒸馏产物固定存到 vault 根目录
- **方案**: 在 Vault 选择器下加一个简化的"Subfolder (optional)"输入框,留空则存到 vault 根目录
- **取舍**: 与"方案A"初衷有冲突,需先确认用户是否真的不需要子目录归档
- **工作量**: 0.5 人时

#### 1.3 Template 选择器改为"卡片式"展示
- **现状**: 6 个 chip 横向排列,hover 只能看 title tooltip
- **方案**: 改为 2-3 列卡片,卡片内显示 `label + desc`,选中态边框高亮
- **收益**: 用户首次使用时即可看到模板说明,降低学习成本
- **工作量**: 1 人时

### P1 · 代码质量类

#### 1.4 抽离内联样式到 CSS Module 或 styled-components
- **现状**: 整个文件 60+ 处内联 `style={{...}}`
- **方案**:
  - 选项 A: 创建 `DistillDialog.module.css`,迁移所有静态样式
  - 选项 B: 引入项目内的 `pixel-button`/`dialog-*` 体系,补充缺失样式
- **收益**: 减少重复代码,便于主题切换
- **工作量**: 2-3 人时(涉及样式整理 + 回归测试)

#### 1.5 拆分 `handleStart` 中的副作用
- **现状**: 4 个职责耦合:validity check / addTask / onStartDistill / reset
- **方案**:
  ```js
  const validate = () => allSources.length > 0;
  const buildArgs = () => ({ prompt, template, taskId: undefined, targetPath: vaultRootPath, vault: ..., sources: allSources });
  const handleStart = async () => {
    if (!validate()) return;
    setIsStarting(true);
    addTask(...);
    try { await onStartDistill(buildArgs()); reset(); onCancel(); }
    catch (e) { ... }
  };
  ```
- **收益**: 易测试、易读
- **工作量**: 0.5 人时

#### 1.6 提取 `vaultRootPath` 工具常量
- **现状**: 硬编码 `knowledge/notes/${vault}` 路径前缀
- **方案**: 与后端约定常量 `KNOWLEDGE_VAULT_ROOT = 'knowledge/notes'`,从共享常量文件导入
- **收益**: 路径协议集中管理,避免后端路径规则变化时散落修改
- **工作量**: 0.5 人时(需评估后端是否已有共享常量模块)

### P2 · 功能增强

#### 2.1 蒸馏成功后自动跳转到目标 vault
- **现状**: 蒸馏任务在后台跑,用户需手动切换到对应 vault 文件树
- **方案**: `handleStart` 成功后,调用 `onCancel` 之前通过 props 回调通知父组件切换到目标 vault
- **新增 props**: `onDistillStarted?: (vault) => void`
- **工作量**: 1 人时

#### 2.2 重复文件名校验
- **现状**: 父组件 `handleStartDistill` 未做重名检查,后端行为待确认
- **方案**:
  - 前端: 提交前 `sendWSMessage('knowledge_list', { path: vaultRootPath })` 检查同名文件
  - 后端: 若需后端兜底,在 `knowledge_distill` handler 内做校验
- **工作量**: 1-2 人时

#### 2.3 模板选择持久化
- **现状**: 每次打开弹窗都重置为 `summary`
- **方案**: 用 `localStorage` 记忆用户上次选择
- **工作量**: 0.3 人时

#### 2.4 自定义模板(用户级)
- **现状**: `TEMPLATES` 是写死的 5 个
- **方案**: 允许用户在后端保存自定义模板,在 `TEMPLATES` 后追加
- **工作量**: 4-6 人时(涉及后端存储 + 前端管理 UI)

### P2 · 性能/可观测性

#### 2.5 任务启动埋点
- **现状**: 没有埋点,无法统计用户常用 template / vault
- **方案**: 在 `handleStart` 中 `console.info` 或调用统一埋点 SDK
- **工作量**: 0.5 人时

#### 2.6 `vaultRootPath` 路径合法性校验
- **现状**: 用户可输入包含 `..` 或特殊字符的 vault 名(虽然 `<option>` 限制了,但理论上后端会再次校验)
- **方案**: 前端做白名单校验 `[a-zA-Z0-9_-]+`,失败时禁用提交按钮并提示
- **工作量**: 0.3 人时

### P3 · 长期演进

#### 3.1 蒸馏参数预设(Preset)
- 允许用户保存 "Template + Prompt + Vault" 的组合为 Preset
- 工作量: 8-10 人时

#### 3.2 蒸馏结果预览
- 后端蒸馏完成后,在任务详情里支持打开预览
- 工作量: 4-6 人时(主要在后端和任务列表)

#### 3.3 蒸馏产物自动标签/分类
- 蒸馏过程中由 AI 推断分类,自动写入 frontmatter
- 工作量: 6-8 人时(涉及 prompt 设计和后端 schema 扩展)

---

## 二、回归测试清单

> 改造后需确保以下场景行为不变或符合预期

| # | 场景 | 期望 | 备注 |
|---|------|------|------|
| 1 | 单文件蒸馏,默认 vault | 输出到 `knowledge/notes/default/{ts}_{name}.md` | 路径由父组件拼接 |
| 2 | 单文件蒸馏,选择具体 vault | 输出到 `knowledge/notes/{vault}/{ts}_{name}.md` | |
| 3 | 批量蒸馏,N 个文件 | 每个文件独立输出,文件名时间戳一致或递增 | 后端保证 |
| 4 | 切换 vault 前后提交 | 各自分别写入对应 vault 根目录 | |
| 5 | 取消按钮 | 关闭弹窗,状态完全重置 | |
| 6 | 提交中取消 | 当前不支持(只有 isStarting 锁),若需要可在后续迭代 | 不在本次范围 |
| 7 | `vaults` 为空 | 隐藏 Vault 选择器,直接存到 default | 见 `vaults.length > 0` 条件渲染 |
| 8 | 父组件未传 `onStartDistill` | 抛错(调用空函数) | 业务层需保证总是传入 |

---

## 三、潜在风险与监控

### 3.1 兼容性
- ✅ 父组件 `KnowledgePanel.jsx` 的 `handleStartDistill` 签名未变,业务无感
- ✅ 后端 `knowledge_distill` 协议未变
- ⚠️ 若有第三方扩展(插件/其他页面)直接使用 `DistillDialog`,需同步更新 props 传入

### 3.2 监控指标建议
- 蒸馏任务启动成功率(`onStartDistill` 抛错率)
- 平均每次蒸馏的 `template` 分布(用于优化默认模板)
- 用户选择非 default vault 的占比(用于评估 vault 功能渗透率)

### 3.3 已知未覆盖场景
- 蒸馏进行中网络断开: 当前仅前端 `setIsStarting(true)` 后 await,失败会 `setIsStarting(false)` 恢复
- 服务端异步失败的提示: 任务失败需要用户在 `TaskDetailModal` 查看

---

## 四、文档同步

| 文档 | 是否需要更新 | 负责人 |
|------|--------------|--------|
| `DistillDialog.jsx` 头部 JSDoc | 可选(当前无) | TBD |
| `Knowledge/index.js` 导出说明 | 无需更新 | — |
| README/API 文档 | 暂无 Distill 公开 API,跳过 | — |
| 本规划文档 | 已勾选完成 | DONE |

---

## 五、迭代路线图(建议)

```
Sprint N    1.4 内联样式提取 + 1.5 handleStart 拆分(基础重构)
Sprint N+1  1.1 Vault chips + 1.3 Template 卡片(UI 升级)
Sprint N+2  2.1 蒸馏后跳转目标 vault + 2.3 模板持久化
Sprint N+3  2.2 重名校验 + 2.5 埋点
后续季度     3.x 长期演进(Preset / 预览 / 分类)
```
