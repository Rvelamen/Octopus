# 书籍人物 Agent 状态交接（State of Play）

日期：2026-10-16
范围：M1–M4 首版任务中所有可在不消耗模型预算情况下落实的子项
目的：让下一位接手人（或本人下次会话）能直接看到「已完成、待解锁、待条件」三档，避免重新推导

> 2026-10-19纠正：本页旧“0 published”“160行均为石猴”及“唯一外部条件人工盲评”的结论不得用于关闭验收。原始20份报告有159条发布正文（石猴93、黛玉66），新盲评表为94/66；全部来自非全书摘录，160轮表达增强均关闭，两部全书仍queued在发现阶段。统计与身份已修复，仍需完成检索/档案质量、全来源、有效表达A/B和完整应用。当前证据与下一步见[纠正记录](2026-10-19-t12-evidence-correction.md)及[新盲评表](blind-review-2026-10-19-worksheet.csv)，旧段落保留作历史，不代表当前验收结论。

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
| T12 题集 + 切片器 + 6 类负例防护 + 11 类人物/别名/说话者/权限/基线/隔离 + 3 类禁言/移除恢复/局部来源删除 + 6 类金标准池结构完整性 + 6 类 8-pilot 接线契约 + 4 类 frozen dryrun 审计 trail + 8 类 runner 脚本结构不变量确定性聚合 + 8-pilot 真实模型运行（首档 8/8 case 走完）+ 60+24 真实模型运行（84 题金标准 100% 落地 152/152 case 走完） | [2026-10-16-t12-v2-pool-slicer-evidence.md](./2026-10-16-t12-v2-pool-slicer-evidence.md) + [2026-10-16-t12-8pilot-real-run-evidence.md](./2026-10-16-t12-8pilot-real-run-evidence.md) + [2026-10-16-t12-v2-real-run-evidence.md](./2026-10-16-t12-v2-real-run-evidence.md) | 9073987 / bcced1d / 75f2af2 / 589db8e / c57594d / 57558c7 / fb395eb / 7319c0c / (本批次) / 7960170 / 63fd1e3 / 70443bf / 27cb369 / f4c0279 / ea2738e | 84 题金标准 + 45 窗口 + 87 负例 + 42 人物/别名 + 6 禁言/移除恢复/局部来源删除 + 6 金标准池结构完整性 + 6 8-pilot 接线契约 + 4 frozen dryrun 审计 trail + 8 runner 脚本结构不变量（含 v1ext 协议扩展） + 1 8-pilot 真实模型运行（23/32 native calls、6/8 over-decline）+ 1 v2 60+24 真实模型运行（19 窗口 152/152 case 走完、369 native calls、0 published、19/19 baseline 不变，runner v1ext 协议扩展后 SHA `35fd8681`） |
| T12 人工盲评 CLI + 协议 + worksheet + 报告模板 + 操作卡 | [2026-10-16-blind-review-protocol.md](./2026-10-16-blind-review-protocol.md) + [blind-review-cli.py](../../blind-review-cli.py) + [blind-review-2026-10-16-worksheet.csv](./blind-review-2026-10-16-worksheet.csv) + [2026-10-16-t12-blind-review-cli-e2e-evidence.md](./2026-10-16-t12-blind-review-cli-e2e-evidence.md) + [2026-10-16-t12-blind-review-report-template.md](./2026-10-16-blind-review-report-template.md) + [2026-10-16-t12-blind-review-operator-card.md](./2026-10-16-t12-blind-review-operator-card.md) | e0f4b3f / c103a62 / 391aaa8 / (本批次) | 6 子命令 start/resume/stats/worksheet/import/regrade（`import` 为离线 CSV 路径）+ 报告模板（8 节：审阅者 / 审阅时间 / stats / 关键评论 / 已知异常 / 与 §4 行衔接 / 不变量 / §4 行更新清单）+ 82 行操作卡（4 路径：交互式最短 / 离线 CSV / regrade / 报告）；160 case（8-pilot 8 + v2 152，含 1 已知 timeout case 已标注）；模型调用 0 / 不动 baseline / 不动既有 40 项 T12 契约测试；端到端 e2e 验证（commit c103a62 同步修复 v1ext runner-accept 测试幂等性 + commit 25ca27a 同步注册工具于 §1/§2/§4）已完成：3 case 真实跑通 start → quit → resume → stats → regrade 链路，临时输出已清理 |
| T15 秒数设置 | (无独立验证文档) | e29231c | 3 契约测试 |
| T16 圆桌 UI | [2026-10-14-roundtable-validation](./2026-10-14-roundtable-validation.md) | (历史提交) | WS 3D + 2D 切换 |
| T17 主题/自由 | [2026-10-15-discussion-matrix-v2-validation](./2026-10-15-discussion-matrix-v2-validation.md) + cognition 修复 | 70eed8e / 0e87b78 / 24d1959 | 26/28 + lint 门 |
| T18 TXT 图书馆 | 与 T01 同一来源链 | (历史提交) | — |

最近 10 个 commit（`git log --oneline -10`）：

```
e96f800 docs(t12): log 2026-10-19 compound-anchor supply-layer fix in implementation plan + reconcile validation doc
588b2be fix(knowledge): pin CJK compounds ahead of trigrams in 32-slot query budget
3e1570d fix(t12): derive publication and reviewer identities from run records
88e3df4 docs(t12): fix operator card §4 row count 12→11 (T15 closure) + add report template to ready list
3ebd637 docs(t12): add 盲评完成报告模板 + 操作卡/状态交接/实施计划同步
af508b2 docs(state): mark 60+24 real-model run as completed in state-of-play §4 (was stale '未跑')
391aaa8 docs(t12): add blind review operator card + fix worksheet link path
85c594a feat(t12+t17): extract published body content for A/B + cognition slots
54f621b feat(t12+t17): extend aggregation to include T17 A/B + cognition pilot
91616ea feat(t12): aggregate 8-pilot + v2 real-runs into one consumable evidence table
```

分支：`feature/pdf-annotation-chat-and-clip-fix`（已推送远端，与 `main` 同步无冲突）
完整项目 pytest：**652 通过 / 13 跳过**（13 跳过为既有 Playwright 缺失；625 → 651 = T05 检索侧供给层回归修复新增 2 项 + 既有多批次补 24 项 + 桥化合物追加 1 项 = 652；最近 1 个失败=0）

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
14. **2026-10-19 检索侧供给层修复**（commit 588b2be）
   - 文件：[2026-10-19-compound-anchor-bugfix.md](./2026-10-19-compound-anchor-bugfix.md) + 实施计划 §当前交付状态同步
   - 在 [tests/test_book_knowledge.py](../../../tests/test_book_knowledge.py) 末尾追加 3 项契约测试：`test_long_query_retains_compound_anchor_and_identifier_within_term_budget` / `test_long_question_keeps_bridge_compound_in_top_32_slots` / `test_long_question_recalls_owned_episode_without_granting_it_to_another_person`；锁住 32 槽预算下 2 字/2-3 字 CJK 化合物（`瀑布`/`桥下`/`key9`）排在 3 字 trigram 之前的次序。解决第一题可知桥梁的检索供给层失败（之前 8-pilot 真实跑 6 行 `reader_evidence` 命中但 episode 行 `approved_excerpt=''` 触发模型退拒），仅排序逻辑改动、索引与允许集未动、模型调用 0；剩余 2 层待办（按 [证据纠正 §首版仍未闭合的实际条件](./2026-10-19-t12-evidence-correction.md)）：(1) 原著档案命题完整度——铁板桥段落命题当前不含"桥下之水冲贯于石窍" / "倒挂流出去遮闭桥门"，而全文在 `tmp/book-corpus/西游记.txt:33`；(2) 模型对 `approved_excerpt=''` episode 的安全回退策略——若不打开"可凭 episode 命题作答"开关或补 quote 仍会退拒。两层均需真实模型预算授权。

## 3. 待解锁：模型预算授权

| 阻塞项 | 解除条件 | 解除后立即可做 | 预计预算 | 状态 |
| --- | --- | --- | --- | --- |
| T12 8-pilot 真实模型跑 | 开放 `kimi-coding-plan · K3` provider 授权 + 设定模型调用预算 | 在 4 个 canonical 窗口跑完 8-pilot；按 `--real` 模式记录 token/elapsed；与 dry-run 比对 | 小（≤ 50 次调用） | ✅ 2026-10-16 跑完，23/32 native calls，8/8 case 走完 `executed_pending_semantic_review`，6/8 over-decline 诊断记录于 [2026-10-16-t12-8pilot-real-run-evidence.md](./2026-10-16-t12-8pilot-real-run-evidence.md) |
| T12 60+24 真实跑 | 同上 + 接受更长时间窗 | 切 15 canonical 窗口跑 60+16=76 runner-兼容 case + 4 ext-a 窗口跑 4 disagree + 4 unknown_expression=8 extension case | 中（~180-360 次，depends on review-retry） | ✅ 2026-10-16 跑完，152 case / 369 native call / 0 published / 0 budget_exhausted / 19/19 windows baseline 不变；runner v1ext 协议扩展（commit `f4c0279`）+ 5 份 frozen dryrun 报告重生成对齐 runner SHA `35fd8681`；84 题金标准 100% 真实模型跑过（60 boundary + 24 expression），诊断记录于 [2026-10-16-t12-v2-real-run-evidence.md](./2026-10-16-t12-v2-real-run-evidence.md) |
| T17 matrix v2 A/B 重评 | 同上 | 同 baseline 独立干净房间重跑 6 组合作为 B 路径，与 A 路径（[real-model-t17-matrix-v2.json](./real-model-t17-matrix-v2.json) 26/28 既有）对比验证 v9/v14 + trait lint 门禁下行为稳定性 | 小（~28 次） | ✅ 2026-10-16 跑完，B 路径 [real-model-t17-matrix-v2-ab.json](./real-model-t17-matrix-v2-ab.json) 20/28 native calls、6/6 case 走完 `executed_pending_semantic_review`、0 published、baseline c2da28c8/58609a52 不变；A vs B 6 组合行为形状 100% 一致（公开称呼 / 拒绝诱导 / 区分假设 / 追问限制在公开信息内），B 路径收敛更快（20 vs 26 call = v9 审查无 retry 一次否决），trait_completion_overreach 在 free-directed + free-all 2 case 两路径都仍触发由 v9 审查拒（生成侧无法在不修改基线的前提下防止该措辞出现）；详细对比见 [2026-10-16-t17-v2-ab-reeval-evidence.md](./2026-10-16-t17-v2-ab-reeval-evidence.md) |
| 人工盲评 | T12 真实跑数据落地后 | 对 8-pilot × 8 case = 8 条已发布人物回复（7 成功发布 + 1 review 失败未发布）+ 60+24 × 152 case 中按 §4 抽样忠实度/表达自然度盲评 | 人工（不计预算） | 已具备输入 + 工具（[blind-review-cli.py](../../blind-review-cli.py) + [2026-10-16-blind-review-protocol.md](./2026-10-16-blind-review-protocol.md) + [blind-review-2026-10-16-worksheet.csv](./blind-review-2026-10-16-worksheet.csv) + [2026-10-16-t12-blind-review-report-template.md](./2026-10-16-blind-review-report-template.md) + [2026-10-16-t12-blind-review-operator-card.md](./2026-10-16-t12-blind-review-operator-card.md)，commit `e0f4b3f` / `391aaa8` / 本批次）：8-pilot + 60+24 共 160 case 落地，0 published 全部进入人工盲评队列；6 子命令 start/resume/stats/worksheet/import/regrade 全部可用（其中 `import` 为离线 CSV 路径，方便 Excel 党），待人工启动 `python docs/plans/book-character-agents/blind-review-cli.py start --reviewer <name>`；1 已知 timeout case `expression-comfort-stone-to-failed-peer` 已按 over_decline 标注；完成后按模板 [2026-10-16-blind-review-report-template.md](./2026-10-16-blind-review-report-template.md) 写报告 [2026-10-16-blind-review-report.md](./2026-10-16-blind-review-report.md)，再按协议 §6 把 T12 验收索引 §4 row 1 / row 5 / row 9 改写为「✅（人工盲评 160/160 判定完成）」 |

**不变量**：所有待跑项都不会触碰已发布 canonical baseline；trait lint 已在 24d1959 落入门禁。

## 3.1 不需模型预算：操作员 / 评审员即可推进

[2026-10-19 五门分项执行版](2026-10-19-t12-five-remaining-gates.md) 把 5 个未闭合条件按"不需预算 / 需真实模型预算 / 需人工"三档分类。本节承接其中不需模型预算的两门（门 D / 门 E），便于操作员/评审员在 0 模型调用下推进首版验收。

| 阻塞项 | 解除条件 | 解除后立即可做 | 状态 |
| --- | --- | --- | --- |
| 门 D — 完整应用 E2E | 启动 1 用户 1 角色 1 房间的人工 E2E 跑通 | 创建 `tmp/accept-e2e-workspace`，按 [release-and-rollback.md](../../release-and-rollback.md) 启动 4 个环境变量全开，跑通"上传 TXT → 自动导入 build → 单聊 + 全体"；提交 1 份 E2E 报告作为首版"操作验收"关闭证据 | 未启动；当前 `tests/` 全部 665 项契约测试 + 3 个前端集成场景覆盖 T01–T11 / T15 / T16 / T17 链路与确定性层，8 项 [test_book_feature_flags.py](../../../tests/test_book_feature_flags.py) + 1 项 [release-gates-validation](./2026-10-14-release-gates-validation.md) 锁定功能开关 + 关闭流程的确定性；T16 WS 3D / 2D 切换 / 历史气泡 / 右栏同 ID/seq/正文 / 证据操作 已在 [2026-10-14-roundtable-validation](./2026-10-14-roundtable-validation.md) 落实；T09 暂停/继续/停止 + 首次工作区恢复 + 过期租约 + 有效生成占位 + 增量重连 已在 [2026-10-14-all-queue-validation](./2026-10-14-all-queue-validation.md) 落实 |
| 门 E — 160 case 人工盲评 | 评审员姓名 + 评审方式（交互式 CLI / 离线 CSV）+ 30 分钟时间窗 | 评审员 1: 运行 `python docs/plans/book-character-agents/blind-review-cli.py start --reviewer <name>`；评审员 2 (Excel 党): `worksheet` 导出 CSV → 离线填写 → `import` 导入；完成后按 [2026-10-16-blind-review-report-template.md](./2026-10-16-blind-review-report-template.md) 写报告 [2026-10-16-blind-review-report.md](./2026-10-16-blind-review-report.md)；按 [协议 §6](./2026-10-16-blind-review-protocol.md) 把 T12 验收索引 §4 row 1 / row 5 / row 9 改写为「✅（人工盲评 160/160 判定完成）」 | 工具与数据就绪：6 子命令 start/resume/stats/worksheet/import/regrade 全部可用；[blind-review-2026-10-19-worksheet.csv](./blind-review-2026-10-19-worksheet.csv) 160 case（94 石猴 + 66 黛玉）18 列已就位；1 已知 timeout case `expression-comfort-stone-to-failed-peer` 已按 over_decline 标注；端到端 e2e 验证（[2026-10-16-t12-blind-review-cli-e2e-evidence.md](./2026-10-16-t12-blind-review-cli-e2e-evidence.md)）3 case 真实跑通 start → quit → resume → stats → regrade 链路，临时输出已清理 |

补充说明：

- 两门与 §3 的 4 个真实模型跑（8-pilot / 60+24 / T17 A/B / 隐式第四项）独立，可并行推进：门 D 与门 E 不消耗预算、且不依赖 §3 中任何一项。
- 门 D 的最小落地形态是 1 份不超过 1 页的 E2E 报告，按 "上传 TXT → build → persona → 单聊 → 圆桌 → 暂停/继续" 6 步叙述；不需要再次跑全套真实模型。
- 门 E 的评审员姓名出现在盲评 JSON 文件名后缀；评审员不必是项目成员，0 模型调用门槛下任何 1 名评审员在 30 分钟内可完成。
- 两门落地后，按 [2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md) §6 "只增不改" 原则，T12 验收索引 §4 row 1 / row 5 / row 9 与 [implementation-plan.md §当前交付状态](../../implementation-plan.md) 第 295 行附近的"首版验收"行才改为「✅」。

## 4. 超出本次范围（不会在首版中实现）

| 项 | 原因 | 评估 |
| --- | --- | --- |
| T04 修订机制新增 `rephrase_claim` 类操作 | T17 诊断明确标"超出本次范围" | 若未来仍需对现存 build `c2da28c8` 产出修订版，需先扩展操作集，再以 lint 为 review 一侧的预检；该扩展与本次 wiring 互不阻塞 |
| T17 cognition 第 3 题（条件推演 · 复杂分支） | 现有真实模型调用未稳定通过 | 待 v9 防护文字冻结后下次真实跑复评 |
| 60+24 真实跑（运行层） | 已完成（2026-10-16 跑完 152/152 case） | 84 题金标准 100% 真实模型跑过（60 boundary + 16 canonical expression + 4 ext-a disagree + 4 ext-a unknown_expression = 84 题），19 窗口 / 369 native calls / 0 published / 19/19 baseline 不变，详见 §3 第 2 行 + [2026-10-16-t12-v2-real-run-evidence.md](./2026-10-16-t12-v2-real-run-evidence.md)；本行原条目"阻塞于预算；仅运行层未跑"系 2026-10-16 真实跑落地前留下，按"只增不改"原则保留旧描述并以新行覆盖"

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
