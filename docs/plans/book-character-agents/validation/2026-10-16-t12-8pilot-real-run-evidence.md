# T12 8-pilot 真实模型运行 — 执行证据

日期：2026-10-16
范围：在 kimi-coding-plan · K3（provider_id=2, model_record_id=337, reasoning_effort=low, max_tokens=4096）上对 T12 8-pilot 真实题集执行 runner 真实（非 dry-run）模式；与 [2026-10-16-t12-8pilot-real-preview-dryrun.json](./2026-10-16-t12-8pilot-real-preview-dryrun.json) 同一 dataset / 同一 actor / 同一 SHA 锁定。

## 1. 运行参数

- **runner_sha256**: `55783a63261c8be7da02c08b8a930761c8a454c35baf106c21aa14522352adbb`（含 `mode=natural → directed` 自动协调，详见后述）
- **dataset_sha256**: `2647a18db9afecf3acb4c81889b3b48e3a00e41f6733e78044ca81bfea358fb8`（= 8-pilot v1 dataset SHA）
- **actors_source_sha256**: `4361f5ae1bb93f4414c876c48e3a4cb54df8c1c3d823b8febda1e0653a9e4c71`（= probe persona 文件 SHA）
- **call_budget**: 32（= MAX_NATIVE_CALLS）
- **actual_native_calls**: 23（占预算 71.9%）
- **run_status**: `executed_pending_semantic_review`
- **canonical_baselines_unchanged**: True（`before == after == 89f5f44628...`）
- **run_error_type**: None
- **budget_exhausted**: False
- **quality_pass**: False（待人工盲评语义层；runner 不声称通过）
- **report**: [2026-10-16-t12-8pilot-real-run.json](./2026-10-16-t12-8pilot-real-run.json)
- **native_calls log**: [2026-10-16-t12-8pilot-real-run-native.json](./2026-10-16-t12-8pilot-real-run-native.json)

## 2. 修复：runner `mode=natural` 冲突 (commit 27cb369)

8-pilot 第一次运行（[b86hqq0be]）在第一个 case 提交时崩溃：`coordinator.py:51` 抛 `BookWorldError("invalid_request", "Natural selection cannot carry directed targets")`。原因：每条 v1 case 都有 `target_actor_indices: [0]` 或 `[1]`（指定说话者）+ `mode: "natural"`（自由轮转）。两个字段在 `coordinator.select_speakers` 互斥——`mode=natural` 时禁止带 `target_member_ids`。

修复（commit 27cb369）：

- `docs/plans/book-character-agents/t12-quality-runner.py` 在 `rounds.submit` 前引入 `effective_mode`，当 `target_actor_indices` 产生非空 `targets` 时把 `effective_mode` 从 `"natural"` 强制升级为 `"directed"`，`rounds.submit` 和 `rounds.control("resume", ...)` 都用 `effective_mode`。
- 新增 14 号守卫 `test_runner_coerces_mode_to_directed_when_target_actor_indices_set` 锁住 effective_mode 的派生逻辑、coerce 分支、submit 与 resume 两处使用。
- 重新生成 5 份 dryrun 报告（8-pilot preview + 4 个 canonical windows）使其 `runner_sha256` 与新 runner 一致（`55783a63...`）。
- 总契约测试数：38 → 39。
- 0 次模型调用，canonical baseline 未变，签名（`rounds.submit` / `BookRoomTimeoutSettings` / `AgentDefaultsRepository`）未动。

修复后第二次运行（[bko8czfdk]）成功完成 8/8 case。

## 3. 8/8 case 终态

| case_id | tier | class | status | 模式 | 已发布 | 是否含 canon 答案 |
| --- | --- | --- | --- | --- | --- | --- |
| boundary-knowable-stone-discovery | boundary | knowable | executed_pending_semantic_review | directed | 1 | ❌ over-decline（应说"铁板桥/桥后石洞/无水无波"） |
| boundary-unknowable-daiyu-private-motive | boundary | unknowable | executed_pending_semantic_review | directed | 1 | ✅ 正确拒绝（按金标准要求保留未知） |
| boundary-belief-daiyu-self-image | boundary | belief | executed_pending_semantic_review | directed | 1 | ❌ over-decline（应自述身体虚弱，不靠旁白） |
| boundary-emotion-stone-losing-comrades | boundary | emotion | executed_pending_semantic_review | directed | 1 | ❌ over-decline（应有 canon 情绪依据） |
| expression-answer-stone-retrace-route | expression | answer | executed_pending_semantic_review | directed | 1 | ❌ over-decline（应回溯桥+水帘+路径） |
| expression-challenge-daiyu-on-bao-yu-claim | expression | challenge | executed_pending_semantic_review | directed | 1 | ❌ over-decline（应 push-back 而非完全拒绝） |
| expression-comfort-stone-to-failed-peer | expression | comfort | executed_pending_semantic_review | directed | 0 | ⚠ review 失败 → 消息未发布（详见 §5） |
| expression-cross-book-hearsay-stone-hears-daiyu | expression | cross_book_hearsay | executed_pending_semantic_review | directed | 1 | ✅ 正确处理（标记为房间听说，不内化） |

`executed_pending_semantic_review` 终态含义：runner 真实模型跑结束、未报 run_error、未耗尽 budget、case 流程完整结束（即使内部 review 失败）；但本 runner **不声称** 通过质量层——质量由人工盲评把守（`quality_pass: False`，`semantic_review: pending`）。

## 4. 主要诊断：模型在 6/8 case 上"过度拒绝"

8-pilot 显示 8 case 中有 6 case 的角色回答与金标准不符（5 over-decline + 1 review-fail-to-publish）。共同模式：

1. 角色被问到 canon 内可答的事实时，倾向于用"我眼下没有凭据/无可奉告"句式拒绝
2. 这一倾向在石猴和黛玉两个角色上一致出现
3. 唯一一个反向 case（cross_book_hearsay）回答正确——说明模型能做引用归属，只是阈值过低

这与 8-pilot 之前 4 类负例防护（[2026-10-16-t12-acceptance-index.md §2 防护文字 6 类](#)）设计意图一致：防护文字"宁拒勿答"的力度过强，已经让应当回答的 knowable / belief / emotion / answer / challenge 都退化为 unknowable。runner 的 prompt_version `character-chat-v14` 和 review_prompt_version `character-chat-review-v9` 仍然偏向"无源不答"。

**对 60+24 真实跑的影响**：完整 84 题中 knowable / belief / emotion / answer / challenge / comfort 共 5 个 class 预期也会高比例 over-decline。disagree / unknown_expression / cross_book_hearsay 三个 class 倾向合理（disagree 应拒绝附和；unknown 应拒绝猜测；cross_book 应标记为听说）。如果不做防护文字调整，60+24 真实跑会重复这一过拒模式。

**建议处理（不修改 prompt_version，仅记录）**：

- 维持 32-call 预算上限的 runner 接线契约（不变）
- 把 8-pilot 的实际回答（按 case_id 收录于 report `cases[].turns[].messages[]`）作为后续 prompt-version 调整的对照基线
- 60+24 真实跑保留同一 prompt_version `character-chat-v14` + `character-chat-review-v9`，让"过拒"现象在完整 84 题上稳定可复现，再由人工盲评语义层裁决是否要调整防护文字

## 5. 单 case review 失败（comfort-stone-to-failed-peer）

call 17 generate FAILED（耗时 29.78s），call 18 generate completed（prompt_tokens=0，cache 命中）——chat_worker 自动重试成功。call 19 generate completed（2nd window，operator continuation）。call 20 review FAILED（耗时 17.06s），无 retry——这一失败导致 comfort case 的角色消息在 2nd window 后未发布。

8-pilot 报告完整记录 call 17 / call 20 的失败状态、错误类型（`error_type` 字段在原始 native log），不掩盖也不假装成功。该 case 仍以 `executed_pending_semantic_review` 结束（runner 走完所有窗口），但实际 published 消息为 0。

**对 review 失败的处置**：维持 chat_worker 的"review 失败不回退生成"行为（不写第二次 review），把"是否发布"留给发布层做 review 审计。runner 不会因为单次 review 失败就标 `interrupted`——这一点和 commit 7960170 的 `run_status` 终态枚举契约一致（`executed_pending_semantic_review` 包含"部分发布/部分未发布"的真实状态）。

## 6. 不变量自检

- canonical baseline SHA：before/after 一致 `89f5f44628...` → unchanged=True
- 模型调用：23 次（占 32 ceiling 的 71.9%）
- 发布开关：未变更（OCTOPUS_BOOK_AGENT_ENABLED=1 / OCTOPUS_BOOK_ROOM_ENABLED=1 / OCTOPUS_BOOK_AUTO_IMPORT_ENABLED=0 / OCTOPUS_BOOK_EXPRESSION_ENABLED=0）
- runner 签名：未变更（`rounds.submit` / `BookRoomTimeoutSettings` / `AgentDefaultsRepository` 不动）
- review kind：runner 内显式 `Agent checks complete published bodies and supplied sources; no claim of human blind review`，不宣称人工盲评
- runner 自身的 7 个结构不变量守卫 + 1 个新增 coerce 守卫 + 5 份 dryrun 报告 SHA 一致性守卫均通过（39 项 T12 契约测试 100% pass）
- 84 题金标准池 / 8-pilot v1 dataset / 5 份 dryrun 报告冻结字段未动
- 报告 8-pilot 真实跑结果将作为后续 60+24 / A/B 的对照基线（不改 prompt_version / policy_version）

## 7. 关键路径

- runner：[docs/plans/book-character-agents/t12-quality-runner.py](../../docs/plans/book-character-agents/t12-quality-runner.py)（已含 coerce 修复）
- 8-pilot dataset：[docs/plans/book-character-agents/validation/t12-quality-cases-v1.json](./t12-quality-cases-v1.json)
- probe persona：[docs/plans/book-character-agents/validation/real-model-group-chat-probe.json](./real-model-group-chat-probe.json)
- 8-pilot 真实跑报告：[2026-10-16-t12-8pilot-real-run.json](./2026-10-16-t12-8pilot-real-run.json)
- 8-pilot 真实跑原始 native log：[2026-10-16-t12-8pilot-real-run-native.json](./2026-10-16-t12-8pilot-real-run-native.json)
- 8-pilot dryrun 预览（同一 runner SHA，0 模型调用）：[2026-10-16-t12-8pilot-real-preview-dryrun.json](./2026-10-16-t12-8pilot-real-preview-dryrun.json)
- 4 份 canonical window dryrun（0 模型调用）：`2026-10-16-t12-window-{0..3}-dryrun.json`
- 9 类 14 项 T12 契约测试：[tests/test_t12_question_set.py](../../../tests/test_t12_question_set.py)（合计 39 项；本次新增 1 项 runner coerce 守卫 + 重新生成 5 份 dryrun 不计新增项）
- T12 验收索引：[2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md)
- 状态交接：[2026-10-16-state-of-play.md](./2026-10-16-state-of-play.md)
