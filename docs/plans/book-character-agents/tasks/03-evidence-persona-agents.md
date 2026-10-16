# T03 生成有原著证据的人物档案与 Agent

状态：已实施并完成阶段验证，2026 年 10 月 12 日。完整书籍语义与人格质量仍由 T12 评测。阶段：M1。

## 用户可见交付

人物页面展示经历、信念、观念、关系和表达依据，并为身份明确的人物自动建立书籍绑定的逻辑 Agent。

## 前置依赖

[T02 手动构建全书人物候选名单](F:/god/project/Octopus/docs/plans/book-character-agents/tasks/02-character-discovery.md)。

## 实施步骤

1. 新增原著断言、证据和人物获知权限，分别保存真相与人物信念。
2. 分场景抽取亲历、被告知、误解与修正、人设和表达样本。
3. 执行引文匹配、实体一致性、支持关系和获知路径检查。
4. 计算最后有证据支持的人物基线，原子发布构建与人物运行策略。
5. 分离公开简介与读者私密档案，展示 ready、sparse、needs_review 等状态。

## 验收标准

- [x] 启用项经过逐字定位及独立阶段的语义/获知审查，发布前核验来源快照。
- [x] 旁白秘密和他人心理没有默认授权；个人项只能授权本人，referenced 不授予获知。
- [x] 信念真值独立存储；明确修正连接旧项，历史项不竞争当前槽位，不明时间保留未知。
- [x] 独立个体可发布 ready/sparse 逻辑 Agent；未授权内容缺省未知，歧义和群体不启用。
- [x] 失败单元、未解身份、拒绝项和基线冲突触发部分发布，进度只统计已验证单元。
- [x] 定义保存在书籍人物表与固定策略中，工具为空，不写通用助手或全局记忆。

- [x] 六张新表及复合外键隔离书籍、来源、构建与人物；基线拒绝未通过的权限。
- [x] 私人类断言有 owner；跨人物授权被校验及 SQL 触发器拒绝。
- [x] 已发布知识、基线、档案、检查点及配置冻结；不安全引用投影清空，只保留允许的命题。

- [x] motivation/value 槽位只来自本人已授权 trait/belief/relation，其他缺项保持 unknown。

## 验证场景

- 真相与错误信念、人物修正、死亡后事件、隐瞒和情境情感的固定样本。
- 伪造引文、越界偏移、错误人物归属与不支持的获知路径。
- 发布事务失败与候选结果不得被聊天读取。

- 他人人格授权、跨构建证据、未授权基线与发布冻结。

## 完成记录

显式提取v7强制每条access明确选择安全摘录（可空、不能省略），服务端最多修复一次，旧契约/default不变。完整项目526通过/13既有跳过，限定Mypy55与Ruff通过。真实新摘录4次的9条摘录格式有效，但仍有远端获知、个人感官分配及命题引用覆盖漏审；已不可用且定义/知识绑定拒绝，旧v5不变。另4次固定重审与4次逐人理由原型保留目标成功和残余失败，不计人格通过。见[获知范围验证](../validation/2026-10-15-persona-scope-validation.md)，全书及质量仍属T12未验收内容。

显式提取v5补齐所有权、approved_excerpt层次及有界分阶段反馈，默认/旧提示保留。41项档案/修订专项及完整项目505项通过，Mypy55与Ruff通过；真实摘录新B 5/8次部分发布4个稀疏个体、2个群体待复核，旧Agent不变。实际归属复核没有额外获知越界，但一条episode的保存引文未覆盖全部内容，不能计引用质量通过；实际档案与新旧版本往返可读。见[字段修复验证](../validation/2026-10-15-persona-structure-validation.md)，不计全书人格或严格A/B。

2026-10-15 冻结v4失败输入的详细字段反馈诊断实际3次，沿用原8次提取预算后累计7/8：一单元提取/审查契约通过，另一单元仍把approved_excerpt放到claim顶层而拒绝。没有接入生产、创建新B或发布基线；原v3/v4提示不变，不能据此计全书人格或有效A/B，见[同B修复阶段记录](../validation/2026-10-15-unit-discovery-repair-validation.md)与[原始结果](../validation/real-model-persona-v4-feedback-v1.json)。

新增工作区迁移 16（迁移前备份）、BookPersonaService、严格提案/审查协议、发布与冻结、读者档案 Modal 和原文定位。T03 从已完成候选创建同来源子构建，复制场景/人物关联并保留 lineage，旧候选版本不改；来源、提取模型、提示词和策略进入新指纹。

17 项阶段回归覆盖秘密与私有人格、伪造/跨身份、错误信念修正、历史/冲突基线、跨单元死亡与复活倒叙、取消迟到结果、发布回滚、来源损坏、冻结、幂等与部分进度。真实 k3 在既有《西游记》摘录上发布 1 个 ready、3 个 sparse，2 个群体待复核，正确 partial_published；这不代表全书人格/知情评测完成。[阶段验证](F:/god/project/Octopus/docs/plans/book-character-agents/validation/2026-10-12-persona-validation.md)。

本阶段交付固定原著档案和逻辑 Agent；T05 将实现人物允许集查询，T06 才开放受约束回复。独立阶段审查仍使用模型，不能宣称自然语言语义零越界。

设计约束见[详细设计](F:/god/project/Octopus/docs/plans/book-character-agents/detailed-design.md)，代码接入点和执行顺序见[实施计划](F:/god/project/Octopus/docs/plans/book-character-agents/implementation-plan.md)。

2026-10-15 增加显式v4提取/审查提示及按保存配置分派，区分主动意向和已完成行为；默认v3、旧提示与旧基线保持。两项公共服务回归验证独立子构建和旧版恢复。真实新档案8次上限、实际4次提取均失败，未进入独立审查或发布；另2次固定审查分别拒绝未获知的天庭评价、接受明确意向，只有局部语义证据。运行不是同修订身份图的受控对照，旧Agent哈希不变，见[完整失败与限制](../validation/2026-10-15-grouped-discovery-persona-validation.md)。档案质量和T12仍未通过。

2026-10-16 增加显式v7独立 per-recipient 获知审查（monotone veto），与canonical review 分离保存，reader 视图显示 knowledge_review 但 Agent definition 不引入；新增 `persona_acquisition` 模块、12 项专项测试、66 项 persona/revisions/cognition 全过、变更文件 Mypy55 与 Ruff 通过、前端生产构建通过；未切换默认提示，全书 v16-pending-03 与 retention-03 快照保留。同日追加 v3 reader 路径回归，验证旧 build_steps（无 acquisition_review 字段）经 `get_character` / `get_agent_definition` 解析时不返回 knowledge_review，agent definition 仍保持 reader-only 隔离。见[获知审查v7记录](../validation/2026-10-16-persona-acquisition-v7-validation.md)。T12 仍未验收。

同日追加 `test_persona_extract_v4_and_review_v6_pin_trait_vs_completed_action_safeguard`：验证 persona-extract-v4 与 persona-review-v6/v7 的 trait/intention-vs-completed-action 防护文字在源提示词编辑后仍保留，锁住 v3 默认下历史动作/性格混说风险。

同日追加 `test_acquisition_prompt_v7_pins_recipient_knowledge_safeguards`：验证 per-recipient 获知审查阶段（ACQUISITION_PROMPT）保留"不使用预训练故事常识"、"旁白客观真相不能替代获知证据"、"在场、同组织、名字暗示能力均不算路径"、"收到命令与获知其所有前因分开"、"集体看听报告不能凭名字逐人分配"等关键防护；63 项 model contracts 全过。

同日追加 `test_acquisition_prompt_v7_frozen_sha256_matches_diagnostic_snapshot`：锁住 ACQUISITION_PROMPT 当前字节级 SHA256 与保存的 `real-model-persona-acquisition-controls-v4.json` 诊断记录 `ccc2eb487c0edbb3659b02ed1b56c0f554a4cd01f664178d1b8b21600d4741c0` 一致；任何字符级改动必须同步更新诊断记录并重跑原生确认。

同日追加 `test_chat_models_module_frozen_sha256_matches_v2_matrix_runtime`：锁住 `chat_models.py` 模块级 SHA256 与 `real-model-t17-matrix-v2.json` 诊断记录 `36040c99…` 一致，与 ACQUISITION_PROMPT 字节级冻结共同覆盖 v9 审查/v14 生成与 ACQUISITION_PROMPT 关键防护不被误改。

同日追加 `test_persona_diagnostic_sha256s_match_prompt_versions`：把 intent-v4、intent-v5、evidence-v6、scope-v7 四份 persona 诊断中的 `prompt_sha256.review` 与 `prompt_sha256.extract` 绑定到 `persona_models.py` 中具体的 v4+v4、v4+v5、v5+v6、v7+v7 组合；任何 prompt 字符级改动必须同步更新诊断并重跑原生。

同日追加 `test_t17_matrix_v2_freezes_all_five_chat_runtime_modules`：把 `real-model-t17-matrix-v2.json` 中 5 个 chat-room 运行时模块（`chat_worker.py`、`chat_models.py`、`chat_validation.py`、`context.py`、`knowledge.py`）的字节级 SHA256 一并冻结；任何 chat-room 端代码改动必须同步更新诊断并重跑六组合原生。

同日追加 `test_discovery_inline_and_grouped_prompts_match_v2_v1_diagnostics`：锁住 `INLINE_PROMPT`（discovery_inline）与 `GROUPED_PROMPT`（discovery_grouped）的字节级 SHA256，分别与 `real-model-inline-discovery-v2.json` 和 `real-model-grouped-discovery-v1.json` 中 `prompt_sha256` 一致；发现阶段提示词任何字符级改动必须同步更新诊断并重跑。

