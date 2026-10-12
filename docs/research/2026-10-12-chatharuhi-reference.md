# ChatHaruhi 对 Octopus 人物 Agent 的参考价值

核对日期：2026 年 10 月 12 日。主仓库固定提交 290bf4ad22076156083804013012847a77c0646c，实际运行库 Haruhi-2-Dev 固定提交 776c401092ef726d786e23dea7ec4771f3ac9428。结论：适合作为原著对白与人物表现的参考实现，采用时仍需执行 Octopus 的知情、版本和房间边界。

官方[小说提取说明](https://github.com/LC1332/Chat-Haruhi-Suzumiya/blob/290bf4ad22076156083804013012847a77c0646c/characters/novel_collecting/Readme.md)给出小说结构化、选定人物、整理场景对白、设计人物提示词和建立向量资料的流程。它提出 StoryTeller 多人物交流与续写方向；该说明不足以证明具备持久化群聊队列、禁言/移除或有限轮次控制。

[运行代码](https://github.com/LC1332/Haruhi-2-Dev/blob/776c401092ef726d786e23dea7ec4771f3ac9428/ChatHaruhi/ChatHaruhi.py)将角色 system prompt、相关经典场景与当前聊天历史组合；资料与历史分别限制 token 数。该类的 story 检索与内存 history 没有体现 Octopus 所需的断言获知 ACL、构建版本和房间 epoch，因此不能仅以每人一份资料库证明知情正确。

这是工程判断：T05 继续先联接人物允许集再检索；T06 可借鉴人物原著表达样例，但只能使用本人获准的安全投影，不能把整个经典场景交给人物。T07 保留带房间/代数/说话者的听说来源；T08/T09/T17 继续使用服务端有限队列与讨论快照。T12 分开评测人物语气表现和原著知识越界，避免把语气相似当作事实正确。

作者的 [2023 年技术报告](https://arxiv.org/abs/2308.09597)报告了角色扮演改进与自动/人工评测；该结果支持把方案作为人物表现基线，不证明 Octopus 的严格原著隔离或多人调度已经验证。未安装、运行或引入该库，也未导入其角色语料。

## 已纳入设计的采用决策

用户要求将参考工程用于提升精度与聊天质量后，采用其素材组织和表达检索方法，适配当前模块。具体[适配设计](F:/god/project/Octopus/docs/plans/book-character-agents/chatharuhi-adoption-design.md)定义事实与表达双通道、说话者/原句/当前基线审查、表达派生存储与生命周期、上下文预算及同模型质量对照。原项目固定版本的直接运行仅作为可选研究实验，主线继续使用 Octopus 的 Provider、允许集和发布校验。

落地任务为 T05 表达素材及检索、T06 上下文/样例/候选校验、T07 记忆分区、T10 自动派生任务、T11 来源清理、T12 原有 60 项加 24 项表达质量问题的 A/B。T10 完整交付新增 T05 前置；已完成 T01–T04 不回溯改写。T05 的原生服务与预览现已实施，见[验证记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/2026-10-12-knowledge-expression-validation.md)；聊天接入及质量收益仍待 T06/T12，不将当前空素材探针当作质量提升证明。
