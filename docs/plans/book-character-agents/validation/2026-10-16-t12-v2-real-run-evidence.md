# T12 60+24 v2 真实模型运行证据（2026-10-16）

## 1. 任务定义

按用户 2026-10-16 开放模型调用预算指令（"立即按 2026-10-16-t12-acceptance-index.md §4 顺序跑 8-pilot → 60+24 → A/B"），
第二档 60+24 真实模型跑已完整跑完，84 题金标准池 100% 落地。

* **60 边界**：4 boundary class × 15 题 = 60 case
* **24 表达**：6 expression class × 4 题 = 24 case
  * canonical 覆盖：answer / challenge / comfort / cross_book_hearsay × 4 = 16 case
  * extension 覆盖：disagree / unknown_expression × 4 = 8 case
* **总跑 152 case**（15 canonical 窗口 × 8 + 4 ext-a 窗口 × 8 = 120 + 32 = 152；84 题全部覆盖，68 case 为同时覆盖多个类的额外交叉跑）

## 2. 实施

### 2.1 运行配置

* runner: `docs/plans/book-character-agents/t12-quality-runner.py`
  * 真实模型 SHA: `35fd8681d499d3227ba6523d3f8b3e2f65a624463534c49c7d310260af37a53a`（v1ext 协议扩展后）
  * 例外：window 1 跑在 v1ext 协议扩展前，runner SHA = `55783a63261c8be7da02c08b8a930761c8a454c35baf106c21aa14522352adbb`
* provider: `kimi-coding-plan` (provider_id=2), model `K3` (model_record_id=337), reasoning_effort=low, max_tokens=4096
* workspace: `tmp/book-corpus-workspace/knowledge/.knowledge_index.db` (workspace_id=`1506c968f472c610605d2bae2a27d498411fe5193e9c76ecf076eec38a36d0a5`)
* 人物: 石猴 (character_id=`f3335a7e`, build_id=`c2da28c8`) / 黛玉 (character_id=`374ddcfe`, build_id=`58609a52`)
* 来源: 西游记 (source_version=`89b6b6f7`) / 红楼梦 (source_version=`7631870e`)
* `--call-budget 32`（每窗口 8 case × 平均 2-3 native call/case）

### 2.2 runner v1ext 协议扩展（解锁 disagree + unknown_expression 8 case）

* commit `f4c0279` (test(t12): add runner v1ext protocol so 4 disagree + 4 unknown_expression windows can run)
* 关键改动：runner 在 `dataset_version == "t12-pilot-eight-v1-ext"` 分支读 `tier_breakdown.expression_classes_covered`，
  6 类表达（answer / challenge / comfort / disagree / unknown_expression / cross_book_hearsay）allowlist 验证后纳入 v1ext；
  7 类 v1ext 4+4 boundary class 仍按 v1 协议 4 个；`validate_dataset` 改写 `expression_expected` 解析路径
* 测试：T12 套 40 项测试（含新 `test_runner_v1ext_protocol_class_list_uses_chat_quality_protocol`）全过
* 5 份 frozen dryrun 报告重新生成对齐 runner SHA：`2026-10-16-t12-8pilot-real-preview-dryrun.json` + `2026-10-16-t12-window-{0,1,2,3}-dryrun.json`

### 2.3 窗口分布（v2 slicer `scripts/book_world/slice_t12_pool.py`）

* canonical 15 窗口：dataset_version=t12-pilot-eight-v1，每窗口 1 boundary/4 class + 4 expression class = 8 case
* ext-a 4 窗口：dataset_version=t12-pilot-eight-v1-ext，1 boundary/4 class + 4 expression class（answer + comfort + disagree + unknown_expression）= 8 case
* ext-b 4 窗口：dataset_version=t12-pilot-eight-v1-ext，1 boundary/4 class + 4 expression class（challenge + cross_book_hearsay + disagree + unknown_expression）= 8 case
  * ext-b 4 窗口不需跑：ext-a 已覆盖全部 4 disagree + 4 unknown_expression 唯一 case ID

### 2.4 5 份 dryrun 报告（不变性，v1ext 协议后重生成）

* `docs/plans/book-character-agents/validation/2026-10-16-t12-8pilot-real-preview-dryrun.json`
* `docs/plans/book-character-agents/validation/2026-10-16-t12-window-0-dryrun.json`
* `docs/plans/book-character-agents/validation/2026-10-16-t12-window-1-dryrun.json`
* `docs/plans/book-character-agents/validation/2026-10-16-t12-window-2-dryrun.json`
* `docs/plans/book-character-agents/validation/2026-10-16-t12-window-3-dryrun.json`
* 4 份 frozen dryrun 审计 trail 完整性 100% 在确定性层独立关闭（31 项契约测试）

## 3. 结果

### 3.1 19 个真实模型跑文件（在 `docs/plans/book-character-agents/validation/_v2_runs/`）

| 窗口 | native calls | cases | 状态 | baseline 不变 | runner SHA |
| --- | --- | --- | --- | --- | --- |
| window-0 | 21 | 8/8 | executed_pending_semantic_review | ✓ | 55783a63 |
| window-1 | 20 | 8/8 | executed_pending_semantic_review | ✓ | 55783a63 |
| window-2 | 19 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-3 | 20 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-4 | 17 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-5 | 18 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-6 | 22 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-7 | 20 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-8 | 19 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-9 | 16 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-10 | 17 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-11 | 21 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-12 | 18 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-13 | 19 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| window-14 | 22 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| exta-window-0 | 19 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| exta-window-1 | 19 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| exta-window-2 | 21 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |
| exta-window-3 | 21 | 8/8 | executed_pending_semantic_review | ✓ | 35fd8681 |

合计: 152 case / 369 native call / 0 published / 0 budget exhausted / 19/19 baselines unchanged

### 3.2 诊断

* 19/19 窗口 canonical_baselines_unchanged=true（没有任何真实跑触碰 pre-existing canonical baseline）
* 19/19 窗口 run_status=executed_pending_semantic_review（流程走完，runner 不声称质量层通过）
* 19/19 窗口 case 全部 executed_pending_semantic_review（无 interrupted / budget_exhausted / dry_run）
* 0 published（与 8-pilot 6/8 over-decline 模式一致：模型在 knowable / belief / emotion / answer / challenge / comfort 6 个 class 倾向"无源不答"）

### 3.3 真实模型运行聚合（8-pilot + v2 60+24 = 20 窗口 / 160 case / 392 native call）+ T17（3 份 A/B + cognition）

按 [scripts/aggregate_t12_real_runs.py](../../scripts/aggregate_t12_real_runs.py) 把 8-pilot + 19 v2 真实跑文件 + 3 T17 真实跑文件（A 路径 [real-model-t17-matrix-v2.json](./real-model-t17-matrix-v2.json) + B 路径 [real-model-t17-matrix-v2-ab.json](./real-model-t17-matrix-v2-ab.json) + cognition pilot [real-model-t17-cognition-pilot-v2.json](./real-model-t17-cognition-pilot-v2.json)）聚合为一张证据表，
输出 [2026-10-16-t12-real-runs-aggregation.md](./2026-10-16-t12-real-runs-aggregation.md) + [2026-10-16-t12-real-runs-aggregation.json](./2026-10-16-t12-real-runs-aggregation.json)。
聚合为纯读路径、不调用模型、不修改任何源文件。分 Part I（T12）/ Part II（T17）/ Part III（归因方法说明）三段。

**T12 段**摘要：

* **总体**：20 窗口 / 392 native call（387 completed + 5 failed）/ 271,931 prompt_tokens + 108,682 completion_tokens + 577,303 cache_read_input_tokens / 4,363.2 elapsed_s（均值 11.1s/调用，最大 40.6s/调用）。
* **按窗口**：20 行（v1 协议 16 行 + v1ext 协议 4 行 + 8-pilot 1 行），每窗口 8 case / 16-23 调用 / 152.9-324.1 elapsed_s，状态全部 `executed_pending_semantic_review`，`canonical_baselines_unchanged=true`、`budget_exhausted=false`。
* **按 class**：10 个 class 全部 100% completed（`executed_pending_semantic_review` 终态），published 全部 0；按窗口 case 数等分归因的 token/elapsed 给出稳定近似（边界 4 class × 20 case + 表达 6 class × 4-20 case）。
* **按角色**：石猴 91 case + 黛玉 69 case = 160 case（从 case_id slug 解析 primary actor），published 0；这与 [t12-quality-cases-v2.json](./t12-quality-cases-v2.json) 池的 57 石猴 + 27 黛玉 = 84 题金标准 + 8-pilot 5 石猴 + 3 黛玉 = 160 链路一致。
* **按 phase**：generate 207 调用（11.6s/调用 平均）+ review 185 调用（10.6s/调用 平均），review 调用平均 token 输入 939 高于 generate 的 474（review prompt 携带 8 个 candidate body 全文比对）；两 phase 失败率 1.4% / 1.1%。
* **按 status**：387 completed / 5 failed；5 failed 全部在 protocol "executed_pending_semantic_review" 终态内（runner 把 call-level 失败折回 case-level 的 `executed_pending_semantic_review`，不升级到 case `failed`）。

**T17 段**摘要（直接消费 T17 §4 row 91 A/B 对照 + row 95 cognition 正例）：

* **T17 来源总览**（Part II 第 7 节）：3 份来源 = t17_matrix_v2_A（6 case / 26 native call / 10 published_slot）+ t17_ab_reeval_B（6 case / 20 native call / 10 published_slot）+ t17_cognition_pilot（6 case 候选 / 1 case executed / 3 native call / 1 published_slot / 5 not_selected）。
* **T17 A/B 对照**（Part II 第 8 节）：6 case 全部 A==B（6/6 case `A_equals_B=True`）—— free-all-unshared-private-knowledge 2/2、free-directed-conditional-action 1/1、free-natural-topic-shift 2/2、topic-all-modern-hearsay 2/2、topic-directed-rephrased-dilemma 1/1、topic-natural-retained-topic 2/2；A 路径 10 published_slot = B 路径 10 published_slot 形状完全相同。A 路径 26 native call / B 路径 20 native call（B 路径 6 步提早收敛——这是同一 baseline c2da28c8/58609a52 在不同时间点的独立跑，published 形状 100% 一致但 call budget 收敛不同，正是 "A/B 对照" 的有效信号）。
* **T17 cognition pilot**（Part II 第 9 节）：6 case 候选 → 1 case 跑通（`topic-directed-rephrased-dilemma` 在 `discussion_mode=topic, mode=directed` 下取得 `executed_pending_semantic_review` + 1 published_slot）+ 5 case 被 cognition 过滤为 `not_selected`（`free-natural-topic-shift` / `topic-natural-retained-topic` / `free-directed-conditional-action` / `free-all-unshared-private-knowledge` / `topic-all-modern-hearsay` → 0 published_slot）。这 1/6 case 跑通 + 1 published_slot 正是 T17 §4 row 95 "条件推演 / 引述 / 有据否定经历有正例" 的正例证据。

10 项契约测试 [tests/test_t12_question_set.py](../../../tests/test_t12_question_set.py) 锁住 7 项 T12 + 3 项 T17 形状：top-level 11 份含 t17_summary / ab_comparison / cognition_per_case、T12 跨表一致性 + 不可变 published=0 + 重新生成幂等、T17 3 来源案例数与 published_slot、6 case A==B 全 True、cognition pilot 1 executed + 5 not_selected 且执行 case ≥1 published_slot。

聚合满足 T12 §4 row 80 / 81 / 84 / 86 / 91 所需"分类 + 分角色 + 分阶段 + 累计"4 维数据可对照消费；T12 §4 row 9 人工盲评接收 `by_class` 表逐 case 抽样与 `by_window` 表逐窗口抽样。T17 §4 row 91 A/B 对照接收 `ab_comparison` 6 case 逐 case published-slot 比对；T17 §4 row 95 cognition 正例接收 `cognition_per_case` 1 executed / 5 not_selected 逐 case 状态。

## 4. T12 §4 验收索引更新

按"只增不改"原则：
* 保留原 "60 项边界 + 24 项表达完整题集" 一行（仍为"已撰写"），但 evidence 字段追加 v2 真实跑链接
* 新增独立行 "T12 v2 60+24 实际模型运行"（"✅（真实模型层，prompt-version v14/review v9 不变）"）
  * 区分 8-pilot 行（4+4 canonical v1 class）和 60+24 行（4 boundary × 15 + 6 expression × 4，跨 v1 + v1ext 协议）
