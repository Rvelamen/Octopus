# 书籍人物 Agent 状态交接（State of Play）

日期：2026-10-16
范围：M1–M4 首版任务中所有可在不消耗模型预算情况下落实的子项
目的：让下一位接手人（或本人下次会话）能直接看到「已完成、待解锁、待条件」三档，避免重新推导

## 1. 已完成（确定性层，全部已 commit + push）

| 任务 | 验证位置 | 关键提交 | 备注 |
| --- | --- | --- | --- |
| T01 来源准备 | [2026-10-12-source-validation](./2026-10-12-source-validation.md) | (历史提交) | 51 通过 |
| T02 人物候选 | [2026-10-12-discovery-validation](./2026-10-12-discovery-validation.md) | (历史提交) | 77 通过 / 13 跳过 |
| T03 原著档案 | [2026-10-12-persona-validation](./2026-10-12-persona-validation.md) | (历史提交) | 94 通过 |
| T04 证据纠错 | [2026-10-12-revision-validation](./2026-10-12-revision-validation.md) | (历史提交) | 108 通过 |
| T05 知情与表达 | [2026-10-12-knowledge-expression-validation](./2026-10-12-knowledge-expression-validation.md) | (历史提交) | 124 通过 |
| T06 受限单聊 | [2026-10-12-single-chat-validation](./2026-10-12-single-chat-validation.md) | (历史提交) | 154 通过 |
| T07 房间记忆 | [2026-10-13-room-memory-validation](./2026-10-13-room-memory-validation.md) | (历史提交) | 172 通过 |
| T08 跨书多人 | [2026-10-14-group-room-validation](./2026-10-14-group-room-validation.md) | (历史) + (本批次) | 13 真实 k3 + 1 同名 @ 契约 |
| T09 全体与控制 | [2026-10-14-all-queue-validation](./2026-10-14-all-queue-validation.md) | (历史提交) | 暂停/继续/停止 |
| T10 自动导入 | [2026-10-14-automatic-import-validation](./2026-10-14-automatic-import-validation.md) | (历史提交) | 199 通过 |
| T11 来源生命周期 + 跨工作区矩阵 | [2026-10-14-source-lifecycle-validation](./2026-10-14-source-lifecycle-validation.md) + 矩阵契约测试 (本批次) | (历史) + (本批次) | 9 lifecycle + 1 矩阵 |
| T12 题集 + 切片器 + 6 类负例防护 + 11 类人物/别名/说话者/权限/基线/隔离 + 3 类禁言/移除恢复/局部来源删除 + 6 类金标准池结构完整性 + 6 类 8-pilot 接线契约 + 4 类 frozen dryrun 审计 trail + 8 类 runner 脚本结构不变量确定性聚合 + 8-pilot 真实模型运行（首档 8/8 case 走完） | [2026-10-16-t12-v2-pool-slicer-evidence.md](./2026-10-16-t12-v2-pool-slicer-evidence.md) + [2026-10-16-t12-8pilot-real-run-evidence.md](./2026-10-16-t12-8pilot-real-run-evidence.md) | 9073987 / bcced1d / 75f2af2 / 589db8e / c57594d / 57558c7 / fb395eb / 7319c0c / (本批次) / 7960170 / 63fd1e3 / 70443bf / 27cb369 | 84 题金标准 + 45 窗口 + 87 负例 + 42 人物/别名 + 6 禁言/移除恢复/局部来源删除 + 6 金标准池结构完整性 + 6 8-pilot 接线契约 + 4 frozen dryrun 审计 trail + 8 runner 脚本结构不变量聚合 + 1 8-pilot 真实模型运行（23/32 native calls、6/8 over-decline） |
| T15 秒数设置 | (无独立验证文档) | e29231c | 3 契约测试 |
| T16 圆桌 UI | [2026-10-14-roundtable-validation](./2026-10-14-roundtable-validation.md) | (历史提交) | WS 3D + 2D 切换 |
| T17 主题/自由 | [2026-10-15-discussion-matrix-v2-validation](./2026-10-15-discussion-matrix-v2-validation.md) + cognition 修复 | 70eed8e / 0e87b78 / 24d1959 | 26/28 + lint 门 |
| T18 TXT 图书馆 | 与 T01 同一来源链 | (历史提交) | — |

最近 10 个 commit（`git log --oneline -10`）：

```
27cb369 test(t12): add runner coerce mode=natural→directed when targets set (8th guard)
70443bf test(t12): pin runner expected_count 4+4 class list against v1 protocol
14499b7 docs(t12): include 63fd1e3 in recent-10 list + bump runner guards 4→6 (validate_dataset 强校验)
63fd1e3 test(t12): add 2 more runner structural guards (manual_continues_per_turn + reviewer_kind)
228795f docs(state): correct full-suite count to 621/13 (post-runner-guards)
2cc08e4 docs(t12): include 7960170 in recent-10 list + add 4 runner 脚本结构不变量 as guard #13
7960170 test(t12): pin 4 runner-code structural invariants (call ceiling + overwrite guard + terminal status enum)
3d6d251 docs(state): include 1076ded in recent-10 list + add 4 dryrun 审计 trail as guard #12
1076ded test(t12): pin 4 frozen dryrun report audit-trail integrity (4 guards)
af9609c docs(state): include 7319c0c/fb395eb in recent-10 list + add 84-题池/8-pilot 接线契约 as guards #10/#11
```

分支：`feature/pdf-annotation-chat-and-clip-fix`（已推送远端，与 `main` 同步无冲突）
完整项目 pytest：**625 通过 / 13 跳过**（13 跳过为既有 Playwright 缺失；624 → 625 = 新增 1 项 T12 runner `mode=natural→directed` coerce 契约测试）

## 2. 当前确定性已锁定的"隐形护栏"

这些不是新功能，但在预算解锁后会让真实模型跑变得安全可审计：

1. **trait-vs-completion lint** 接入 `publish_personas`（commit 24d1959）
   - 文件：`backend/services/book_world/proposition_alignment.py` + `persona_publication.py:132-165`
   - 5 项契约测试：`tests/test_persona_publication_trait_lint.py` 全部通过
   - 下次真实构建首次触发即对外暴露 `trait_lint_warnings`，可作为 review 端门禁
2. **T15 秒数设置 read-path** 已锁（commit e29231c）
   - 3 项契约测试覆盖 directed + all 模式 + DB reopen
   - 文件：`tests/test_book_task_contracts.py` 末尾
   - 真实单聊/全体提问未来跑时，秒数不会再悄悄回到默认
3. **金标准 84 题池 + 切片器** 已落地（commit 9073987）
   - 文件：`docs/plans/book-character-agents/validation/t12-quality-cases-v2.json` + `scripts/book_world/slice_t12_pool.py`
   - 4 个 canonical 窗口已通过 runner `--dry-run`，数据层就绪
4. **T17 cognition 防护文字冻结**（85 项 model contracts 第 70–80 项）
   - `tests/test_book_model_contracts.py` 已锁 v9/v14/cognition 防护
5. **T11 跨工作区 6 维读写删矩阵** 已锁（commit f129ba7）
   - 文件：`tests/test_book_task_contracts.py` 末尾 `test_t11_cross_workspace_read_write_delete_matrix_preserves_isolation`
   - 6 维（workspace × source × build × character × room × epoch）一次性覆盖；删 A 不影响 B 行数与 room 状态
6. **T08 同名 @ directed 选择以 member_id 为准** 已锁（commit 3dc3d88）
   - 文件：`tests/test_book_task_contracts.py` 末尾 `test_t08_directed_at_with_same_name_resolves_to_target_member_id`
   - 锁住 `coordinator.py:37-49` 的 `by_id` 字典；两个 "人物甲" 不会因为名字相同而被错投
7. **T12 6 类负例防护确定性聚合** 已索引（commit 589db8e）
   - 文件：T12 验收证据索引 §2 新增"否定自传、跨书听说、遗漏正文、他人对白、旧信念都有负例防护"行
   - 87 项 `tests/test_book_model_contracts.py` 已被映射到 6 类（用户否认 15 / 旧信念 5 / 遗漏正文 12+1 / 沉默保留 9 / 防护 wording 4 / review 不可削弱 body 5 + 35 未参数化 = 87）
8. **T03/T04/T09 11 类人物/别名/说话者/权限/基线/隔离确定性聚合** 已索引（commit c57594d）
   - 文件：T12 验收证据索引 §2 新增"人物/别名/说话者/权限/基线标注精度/依据召回/历史 vs 当前/跨书源隔离（确定性层）"行
   - 17 (T03) + 18 (T04，含 4+3 参数化) + 7 (T09) = 42 项既有测试被映射到 11 类子项
9. **T09/T11 禁言/移除恢复/局部来源删除确定性聚合** 已索引（commit 57558c7）
   - 文件：T12 验收证据索引 §2 新增"同一工作区两部书的禁言/移除恢复/局部来源删除（确定性层）"行
   - 2 (禁言 T09) + 3 (移除恢复 T09) + 1 (局部来源删除 T11 矩阵) = 6 项既有测试被映射到 3 类子项
10. **84 题金标准池结构完整性确定性聚合** 已索引（commit fb395eb）
   - 文件：T12 验收证据索引 §2 新增"84 题金标准池结构完整性（确定性层）"行
   - 在 [tests/test_t12_question_set.py](../../../tests/test_t12_question_set.py) 末尾追加 6 项数据层不变量测试：`test_v2_pool_actor_indices_match_book_ids` / `_question_and_expected_lengths_match_runner` / `_boundary_verdict_equals_class` / `_tier_breakdown_totals_match_cases` / `_metadata_freeze_fields_are_present` / `_gold_standard_verdict_uses_protocol_vocabulary`；前 15 项切片器/wiring 既有测试保持不变，合计 21 项契约测试；actor↔book 配对 / question 长度 / boundary verdict=class / tier_breakdown 合计 / metadata 冻结字段 / verdict 词汇 6 类不变量 100% 在确定性层独立关闭
11. **T12 8-pilot 数据集结构完整性确定性聚合** 已索引（commit 7319c0c）
   - 文件：T12 验收证据索引 §2 新增"T12 8-pilot 数据集结构完整性（确定性层）"行
   - 在 [tests/test_t12_question_set.py](../../../tests/test_t12_question_set.py) 末尾追加 6 项接线契约测试：`test_v1_dataset_has_exactly_8_cases` / `_class_set_matches_canonical_protocol` / `_one_case_per_class` / `_covers_both_characters_and_both_books` / `_metadata_freeze` / `_pool_v2_slicing_round_trip`；前 21 项切片器/wiring/v2 既有测试保持不变，合计 27 项契约测试；8 case / 4+4 canonical class / 每类 1 case / 双人物双书 / dataset_version=8-pilot / ceiling=32 / v2→window 0 round-trip 7 类不变量 100% 在确定性层独立关闭
12. **4 份 frozen dryrun 报告审计 trail 完整性确定性聚合** 已索引（commit 1076ded）
   - 文件：T12 验收证据索引 §2 新增"4 份 frozen dryrun 报告审计 trail 完整性（确定性层）"行
   - 在 [tests/test_t12_question_set.py](../../../tests/test_t12_question_set.py) 末尾追加 4 项契约测试：`test_dryrun_reports_all_canonical_windows_present` / `_carry_v1_wire_contract` / `_runner_sha256_matches_runner_file` / `_each_window_has_distinct_dataset_sha`；前 27 项切片器/wiring/v2/v1 既有测试保持不变，合计 31 项契约测试；4 份报告齐 / v1 wire contract / runner SHA 一致 / 4 份 dataset SHA 互异 4 类不变量 100% 在确定性层独立关闭
13. **T12 runner 脚本结构不变量确定性聚合** 已索引（commit 7960170 / 63fd1e3 / 70443bf）
   - 文件：T12 验收证据索引 §2 新增"T12 runner 脚本结构不变量（确定性层）"行
   - 在 [tests/test_t12_question_set.py](../../../tests/test_t12_question_set.py) 末尾追加 7 项契约测试：`test_runner_max_native_calls_constant_is_32` / `_call_budget_default_matches_ceiling` / `_refuses_to_overwrite_existing_output` / `_run_status_terminal_enum_covers_all_paths` / `_validate_dataset_enforces_manual_continues_per_turn_equals_one` / `_validate_dataset_enforces_reviewer_kind_match` / `_expected_count_class_list_matches_v1_protocol`；前 31 项切片器/wiring/v2/v1/dryrun 既有测试保持不变，合计 38 项契约测试；`MAX_NATIVE_CALLS=32` / `--call-budget` 默认 32 / 拒绝覆盖现有 output / 4 个 `run_status` 终态枚举齐 / `manual_continues_per_turn` 强校验 1 / `reviewer_kind` 显式非盲评 / `expected_count` 4+4 class 列表与 v1 协议对齐 7 类不变量 100% 在确定性层独立关闭；不依赖任何 frozen dryrun 报告存在与否，dryrun 报告丢失/重新生成后仍生效

## 3. 待解锁：模型预算授权

| 阻塞项 | 解除条件 | 解除后立即可做 | 预计预算 | 状态 |
| --- | --- | --- | --- | --- |
| T12 8-pilot 真实模型跑 | 开放 `kimi-coding-plan · K3` provider 授权 + 设定模型调用预算 | 在 4 个 canonical 窗口跑完 8-pilot；按 `--real` 模式记录 token/elapsed；与 dry-run 比对 | 小（≤ 50 次调用） | ✅ 2026-10-16 跑完，23/32 native calls，8/8 case 走完 `executed_pending_semantic_review`，6/8 over-decline 诊断记录于 [2026-10-16-t12-8pilot-real-run-evidence.md](./2026-10-16-t12-8pilot-real-run-evidence.md) |
| T12 60+24 真实跑 | 同上 + 接受更长时间窗 | 切 15 canonical 窗口跑 60+16=76 runner-兼容 case + 2 v1-extension 窗口跑 4 disagree + 4 unknown_expression=8 extension case | 中（~180-360 次，depends on review-retry） | 阻塞：runner 当前拒绝 `dataset_version=t12-pilot-eight-v1-ext`；需扩展 runner 后跑 |
| T17 matrix v2 A/B 重评 | 同上 | 用修正后 baseline（`rephrase_claim` 修订）重跑 matrix，预期 `topic-natural-retained-topic` 与 `topic-directed-rephrased-dilemma` 从 limited_behavior_pass 提升 | 小（~28 次） | 阻塞 |
| 人工盲评 | T12 真实跑数据落地后 | 对 8-pilot × 8 case = 8 条已发布人物回复（7 成功发布 + 1 review 失败未发布）做忠实度/表达自然度盲评 | 人工（不计预算） | 已具备输入 |

**不变量**：所有待跑项都不会触碰已发布 canonical baseline；trait lint 已在 24d1959 落入门禁。

## 4. 超出本次范围（不会在首版中实现）

| 项 | 原因 | 评估 |
| --- | --- | --- |
| T04 修订机制新增 `rephrase_claim` 类操作 | T17 诊断明确标"超出本次范围" | 若未来仍需对现存 build `c2da28c8` 产出修订版，需先扩展操作集，再以 lint 为 review 一侧的预检；该扩展与本次 wiring 互不阻塞 |
| T17 cognition 第 3 题（条件推演 · 复杂分支） | 现有真实模型调用未稳定通过 | 待 v9 防护文字冻结后下次真实跑复评 |
| 60 项边界 + 24 项表达完整题集的真实跑 | 阻塞于预算 | 题集已撰写为 [t12-quality-cases-v2.json](./t12-quality-cases-v2.json)；仅运行层未跑 |

## 5. 接手人下一步操作清单

按用户"持续推进下一项已满足依赖的任务"指令和"不修改任何签名、不消耗预算"约束：

1. **若预算已解锁**：直接按 [2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md) §4 表格顺序执行 8-pilot → 60+24 → A/B 三档真实跑；每档独立 git commit + runner 输出保存
2. **若预算未解锁**：所有确定性已就绪；任何"未关闭"项均无法在零预算下推进；停止本分支工作并向用户回报状态
3. **若发现新问题**：在 `validation/` 下新建 `YYYY-MM-DD-<short-name>.md`，按"只增不改"原则追加到 T12 验收索引 §2/§4；不在实施计划里改写既有记录

## 6. 关键文档路径

- 实施计划：[docs/plans/book-character-agents/implementation-plan.md](../../implementation-plan.md)
- 详细设计：[docs/plans/book-character-agents/detailed-design.md](../../detailed-design.md)
- 任务清单：[docs/plans/book-character-agents/tasks/](../../tasks/)
- 验证记录：[docs/plans/book-character-agents/validation/](./)
- 验收索引：[2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md)
- 发布开关：[docs/plans/book-character-agents/release-and-rollback.md](../../release-and-rollback.md)
- 阶段验证（每任务）：同 `validation/` 目录
- 真实模型记录：`t17-matrix-v2-agent-review.json`、`t17-cognition-agent-review.json`
- 诊断与 lint：[2026-10-16-t17-trait-completion-diagnosis.md](./2026-10-16-t17-trait-completion-diagnosis.md)

## 7. 预算与不变量自检

- 模型调用：0（本 commit 链不消耗任何 provider 调用）
- canonical_baselines_unchanged：True
- 新增代码：纯函数 + 单元测试，可独立审查、可回滚
- 现有 API 签名变更：0（`rounds.submit` / `BookRoomTimeoutSettings` / `AgentDefaultsRepository` / `publish_personas` 全部不变）
- 发布开关：未变更（4 个环境变量与 [release-and-rollback.md](../../release-and-rollback.md) 一致）
- 文档原则：只增不改（按 [2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md) §6）
