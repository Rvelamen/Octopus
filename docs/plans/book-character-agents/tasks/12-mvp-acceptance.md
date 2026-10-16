# T12 完成首版回归评测与开关发布

状态：进行中；开关/保留数据回滚子交付已实现，完整书籍、真实模型与完整操作验收未通过（2026-10-14）。阶段：M4。

## 用户可见交付

提供两部书籍人物混聊的完整演示与可审查评测结果，功能可分阶段开启，关闭后原有图书馆功能可继续使用。

## 前置依赖

[T11 处理书籍版本更换与删除后的房间状态](F:/god/project/Octopus/docs/plans/book-character-agents/tasks/11-source-lifecycle.md)、[T16 新增人物聊天室 Tab 与 3D 圆桌气泡界面](F:/god/project/Octopus/docs/plans/book-character-agents/tasks/16-roundtable-chat-ui.md)及[T17 支持主题聊天与自由聊天](F:/god/project/Octopus/docs/plans/book-character-agents/tasks/17-discussion-modes.md)。

## 实施步骤

1. 汇总任务已有回归用例，补全原创短篇的知情与信念标注。
2. 建立真实模型评测集，分别检查可知事实、不可知事实、人格、记忆与多人关联性。
3. 进行两部选定书籍的人工复核和端到端混聊演示，记录误判、延迟与调用量。
4. 增加功能开关、迁移备份与回滚说明，定向纳入需要提交的文档与测试。
5. 保留原 60 项边界评测，新增 24 项表达/交流质量问题；先跑其中 8 项小预算试验，再同模型/同原著构建以独立干净房间完成无样例/有样例对照与盲评。
6. 分别记录提取归属/知情精度、检索召回、可知/不可知/误拒、人物表现、复读和自然程度、token/调用/重写与时延；增强开关的默认启用需有可复核改善且边界指标不退步。
7. 按[质量验证协议](F:/god/project/Octopus/docs/plans/book-character-agents/chat-quality-protocol.md)冻结题集/金标准，记录每次素材实际进入上下文的情况，并独立复核整段正文和模型/人工分歧。

## 验收标准

- [x] 结构权限、幂等、停止与记忆隔离的确定性自动检查通过；真实模型与完整路径另列，不据此关闭首版验收。
- [ ] 评测分别报告正确回答与正确拒绝，不用单一拒答率证明效果。
- [ ] 真实模型质量结论附书籍、模型、配置和样本数量。
- [ ] 功能关闭后 PDF 阅读、论文蒸馏、普通书籍问答正常。
- [x] 回滚保留新功能记录，提交中包含预期文档和测试。

- [x] 复合外键、索引、触发器和服务查询范围均有独立回归；SQL 草案与应用测试分开记录。
- [ ] 验证跨工作区、来源、构建、人物、房间和 epoch 的读写矩阵及删除保留历史。

- [ ] 同一工作区两部书的单聊、混聊、同名 @、禁言、移除恢复与局部来源删除均纳入验收。
- [ ] 记录每个角色的独立原著准确性与公共听说传播，不能以混聊效果掩盖知识越界。

- [ ] 秒数设置保存后被真实单聊与全体提问读取，运行中快照与超时继续行为正确。

- [ ] 独立 Tab、固定圆桌座位、同消息气泡与右栏同步、长文本/遮挡、WebGL 降级和资源释放通过操作验收。
- [ ] 生成中禁言/移除、时间上限暂停、重置/重连和局部来源删除时，气泡与人物状态保持一致；不公开未校验正文。

- [ ] 验证 free/topic × natural/directed/all 六种组合、空闲换题、暂停恢复保留快照，以及主题不扩大知识范围。
- [ ] 真实模型评测包含动机/价值两难、情绪触发、参数知识诱导和合理问题过度拒答，并分别报告。

- [ ] 同模型 A/B 固定书籍/来源/构建、人物、问题序列及可控配置，房间历史独立；24 项表达样本覆盖两部书、多人物和六类行为，不能用 8 项试验宣称完整收益。
- [ ] 独立报告人物/别名/说话者/权限/基线标注精度与允许依据召回，样本数量及分母可审查；不能以语气分替代正确性。
- [ ] 关键越界失败阻止增强默认启用；B 的可知准确性、误拒和错误确认不退于 A，盲评改善可复核，不确定时继续补评。
- [ ] 关闭表达增强保留同一事实、人设、记忆和有限轮次约束；新增派生表迁移/来源清理/取消/空素材均有回归。
- [ ] 实际输入/输出 token、调用与重写数、分阶段时延和超时率附对照；向量/重排未验证时不绕过词项允许集。
- [ ] 空素材或与 A 无实质输入差异的 B 不计有效表达对照；受控运行样本不计自动提取准确率，失败/超时不从总运行结果中删除。
- [ ] 人物忠实度、当前交流回应和自然程度分别盲评；24 对有人工评定，关键失败与分歧逐项复核，另有至少八对分层二次复核。
- [ ] 否定自传、遗漏正文断言、他人对白、旧信念和跨书听说都有负例；条件推演、引述及有据否定经历有正例，防止仅靠拒答提升指标。

## 验证场景

- 全套本功能 pytest 回归与前端构建。
- 真实模型人工评测及人物对话/多人队列操作验收。
- 临时数据库迁移、开关关闭及老功能回归。

- 结构校验、查询范围与真实模型质量报告的覆盖对照。

- 两部书及多个角色分别报告可知、不可知、房间听说和成员控制场景。

- 同段旁白秘密、他人台词、旧信念样例、当前事实缺席、原句复读与长历史预算竞争的表达增强负例。
- 自由/主题、单聊/混聊中表达素材的独立来源与当前问题相关性；质量评测按[适配设计](F:/god/project/Octopus/docs/plans/book-character-agents/chatharuhi-adoption-design.md) Q05 执行。

## 完成记录

后续发现单元扫描、保留失败/尝试数的恢复及显式continue链路已接通，真实两书同B按钮和前后哈希通过；全部未处理结束仍有失败则不进入T03。完整项目513通过/13项既有跳过，Mypy55、Ruff、相关Lint、前端类型与构建通过。另2次固定保存引文审查正反例正确，但未接入、未发布、非人工盲评；全书24次有界窗口与剩余验收见[后续扫描记录](../validation/2026-10-15-discovery-pending-validation.md)。

档案v5字段修复得到真实摘录部分发布5/8次，旧Agent不变，UI显示4个稀疏个体/2个待复核群体并可往返历史。新意向trait有据，一条经历仍有保存引文覆盖漏审；独立字面选项2次仅1/2通过，不推进全书。最终完整项目505通过/13项既有跳过、限定Mypy55与Ruff通过；同一前端源码复用既有类型/构建结果。真实限制与后续扫描/引用修复见[阶段记录](../validation/2026-10-15-persona-structure-validation.md)，84题、全书、完整应用和人工盲评仍未验收。

2026-10-15 完整单元第二次修复接入同一v16 B，真实窗口15/24次后两书分别保留4/411及6/581单元；一个修复检查点有实际作用域与完整来源覆盖证据，另两次错误称呼被拒绝。人物/来源/自动构建组件真实只读WS及TXT高亮操作通过，同时修复自动重试旧错误残留。档案另3次冻结输入反馈诊断未发布；全书、84题、完整应用与人工盲评仍未验收，见[阶段记录](../validation/2026-10-15-unit-discovery-repair-validation.md)。

实施时记录实际改动、检查命令、演示结果和未通过项。模型质量与确定性的权限检查分别记录，不把模型替身测试当成真实模型评测。

完整项目最新520通过/13既有跳过；限定Mypy55、Ruff通过，前端源码复用e561733的类型/构建。真实v6摘录仍语义漏审，已隔离、0成员且实际定义/知识绑定拒绝；4次追加控制仅诊断、合计8/8。完整来源另24次推进到西游记12/411、红楼梦14/581，未有全书档案。原始失败、隔离及证明范围见[阶段记录](../validation/2026-10-15-persona-evidence-validation.md)，本任务质量及完整应用项均未关闭。

最新完整项目526通过/13既有跳过，限定Mypy55/Ruff及两轴代码审查通过。显式v7摘录字段契约已落实，真实新B4次仍失败并隔离；同窗4次重审失败，另4次逐人理由原型只完成目标诊断，不是全书、人工或完整应用验收。前端同源码复用已通过检查，全书32次同B窗仍在执行，见[范围与残余失败](../validation/2026-10-15-persona-scope-validation.md)。T17与本任务均未关闭。

已接通进程启动能力、后端写入口/自动工作器门控、旧租约恢复、GET_CONFIG 和前端确认/只读界面。新入口关闭不删除记录，停止与安全成员撤销保留；重置与生成禁止。阶段验证见[发布开关记录](../validation/2026-10-14-release-gates-validation.md)，操作见[发布/回滚](../release-and-rollback.md)。使用受控历史夹具的浏览器操作不代表完整应用或人格质量，验收清单仍未关闭。

2026-10-15 汇总当前确定性层：完整项目369通过、13项既有环境跳过，新增发现修复的85项专项在完整结果内，不叠加计数；原结构草案177项与实际服务测试分开记录。限定范围Mypy52文件、Ruff、前端类型/构建及实际全书失败状态/原文组件操作通过。仅据这些证据勾选确定性和保留数据回滚子项；全书自动人物、真实聊天、完整应用操作与60项边界/24项表达仍未验收。证据与实际模型失败见[窗口修复验证](../validation/2026-10-15-window-repair-validation.md)。

同日追加发现诊断和评测入口后，最终完整项目385通过/13既有环境跳过，限定Mypy53文件与Ruff通过。T17六组合原生25次、固定审查2次累计27/32，已保留漏审、误拒及来源强度警告；实际3D历史气泡与右栏同ID/seq/正文、2D切换和证据操作通过。该集尚未完成原著金标准复核，明确是摘录开发诊断，不替代本任务84题、完整应用或全书人格验收，见[六组合记录](../validation/2026-10-15-discussion-matrix-validation.md)。

设计约束见[详细设计](F:/god/project/Octopus/docs/plans/book-character-agents/detailed-design.md)，代码接入点和执行顺序见[实施计划](F:/god/project/Octopus/docs/plans/book-character-agents/implementation-plan.md)。

同日继续T17修复及全书发现：原32次开发窗口已耗尽且保留误拒、超时；独立精修4/6次得到一题条件推演发布与固定漏审负例拒绝。新消息在实际生产圆桌组件中核对ID/seq/全文和引用，未新增模型调用；原生结果、Agent逐条复核和UI证据分开保存。T17尚未完整复验，本任务84题、全书人物及完整应用路径仍未通过；详见[条件推演记录](../validation/2026-10-15-cognition-repair-validation.md)。

新增显式v15发现格式，115项专项保持原完整来源/身份校验及发布栅栏。新独立全书构建各完成3单元后仍在下一单元失败，未发布完整原著档案；旧v14保留，计数不跨构建相加。真实冻结探针、完整窗口失败与剩余预算的处理见[内联发现记录](../validation/2026-10-15-inline-discovery-validation.md)，不以契约成功关闭本任务。

本轮最终完整项目428通过、13项既有环境跳过；限定Mypy54文件、Ruff、前端类型/构建通过。独立六组合复验26/28次、10条人物发布，实际普通窗口暂停/手动继续已发生，但两处历史动作的来源强度仍未解决，不关闭质量项。未接入嵌套发现原型以2次初稿+2次指定修复得到两项冻结单元契约通过，仍不能当作全书自动发现。详见[矩阵v2](../validation/2026-10-15-discussion-matrix-v2-validation.md)和[来源排障](../validation/2026-10-15-inline-discovery-validation.md)。

继续推进的最终完整项目464通过/13项既有环境跳过，限定Mypy55文件、Ruff、相关ESLint、前端类型及构建通过。已修复真实失败子构建遮住旧档案入口的回归，并在实际WS/组件中验证往返版本、跨书清空和不改旧基线，见[历史回溯](../validation/2026-10-15-history-anchor-validation.md)。本轮16次原生含全书v16失败、档案v4提取失败、固定语义对照及未接入提及格式探针，全部记录，不将任何契约通过计作全书/人格/84题验收；下一步继续同B有限修复协议和具体提取错误，见[原生证据](../validation/2026-10-15-grouped-discovery-persona-validation.md)。

显式审查v7接入独立 per-recipient 获知审查（monotone veto），分离保存 canonical_review 与 acquisition_review，reader 视图新增 knowledge_review；12 项专项测试与 66 项 persona/revisions/cognition 全过、变更文件 Mypy/Ruff 通过、前端生产构建通过；未切换默认 review 提示或启动新真实模型窗口，全书 v16-pending-03 快照保留。本任务质量及完整应用项仍未关闭，见[获知审查v7记录](../validation/2026-10-16-persona-acquisition-v7-validation.md)。

同日追加 v3 reader 路径回归，验证旧 build_steps（无 acquisition_review 字段）经 `get_character` / `get_agent_definition` 解析时不返回 knowledge_review，agent definition 仍保持 reader-only 隔离。

同日追加 v9 review / v14 generate 历史动作防护提示回归 `test_v9_review_and_v14_generate_pin_historical_action_safeguard`，确保 character-chat-review-v9 仍包含"勇敢、敢于探险、率先进入，只支持实际给出的性格或行为"与"愿意/敢于/想要/说要去也不能自动证明已经完成该行动"防护段落、character-chat-v14 仍保留"愿意/敢于/想要/说要做不证明已经做成或看到了什么"；63 项 model contracts 全过。

同日追加 `test_persona_extract_v4_and_review_v6_pin_trait_vs_completed_action_safeguard`：锁住 v4 extract 与 v6/v7 persona review 的 trait-vs-completed-action 防护文字不被误改。

同日追加 `test_acquisition_prompt_v7_pins_recipient_knowledge_safeguards`：验证 per-recipient 获知审查阶段（ACQUISITION_PROMPT）保留 monotone veto 关键防护——"不使用预训练故事常识"、"旁白客观真相不能替代获知证据"、"在场、同组织、名字暗示能力均不算路径"、"收到命令与获知其所有前因分开"、"集体看听报告不能凭名字逐人分配"——不被后续提示词编辑弱化；63 项 model contracts 全过。

同日追加 `test_acquisition_prompt_v7_frozen_sha256_matches_diagnostic_snapshot`：锁住 ACQUISITION_PROMPT 字节级 SHA256 与 `real-model-persona-acquisition-controls-v4.json` 诊断记录 `ccc2eb48…` 一致；任何字符级改动（哪怕只是空白）必须同步更新诊断并重跑原生。

同日追加 `test_chat_models_module_frozen_sha256_matches_v2_matrix_runtime`：锁住 `chat_models.py` 模块级 SHA256 与 `real-model-t17-matrix-v2.json` 诊断记录 `36040c99…` 一致，与 ACQUISITION_PROMPT 字节级冻结共同覆盖 v9 审查/v14 生成与 ACQUISITION_PROMPT 关键防护不被误改。

同日追加 `test_persona_diagnostic_sha256s_match_prompt_versions`：把 intent-v4、intent-v5、evidence-v6、scope-v7 四份 persona 诊断中的 `prompt_sha256.review` 与 `prompt_sha256.extract` 绑定到 `persona_models.py` 中具体的 v4+v4、v4+v5、v5+v6、v7+v7 组合；任何 prompt 字符级改动必须同步更新诊断并重跑原生。

同日追加 `test_t17_matrix_v2_freezes_all_five_chat_runtime_modules`：把 `real-model-t17-matrix-v2.json` 中 5 个 chat-room 运行时模块（`chat_worker.py`、`chat_models.py`、`chat_validation.py`、`context.py`、`knowledge.py`）的字节级 SHA256 一并冻结；任何 chat-room 端代码改动必须同步更新诊断并重跑六组合原生。

同日追加 `test_discovery_inline_and_grouped_prompts_match_v2_v1_diagnostics`：锁住 `INLINE_PROMPT`（discovery_inline）与 `GROUPED_PROMPT`（discovery_grouped）的字节级 SHA256，分别与 `real-model-inline-discovery-v2.json` 和 `real-model-grouped-discovery-v1.json` 中 `prompt_sha256` 一致；发现阶段提示词任何字符级改动必须同步更新诊断并重跑。

同日追加 `test_chat_review_v9_sha_matches_conditional_and_negative_diagnostics`：锁住 `character-chat-review-v9` 字节级 SHA256 与 `real-model-t17-conditional-positive-v1.json` 及 `real-model-t17-current-negative-v1.json` 中 `review_prompt_sha256` 一致；是 `chat_models.py` 模块冻结的细粒度补充。

同日追加 `test_v9_review_pins_cognition_change_safeguard`：锁住 v9 review 在 v8 基础上新增的 3 段 cognition 防护——"原著的认识变化也是事实"、"嵌在过去经历中的'有没有X/是否X'"、"新处境的条件性选择"——防止 v9 review 退回 v8 后再次出现过去经历否定与新条件推演过严的双向回归。

同日追加 `test_persona_version_constants_pin_aliases_and_prompts`：锁住 persona 构建管线的 4 个版本常量（`STRUCTURED_PERSONA_VERSION="persona-extract-v5"`、`EVIDENCE_PERSONA_VERSION="persona-extract-v6"`、`SCOPED_PERSONA_VERSION="persona-extract-v7"`、`ACQUISITION_REVIEW_VERSION="persona-review-v7"`）必须指向仍存在的 prompt 键；锁住 `persona-review-v7` 是 `persona-review-v6` 的同对象别名（v7=v6 共用 prompt 体），并锁住 persona-extract v3→v7 是逐版本累加而非别名；69 项 model contracts 全过。

同日追加 `test_inline_discovery_v2_module_sha_matches_diagnostic_runtime`：锁住 `backend/services/book_world/discovery_inline.py` 的字节级 SHA256 与 `real-model-inline-discovery-v2.json` 中 `runtime_sha256` 记录一致，是 INLINE_PROMPT 字节冻结之外的"模块本身"补充；70 项 model contracts 全过。

同日追加 `test_room_and_knowledge_policy_versions_pin_diagnostic_strings`：锁住 `ROOM_POLICY_VERSION="bounded-room-v1"`、`KNOWLEDGE_POLICY_VERSION="canonical-perspective-v1"` 与 `PersonaConfig.policy_version` 默认值 `"canonical-persona-v3"` 必须与 t17 matrix v1/v2 中 `character_scopes` 与 `model_config.policy_version` 一致；71 项 model contracts 全过。

同日追加 `test_t17_matrix_runner_sha_and_baseline_invariant_pin_v2_diagnostic`：锁住 `discussion-acceptance.py` 矩阵执行器字节级 SHA256 与 t17 matrix v2 / cognition-pilot v1 / cognition-pilot v2 三份诊断的 `runner_sha256=cdcc9040…` 一致；并锁住 matrix v1 / matrix v2 / cognition-pilot v1 / cognition-pilot v2 四份诊断共同报告的 `canonical_baselines_unchanged=True` 与 `canonical_baselines_before == canonical_baselines_after`，作为"矩阵与认知探针是只读、非破坏性"的硬证据；72 项 model contracts 全过。

同日追加 `test_inline_discovery_v1_module_shas_pin_numbered_runtime`：锁住 `discovery_numbered.py` 字节级 SHA256 与 inline discovery v1 诊断 `5f16f1b1…` 一致；并验证 v1 与 v2 inline 诊断中 `discovery_inline.py` SHA 必然不同（作为 v1→v2 之间合法改动的历史快照契约）；73 项 model contracts 全过。

同日追加 `test_inline_discovery_v1_corpus_files_sha_pin_full_source`：锁住 `tmp/book-corpus/西游记.txt` 与 `tmp/book-corpus/红楼梦.txt` 字节级 SHA256 与 inline discovery v1 诊断 `corpus_sources.books[].sha256` 一致（`3f2bf216…` 与 `5eca888f…`），作为发现阶段输入数据的硬证据；74 项 model contracts 全过。

同日追加 `test_persona_sub_build_diagnostics_pin_agent_unchanged_invariant`：把 `real-model-persona-intent-v4-01.json` / `intent-v5-01.json` / `evidence-v6-01.json` / `scope-v7-01.json` 四份档案子构建诊断的 `old_agent_sha256_before == old_agent_sha256_after` 与 `old_agent_unchanged=True` 锁定为"档案子构建只读、不改写父 Agent 哈希"的非破坏性探针契约；并把 `evidence-v6` / `scope-v7` 中的 `previous_v5_sha256_before == previous_v5_sha256_after` 锁定为"v6/v7 在 v5 之上做加法而不改写 v5 基线"的硬证据，与 t17 矩阵 `canonical_baselines_unchanged` 契约共同覆盖两端只读不变量；75 项 model contracts 全过。

同日追加 `test_persona_v5_audit_and_ui_proof_pin_readonly_invariants`：把 `persona-v5-agent-source-audit.json` 的 4 个固定 `permission_checks` 决策标签（`stone_birth_composite_rejected_and_revoked` / `heaven_facts_not_granted_to_stone` / `groups_remain_needs_review` / `stone_intent_trait_supported`）与 `old_agent_unchanged=True` / `native_trace_sha256` 锁定为档案审查探针契约；并把 `persona-v5-ui-proof.json` 的 `model_calls=0` / `only_read_actions=True` / `new_build` 等于审计 `build_id` / `old_build != new_build` / 4 个 "visible" 布尔锁定为只读 UI 证明契约——审计↔UI 配对被绑死，任何把模型调用注入"只读证明"路径的回归都会失败；76 项 model contracts 全过。

同日追加 `test_persona_v4_controls_pin_native_budget_and_case_set`：锁住 v4 controls/v4 feedback 两份诊断的 `actual_native_calls <= native_call_ceiling` 预算硬上限与 `cases` 列表非空；并把 v4 controls 的 `actual_native_calls == native_call_ceiling` 与固定 2 个语义 case 标签（`unheard-heaven` / `volunteered-intention`）锁定为 v3 默认审查的语义金标准（"未亲历的天庭评价应拒"+"主动意向应收"）；v4 feedback 的实际 < 预算（3<4）因验证短路被显式允许；77 项 model contracts 全过。

同日追加 `test_discussion_probe_v8_through_v12_pin_baseline_unchanged_invariant`：把 `real-model-discussion-v8-probe.json` / `v9-probe.json` / `v10-probe.json` / `v11-probe.json` / `v12-probe.json` 五份顺序讨论探针的 `baseline_sha256_before == baseline_sha256_after` 与 `canonical_baselines_unchanged=True` 锁定为"聊天 v8→v12 全程非破坏性"的硬证据——是 t17 矩阵 `canonical_baselines_unchanged` 契约的逐版本探针伙伴；任何偷偷写入基线的探针改动会让该测试失败；78 项 model contracts 全过。

同日追加 `test_expression_revision_room_memory_probes_pin_readonly_invariants`：把 `real-model-expression-probe.json` 的 `canonical_archive_unchanged=True` / `sample_sha256` 存在 / `actual_calls==2` 锁定为 expression 探针只读契约；把 `real-model-revision-probe.json` 的 `original_build_preserved=True` / `base_archive_snapshot_assertion_passed=True` / `global_model_settings_changed=False` / `calls==6` 锁定为 revision 探针只读契约；把 `real-model-room-memory-probe.json` 的 `canonical_baseline_unchanged=True` / `actual_calls==call_budget` 锁定为 room-memory 探针只读契约——三项单功能探针的只读保护与 t17 矩阵/v8-v12 探针基线共同覆盖"无探针偷偷写入权威库/基线/原档案"的硬约束；79 项 model contracts 全过。

同日追加 `test_t17_discussion_cases_dataset_pins_six_combination_ground_truth`：把 `t17-discussion-cases-v1.json` 的 `dataset_version=t17-six-combinations-v1` / `native_call_ceiling=32` / `manual_continues_per_turn=1` / `reviewer_kind` 仍以 Agent 审查自称、6 个 case 完整覆盖 free/topic × natural/directed/all 6 组合 + 每个 case 必含 5 个必填字段锁定为 t17 六组合金标准数据集契约——是 t17 矩阵 / 探针 / 认知 v1 等所有相关诊断引用同一份 case 集合的硬证据；80 项 model contracts 全过。

同日追加 `test_t17_review_cognition_v1_pins_instruction_sha_and_aggregate_budget`：把 `real-model-t17-review-cognition-v1.json` 的 `instruction_sha256=e7295bfe…`（cognition-safeguard 评审增补段字节级 SHA）/ `source_matrix=real-model-t17-matrix-v1.json` / `actual_native_calls==native_call_ceiling`（2==2）/ `aggregate_t17_ceiling=32` / `aggregate_native_calls=27`（v1 矩阵 25 + cognition 2）/ `publication=False` 锁定为认知防护评审增补的字节级指纹与 t17 累计预算硬约束——v9 review cognition 防护段从此与 ACQUISITION_PROMPT 等其它 prompt 冻结同档；81 项 model contracts 全过。

同日追加 `test_discovery_probes_pin_no_publication_and_actual_budget`：把 8 份发现探针（v8-repair / v9-repair / v10-repair / v12-choices / v13-literal / v13-numbered / v14-window-repair / v12-binding-repairs）的 `database_publication=False` 或 `publication=False` 与 `terminal=True` 锁定为"发现探针不写库"的硬证据；并把 `real-model-discovery-v7-contract.json` 的 `validation_pass=True` 锁定为 v7 契约在冻结输入下成立的硬证据——八份探针共同背书"发现阶段只读不写库"的非破坏性约束；82 项 model contracts 全过。

同日追加 `test_t17_agent_reviews_pin_unfinished_and_baseline_invariants`：把 `t17-cognition-agent-review.json` 与 `t17-matrix-v2-agent-review.json` 两份 Agent 自审报告的 `t17_complete=False` / `t12_complete=False` / `quality_pass=False` 锁定为"本任务与 T12 尚未通过 Agent 自审即未验收"的硬证据；并把 cognition 报告的 `baseline_mutation=False` 与 v2 矩阵报告的 `canonical_baselines_unchanged=True` 锁定为"未验收 ≠ 偷偷改基线"的硬约束——`t17_complete` / `t12_complete` 不许在没有重录诊断和新一轮通过的前提下偷偷翻成 True；83 项 model contracts 全过。

同日追加 `test_small_probes_pin_frozen_source_sha_and_budget_consumption`：把 `real-model-detail-review-v7.json` 的 `source_sha256=4cd263c7…` + `actual_calls == native_call_budget` (2==2) / `real-model-grouped-repair-v1.json` 的 `source_report_sha256=84247f0f…` + `actual_native_calls == native_call_ceiling` (2==2) + 两 case 共用 `prompt_sha256=02c581f2…` / `real-model-unit-literal-options-v1.json` 的 `probe_source_sha256=0473ebdd…` + `actual_native_calls == native_call_ceiling` (2==2) 锁定为详情审查 / grouped 修复 / 字面选项三份小预算探针的字节级输入指纹 + 预算硬相等；三份探针全部 `publication: False` + `terminal: True`——是 `t17_complete=False` / `t12_complete=False` 之外"小预算探针不偷偷写库"的硬证据；84 项 model contracts 全过。

同日追加 `test_anchored_and_mentions_prototypes_share_input_pair`：把 `real-model-anchored-discovery-v1.json` 与 `real-model-mentions-discovery-v1.json` 两份 v1 原型的 `cases[].source_input_sha256` 共同锁定为同一对冻结输入（`65270ca4…` + `d6dea8f6…`），并锁定 `policy_version="candidate-identity-v2"` + `prompt_version` 以 `-prototype-v1` 结尾——是发现阶段"原型而非生产"标识与对比同一对冻结单元的硬证据；85 项 model contracts 全过。

同日新增 [T12 验收证据索引](../validation/2026-10-16-t12-acceptance-index.md)，把 T01–T11/T15/T16/T18 已落实的存储/服务/协议/界面证据按 T12 验收标准逐条映射到阶段验证、测试文件和运行脚本；只把"结构权限/幂等/隔离/开关/读写矩阵/可关闭/可回滚"等确定性子项列为已勾选，60 项边界 / 24 项表达 / 84 题金标准 / 全书 / 完整应用 / 人工盲评归入"未关闭清单"并指向现有真实模型记录。本索引不替模型质量背书；4 节起列明每条未关闭项的当前证据位置与状态。85 项 model contracts 仍为完整项目前置硬证据。

同日新增 Q05 "T12 实施时提供实际文件及运行入口" 落实 [t12-quality-cases-v1.json](../validation/t12-quality-cases-v1.json) 8-pilot 案例集（4 边界 + 4 表达，覆盖 knowable / unknowable / belief / emotion + answer / challenge / comfort / cross_book_hearsay，引用 Q05 verdict_legend 六分类与 4 必填金标准字段）+ [t12-quality-runner.py](../../t12-quality-runner.py) 实际运行入口（与 [discussion-acceptance.py](../../discussion-acceptance.py) 同 MAX_NATIVE_CALLS=32 上限、同 SHA 锁、同样支持 `--dry-run`/`--case-id`）；87 项 model contracts 新增 `test_t12_pilot_eight_cases_dataset_pins_layered_gold_standard` 锁定 8-pilot 数据集 tier×class 覆盖与 gold_standard 4 字段必填；新增 `test_t12_pilot_runner_dry_run_produces_frozen_non_destructive_shape` 锁定 runner 字节级 SHA 与 dry-run 输出形状（mode=dry_run / actual_native_calls=0 / publication=False / terminal=True / quality_pass=False / 每 case 必带回完整 gold_standard）。当前仅以 `--dry-run` 模式验证数据集/角色/策略/字节指纹四项硬证据，未消耗任何模型预算；完整 60+24 题集尚未撰写，8 项小预算真实运行待 budget 重开后由 `python t12-quality-runner.py --workspace <path> --output <path>` 触发。

