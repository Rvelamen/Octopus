# T13 扩展 EPUB 与 TXT 的导入和人物构建

状态：首版任务草案，已同步存储约束。阶段：增强。

## 用户可见交付

用户导入 EPUB 或 TXT 小说，可查看原文定位并使用同一人物构建流程。

## 前置依赖

[T10 导入小说后自动构建人物并恢复后台任务](F:/god/project/Octopus/docs/plans/book-character-agents/tasks/10-automatic-import-build.md)。

## 实施步骤

1. 新增附件格式分支及规范化全文解析器。
2. EPUB 保存章节、文件内锚点与文本偏移，TXT 保存稳定偏移和章节候选。
3. 扩展上传、阅读与证据定位 UI，复用来源版本和构建接口。
4. 对编码、重复章节与损坏附件给出明确处理结果。

## 验收标准

- [ ] 同一格式重复导入可复用，跨格式和版本不会混用定位。
- [ ] 非 PDF 引用可打开相应原文位置。
- [ ] 角色权限与自动构建行为与 PDF 一致。
- [ ] 损坏或无法解析的附件不发布人物。

- [ ] 格式变化通过来源版本表达，码点、PDF 页内或 EPUB 锚点不能混用。
- [ ] 不同格式来源仍受同一 B 的证据关联和人物权限约束。

## 验证场景

- EPUB 多章节、TXT 编码、损坏文件与重复章节。
- 非 PDF 来源定位与人物构建回归。

- 码点偏移包含补充平面字符，以及不同定位单位的误用拒绝。

## 完成记录

实施时记录实际改动、检查命令、演示结果和未通过项。模型质量与确定性的权限检查分别记录，不把模型替身测试当成真实模型评测。

设计约束见[详细设计](F:/god/project/Octopus/docs/plans/book-character-agents/detailed-design.md)，代码接入点和执行顺序见[实施计划](F:/god/project/Octopus/docs/plans/book-character-agents/implementation-plan.md)。

