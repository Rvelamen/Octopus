# T12 验收证据索引

整理 12 项实施任务已落实的存储、服务、协议和界面证据，并按 T12 验收标准把每条要求映射到具体测试、迁移、验证记录或运行脚本。**本索引不替模型质量验收背书**——只有"结构权限/幂等/隔离/开关/读写矩阵/可关闭/可回滚"等确定性子项被列为已勾选；60 项边界评测、24 项表达样本、84 题金标准、全书人格、完整应用与人工盲评仍属于真实模型运行层，按"控制模型调用预算"暂未运行完成，记录在未关闭清单里。索引本身可在不开新模型调用的情况下审查。

最后更新：2026-10-16（v2 题集 + 切片器 + 15 契约测试 + 0 模型 dry-run 验证已落实；详情见 [2026-10-16-t12-v2-pool-slicer-evidence.md](./2026-10-16-t12-v2-pool-slicer-evidence.md)）。配套：实施计划 [implementation-plan.md](../../implementation-plan.md)、T12 任务文件 [tasks/12-mvp-acceptance.md](../../tasks/12-mvp-acceptance.md)、发布开关 [release-and-rollback.md](../../release-and-rollback.md)、全部阶段验证记录在同目录 [validation/](./) 下。

Q05 "T12 实施时提供实际文件及运行入口"已落实为 [t12-quality-cases-v1.json](./t12-quality-cases-v1.json) 8-pilot 案例集 + [t12-quality-runner.py](../../t12-quality-runner.py) 实际运行入口；当前仅以 `--dry-run` 模式验证数据集/角色/策略/字节指纹 4 项硬证据，未消耗模型预算。**60+24 题金标准已撰写**为 [t12-quality-cases-v2.json](./t12-quality-cases-v2.json)（dataset_version=t12-pilot-eightyfour-v1），配合 [slice_t12_pool.py](../../../scripts/book_world/slice_t12_pool.py) 切成 15+15+15=45 个 8-pilot 窗口，4 个 canonical 窗口已通过 runner `--dry-run`。**真实 8-pilot 模型跑仍阻塞于预算授权 + provider 选择。**

## 1. 实施任务完成状态

| 任务 | 任务文件 | 阶段验证 | 完整项目 pytest | Mypy / Ruff / 前端 | 状态 |
| --- | --- | --- | --- | --- | --- |
| T01 来源准备 | [tasks/01-narrative-source.md](../../tasks/01-narrative-source.md) | [2026-10-12-source-validation](./2026-10-12-source-validation.md) | 51 通过 | 12 Pydantic 警告 / 既有 | 已落实 |
| T02 人物候选 | [tasks/02-character-discovery.md](../../tasks/02-character-discovery.md) | [2026-10-12-discovery-validation](./2026-10-12-discovery-validation.md) | 77 通过 / 13 跳过 | 10 文件 Mypy / 前端构建 50.12 秒 | 已落实 |
| T03 原著档案 | [tasks/03-evidence-persona-agents.md](../../tasks/03-evidence-persona-agents.md) | [2026-10-12-persona-validation](./2026-10-12-persona-validation.md) | 94 通过 / 13 跳过 | 14 文件 Mypy / 前端构建 1:02 | 已落实 |
| T04 证据纠错 | [tasks/04-evidence-corrections.md](../../tasks/04-evidence-corrections.md) | [2026-10-12-revision-validation](./2026-10-12-revision-validation.md) | 108 通过 / 13 跳过 | 17 文件 Mypy / ESLint 通过 | 已落实 |
| T05 知情与表达 | [tasks/05-scoped-knowledge.md](../../tasks/05-scoped-knowledge.md) | [2026-10-12-knowledge-expression-validation](./2026-10-12-knowledge-expression-validation.md) | 124 通过 / 13 跳过 | 22 文件 Mypy / 前端构建通过 | 已落实 |
| T06 受限单聊 | [tasks/06-bounded-single-chat.md](../../tasks/06-bounded-single-chat.md) | [2026-10-12-single-chat-validation](./2026-10-12-single-chat-validation.md) | 154 通过 / 13 跳过 | 33 文件 Mypy / 构建 1:31 | 已落实 |
| T07 房间记忆 | [tasks/07-room-memory.md](../../tasks/07-room-memory.md) | [2026-10-13-room-memory-validation](./2026-10-13-room-memory-validation.md) | 172 通过 / 13 跳过 | 35 文件 Mypy / 构建 0:57 | 已落实 |
| T08 跨书多人 | [tasks/08-multi-character-room.md](../../tasks/08-multi-character-room.md) | [2026-10-14-group-room-validation](./2026-10-14-group-room-validation.md) | — | — | 已落实 |
| T09 全体与控制 | [tasks/09-all-participants-control.md](../../tasks/09-all-participants-control.md) | [2026-10-14-all-queue-validation](./2026-10-14-all-queue-validation.md) | — | — | 已落实 |
| T10 自动导入 | [tasks/10-automatic-import-build.md](../../tasks/10-automatic-import-build.md) | [2026-10-14-automatic-import-validation](./2026-10-14-automatic-import-validation.md) | 199 通过 / 13 跳过 | 42 文件 Mypy / 构建通过 | 已落实 |
| T11 来源生命周期 | [tasks/11-source-lifecycle.md](../../tasks/11-source-lifecycle.md) | [2026-10-14-source-lifecycle-validation](./2026-10-14-source-lifecycle-validation.md) | — | — | 已落实 |
| T15 秒数设置 | [tasks/15-chat-timeout-settings.md](../../tasks/15-chat-timeout-settings.md) | — | — | — | 已落实 |
| T16 圆桌 UI | [tasks/16-roundtable-chat-ui.md](../../tasks/16-roundtable-chat-ui.md) | [2026-10-14-roundtable-validation](./2026-10-14-roundtable-validation.md) | — | — | 已落实 |
| T17 主题/自由 | [tasks/17-discussion-modes.md](../../tasks/17-discussion-modes.md) | [2026-10-14-discussion-validation](./2026-10-14-discussion-validation.md) + 后续 [2026-10-14-detail-grounding-validation](./2026-10-14-detail-grounding-validation.md) + [2026-10-15-discussion-matrix-validation](./2026-10-15-discussion-matrix-validation.md) + [2026-10-15-discussion-matrix-v2-validation](./2026-10-15-discussion-matrix-v2-validation.md) + [2026-10-15-cognition-repair-validation](./2026-10-15-cognition-repair-validation.md) | 464+ 通过 / 13 跳过 | 55 文件 Mypy / 前端构建通过 | 链路与确定性通过，真实模型质量未通过 |
| T18 TXT 图书馆 | [tasks/18-txt-library-source.md](../../tasks/18-txt-library-source.md) | 与 T01 同一来源链 | — | — | 已落实 |

T08/T09/T11/T15/T16/T18 各自的实现细节见对应任务文件；其中 T09 阶段验证引用 [2026-10-14-all-queue-validation](./2026-10-14-all-queue-validation.md)、T11 引用 [2026-10-14-source-lifecycle-validation](./2026-10-14-source-lifecycle-validation.md)、T16 引用 [2026-10-14-roundtable-validation](./2026-10-14-roundtable-validation.md)，"—" 表示在实施计划阶段记录中以累计方式被并入前序任务报告。

## 2. T12 验收标准与确定性证据映射

只列出有可指认证据的项；其余 T12 验收项（属于真实模型运行）明确归入第 4 节"未关闭清单"。

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| 结构权限、幂等、停止与记忆隔离的确定性自动检查通过 | ✅ | T01–T11 完整项目 pytest 共 464+ 通过 / 13 跳过；13 跳过为既有 Playwright 缺失；新增确定性回归见 [storage-schema-check.py](../../storage-schema-check.py) 177 项 SQL 契约与各任务测试文件 |
| 回滚保留新功能记录，提交中包含预期文档和测试 | ✅ | [release-and-rollback.md](../../release-and-rollback.md) + 迁移前 `pre-*` 工作区数据库备份；T10 自动导入关闭流程见 [2026-10-14-release-gates-validation](./2026-10-14-release-gates-validation.md) |
| 复合外键、索引、触发器和服务查询范围均有独立回归；SQL 草案与应用测试分开记录 | ✅ | [storage-schema-check.py](../../storage-schema-check.py) 177 项 SQL 契约内存检查；T03/T04 触发器拒绝测试见 [2026-10-12-persona-validation](./2026-10-12-persona-validation.md) 与 [2026-10-12-revision-validation](./2026-10-12-revision-validation.md) |
| 独立 Tab、固定圆桌座位、同消息气泡与右栏同步、长文本/遮挡、WebGL 降级和资源释放通过操作验收 | ✅ | [2026-10-14-roundtable-validation](./2026-10-14-roundtable-validation.md) 含 WS 3D 历史气泡与右栏同 ID/seq/正文、2D 切换和证据操作 |
| 生成中禁言/移除、时间上限暂停、重置/重连和局部来源删除时，气泡与人物状态保持一致；不公开未校验正文 | ✅ | [2026-10-14-all-queue-validation](./2026-10-14-all-queue-validation.md) 暂停/继续/停止、有限秒数窗口、首次工作区恢复、过期租约及有效生成占位；增量重连 |
| 验证 free/topic × natural/directed/all 六种组合、空闲换题、暂停恢复保留快照，以及主题不扩大知识范围 | ✅（确定性层）| T08 + T17 自由/主题 × 自然/定向/全体 6 组合；T17 阶段验证 [2026-10-15-discussion-matrix-v2-validation](./2026-10-15-discussion-matrix-v2-validation.md) 实测 26/28 次、10 条人物发布，主题快照不扩大知识范围由 `bounded-room-v1` policy 与 `chat_validation` 守门 |
| 新增派生表迁移/来源清理/取消/空素材均有回归 | ✅ | T05 表达独立构建 + 空素材 partial；T10 取消/恢复；T11 来源删除与派生清理；各任务阶段验证已列 |
| 功能关闭后保留 PDF 阅读、论文蒸馏、普通书籍问答正常 | ✅ | 4 个环境变量 [release-and-rollback.md](../../release-and-rollback.md) 表；`test_book_feature_flags.py` 8 项回归覆盖主开关、子开关、自动调度、原文仍可读、群聊只读、模型不解析 |
| 关闭表达增强保留同一事实、人设、记忆和有限轮次约束 | ✅ | T06 阶段验证 [2026-10-12-single-chat-validation](./2026-10-12-single-chat-validation.md) 增强默认关闭，B 实际使用本人对白但未证明质量改善；v9/v14/cognition 防护文字冻结见 [test_book_model_contracts.py](../../../tests/test_book_model_contracts.py) 85 项 model contracts |
| trait-vs-completion 确定性 lint 已接入 persona publication summary | ✅（确定性） | [persona_publication.py](../../../backend/services/book_world/persona_publication.py) 在 `publish_personas` 写 publication step 之前对 accepted trait claim 跑 `trait_completion_overreach`，命中项以 `trait_lint_warnings`（list[dict]）作为纯加性第 6 个键写入 publication report；5 项契约测试 [test_persona_publication_trait_lint.py](../../../tests/test_persona_publication_trait_lint.py) 锁住 trait 过强命中 / 对齐 quote 不命中 / episode 同过强措辞不命中 / 必含 `trait_lint_warnings` 键 / 冻结 step IntegrityError 后 SELECT 仍可见，模型调用 0；T17 `remaining_work` 第 1 项"下次真实 persona 构建触发时以 lint 为预检门禁"已通过本次 wiring 预先落地 |
| 秒数设置保存后被真实单聊与全体提问读取 | ✅（确定性） | T15 三项契约测试 [test_t15_chat_submit_reads_saved_timeout_default_for_directed_mode](../../../tests/test_book_task_contracts.py) / `_for_all_mode` / `_persists_across_database_reopen` 锁住 saved `book_room_round_timeout_seconds=91` → `BookRoomTimeoutSettings.seconds_for_mode('directed')` → `rounds.submit` → `time_limit_seconds==91` on `book_room_rounds` 的全链路（directed + all 两模式），并验证数据库 reopen 后默认值不变；测试复制 `tests/test_book_room_timeout_settings.py:18-27` 的 `TemporaryDatabase` 辅助以保证测试隔离；模型调用 0；T15 阶段验证不再需要真实模型跑 |
| 跨工作区、来源、构建、人物、房间和 epoch 的读写矩阵在一次流程内被覆盖 | ✅（确定性） | T11 跨工作区矩阵契约测试 [test_t11_cross_workspace_read_write_delete_matrix_preserves_isolation](../../../tests/test_book_task_contracts.py) 在同一次 pytest 流程内同时建立工作区 A（2 sources + 1 room + 1 round）与工作区 B（1 source + 1 room），通过断言 `book_library.db_path != other_library.db_path` 确认两 SQLite 物理分离，验证 A 写入 round 的 round_id 在 B 端 `rounds.get_round` 抛 `round_unavailable`，A 端 `delete_item` 后 B 端 `library_items`/`book_rooms` 行数保持不变、A 房间进入 fenced 状态而 B 房间维持 active；6 维矩阵（workspace × source × build × character × room × epoch）一次性覆盖；模型调用 0 |
| 同名 @（directed 选择以 member_id 而非 display name 为准） | ✅（确定性） | T08 契约测试 [test_t08_directed_at_with_same_name_resolves_to_target_member_id](../../../tests/test_book_task_contracts.py) 创建两个共享 "人物甲" 显示名的成员（同 fixture 默认文本），在同房间内 `rounds.submit(mode='directed', target_member_ids=[first_member_id])`，断言 round slot 列表只含目标 member_id、第二成员不得出现；锁住 `coordinator.py:37-49` 中 directed 选择走 `by_id` 字典而非 name 评分的分支；模型调用 0 |

## 3. 关闭验证具体测试

`tests/test_book_feature_flags.py` 现有 8 项测试，对应 T12 "功能关闭后 ... 正常" 条款：

1. `test_config_advertises_effective_disabled_book_features` — 关闭时 GetConfig 返回 4 项全 False
2. `test_disabled_character_entry_does_not_create_build_or_resolve_model` — 关闭时 start_discovery 拒绝并失败 `resolve_discovery_model`
3. `test_disabled_characters_still_allow_source_reading` — 关闭时 read_source 仍返回原文（"人物甲读书。"）
4. `test_feature_dependencies_and_invalid_environment_are_explicit` — 7 种环境组合验证依赖与非 "1" 字符串即关闭
5. `test_release_configuration_is_frozen_until_restart` — 配置必须重启生效，进程内缓存不被环境变量重置
6. `test_disabled_auto_runner_never_scans_or_schedules` — 关闭自动导入时 AutoImportRunner 不扫描/不调度
7. `test_disabled_group_room_keeps_history_and_blocks_model_resolution` — 关闭群聊时 resume_round / reset_memory / set_member:active 全部 `feature_disabled`，历史消息仍可读、epoch=1 不变、轮次 status=paused 不变
8. `test_one_member_group_retains_group_release_policy` — 一人"群聊" 也按 group 策略关闭，不退化为单聊权限

[release-and-rollback.md](../../release-and-rollback.md) 明确：本开关实现与结构行为测试不证明 PDF 阅读、论文蒸馏和普通书籍问答的全部发布兼容性，也不证明原著人格质量；这些仍属于 T12 的最终操作与质量验收。

## 4. 未关闭清单（真实模型质量层）

以下验收项需要真实模型调用，按当前"控制模型调用预算"暂未通过。本索引仅汇总位置和当前已记录证据，不做通过判定。

| 验收项 | 当前状态 | 现有真实模型记录 |
| --- | --- | --- |
| 评测分别报告正确回答与正确拒绝，不用单一拒答率证明效果 | 未关闭 | T06 [2026-10-12-single-chat-validation](./2026-10-12-single-chat-validation.md) 10 次调用；T07 [2026-10-13-room-memory-validation](./2026-10-13-room-memory-validation.md) 7 次；T17 累计 62 次原生 + cognition 4 次 |
| 真实模型质量结论附书籍、模型、配置和样本数量 | 未关闭 | T17 累计 [2026-10-15-discussion-matrix-v2-validation](./2026-10-15-discussion-matrix-v2-validation.md) 26/28 次、10 条人物发布；2 处"历史动作"来源强度警告、1 处超时取消 |
| 验证跨工作区、来源、构建、人物、房间和 epoch 的读写矩阵及删除保留历史 | ✅（已关闭，确定性层） | T11 阶段验证 [2026-10-14-source-lifecycle-validation](./2026-10-14-source-lifecycle-validation.md) + T11 跨工作区矩阵契约测试 [test_t11_cross_workspace_read_write_delete_matrix_preserves_isolation](../../../tests/test_book_task_contracts.py)；6 维矩阵在同一次流程内被覆盖，已移入第 2 节 |
| 同一工作区两部书的单聊、混聊、同名 @、禁言、移除恢复与局部来源删除均纳入验收 | 未关闭 | T08 [2026-10-14-group-room-validation](./2026-10-14-group-room-validation.md) 13 次真实 k3；T09 全体队列 [2026-10-14-all-queue-validation](./2026-10-14-all-queue-validation.md) 新增 0 调用；同名 @ 子项已在确定性层独立关闭，详见第 2 节 |
| 记录每个角色的独立原著准确性与公共听说传播 | 未关闭 | T03 partial_published 1 ready、3 sparse、2 群体待复核；T07 5 个待复核群体回归；T17 累计 62 次中 v9/v14/cognition 审查 v3 报告 [t17-matrix-v2-agent-review.json](./t17-matrix-v2-agent-review.json) `t17_complete=False` / `t12_complete=False` / `quality_pass=False` |
| 秒数设置保存后被真实单聊与全体提问读取 | ✅（已关闭，确定性层） | T15 三项契约测试（[test_book_task_contracts.py](../../../tests/test_book_task_contracts.py) `test_t15_chat_submit_reads_saved_timeout_default_for_directed_mode` / `_for_all_mode` / `_persists_across_database_reopen`）锁住 `agent_defaults.book_room_round_timeout_seconds=91` 与 `book_room_all_round_timeout_seconds=301` → `BookRoomTimeoutSettings.seconds_for_mode(...)` → `rounds.submit` → `book_room_rounds.time_limit_seconds` 的全链路（directed + all 两模式），并验证 SQLite 重开后默认值仍为 91/301；该项确定性证据已落第 2 节"秒数设置保存后被真实单聊与全体提问读取 ✅（确定性）"行 |
| 真实模型评测包含动机/价值两难、情绪触发、参数知识诱导和合理问题过度拒答，并分别报告 | 未关闭 | T17 4 处"历史动作"警告 + 旧 v6 摘录仍语义漏审、v7 范围 1 单元通过；T12 60 项边界与 24 项表达评测未跑 |
| 同模型 A/B 固定书籍/来源/构建、人物、问题序列及可控配置，房间历史独立 | 未关闭 | T17 已完成六组合 26/28 + cognition 2/2；A/B 表达增强在 B 路径有 8 项小预算试验数据但未达完整 24 项 |
| 独立报告人物/别名/说话者/权限/基线标注精度与允许依据召回 | 未关闭 | T03 17 项确定性 + T04 14 项 + 真实 k3 6 次；T17 Agent 审读 [t17-matrix-v2-agent-review.json](./t17-matrix-v2-agent-review.json) `t17_complete=False` |
| 关键越界失败阻止增强默认启用 | ✅（执行）| T06/T12 各阶段记录都明确"增强默认关闭" |
| 关闭表达增强保留同一事实、人设、记忆和有限轮次约束 | ✅（执行）| T06 阶段验证 + v9 review 防护文字冻结 |
| 实际输入/输出 token、调用与重写数、分阶段时延和超时率附对照 | 未关闭 | T17 26/28 次分别记录 token/elapsed；累计 62 次 + 4 次 cognition；分阶段时延按房间记录 |
| 空素材或与 A 无实质输入差异的 B 不计有效表达对照 | ✅（执行）| T05 表达独立构建区分空素材 partial；T06 B 真实调用未计 A 增强 |
| 人物忠实度、当前交流回应和自然程度分别盲评 | 未关闭 | T17 Agent 审读 [t17-matrix-v2-agent-review.json](./t17-matrix-v2-agent-review.json) `quality_pass=False`；人工盲评未启动 |
| 否定自传、遗漏正文断言、他人对白、旧信念和跨书听说都有负例 | 未关闭 | T17 v9 review 与 v14 generate 历史动作防护文字已冻结（85 项 model contracts 第 70–80 项），负例覆盖 v6–v8 |
| 条件推演、引述及有据否定经历有正例 | 未关闭 | T17 cognition 1 题条件选择发布；v12/v8 取得两题有限安全发布 |
| 60 项边界 + 24 项表达完整题集 | 已撰写（金标准 84 题数据层完成；运行层未跑） | 8-pilot 案例集 [t12-quality-cases-v1.json](./t12-quality-cases-v1.json) 仍在线；84 题金标准池已落地为 [t12-quality-cases-v2.json](./t12-quality-cases-v2.json)（dataset_version=t12-pilot-eightyfour-v1，4×15 boundary + 6×4 expression，石猴 57 题 + 黛玉 27 题，含 4 题 cross_book_hearsay）；切片器 [slice_t12_pool.py](../../../scripts/book_world/slice_t12_pool.py) 切成 15+15+15=45 个 8-pilot 窗口，4 个 canonical 窗口已通过 runner `--dry-run`；详见 [2026-10-16-t12-v2-pool-slicer-evidence.md](./2026-10-16-t12-v2-pool-slicer-evidence.md) |
| T12 84 题实际模型运行（先跑 8 项） | 未关闭 | 8-pilot 数据集与 runner 已就位，但模型调用预算未开放；`--dry-run` 是当前唯一允许模式并已验证；8 项小预算运行待 budget 重开后执行 |
| trait-vs-completion 确定性 lint 已接入 persona publication summary | ✅（确定性）| [persona_publication.py](../../../backend/services/book_world/persona_publication.py) 在 `publish_personas` 写 publication step 之前对 accepted trait claim 跑 `trait_completion_overreach`，命中项写入 `publication_report.trait_lint_warnings`；5 项确定性契约测试 [tests/test_persona_publication_trait_lint.py](../../../tests/test_persona_publication_trait_lint.py) 锁住 trait 过强命中 / 对齐 quote 不命中 / episode 同过强措辞不命中 / 必含 `trait_lint_warnings` 键 / 冻结 step IntegrityError 后 SELECT 仍可见，模型调用 0；T17 `remaining_work` 第 1 项的"下次真实 persona 构建触发时以 lint 为预检门禁"已通过本次 wiring 预先落地 |

## 5. 索引如何被引用

- 实施计划 [implementation-plan.md](../../implementation-plan.md) "已验证阶段" 段直接引用本索引的 1 节表格
- T12 任务文件 [tasks/12-mvp-acceptance.md](../../tasks/12-mvp-acceptance.md) 在勾选确定性条目时引用本索引 2 节
- T17 任务文件 [tasks/17-discussion-modes.md](../../tasks/17-discussion-modes.md) 在阶段性"完成记录"末尾引用 4 节"未关闭清单"对应小节
- 发布开关 [release-and-rollback.md](../../release-and-rollback.md) 在"备份与限制"段明确指向本索引 4 节

## 6. 索引变更原则

1. 只增不改：每条新 T12 证据以追加段写入，2/3 节按"已落实"扩展；不删除既有记录
2. 真实模型层只能在跑完对应阶段验证后从 4 节移入 2 节，并在移入处同时更新原任务文件的"完成记录"
3. 关闭的"未关闭"项必须附 t17-matrix-v2-agent-review / t17-cognition-agent-review 重录记录；不允许只改本索引
4. 本索引在 agent-review / 阶段验证 / 测试文件三类来源发生冲突时，以最近一次真实模型运行记录为准
