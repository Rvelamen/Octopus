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

