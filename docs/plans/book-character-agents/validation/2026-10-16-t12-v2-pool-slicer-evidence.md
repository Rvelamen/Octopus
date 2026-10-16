# T12 84-题金标准池 + 切片器 + 0 模型调用验证（2026-10-16）

日期：2026-10-16
状态：v2 池 + 切片器 + 15 项契约测试全部就绪；真实 8-pilot 模型跑仍阻塞于预算授权与 provider 选择
范围：T12 `remaining_work` 第 3 项前置准备

## 背景

`docs/plans/book-character-agents/validation/t17-matrix-v2-agent-review.json` 的
`remaining_work` 第 3 项要求"完成全书构建、情感/人格评测、T12 60/24 题目与
完整应用/浏览器验收"。本文件记录 v2 题集 + 切片器 + 0 模型调用 dry-run 的落地
部分；真实 8-pilot 模型跑与浏览器验收仍阻塞，明确告知。

## 资产清单

| 文件 | 角色 | 大小 |
| --- | --- | --- |
| `scripts/book_world/build_t12_v2.py` | 84 题金标准生成器 | 904 行 |
| `scripts/book_world/slice_t12_pool.py` | v2→v1 切片器（支持 canonical / extension-a / extension-b） | 283 行 |
| `docs/plans/book-character-agents/validation/t12-quality-cases-v2.json` | 84 题金标准池（dataset_version=t12-pilot-eightyfour-v1） | 2884 行 |
| `docs/plans/book-character-agents/validation/t12-quality-cases-v1-window-{0..3}.json` | 4 个 runner 兼容的 8-pilot canonical 窗口 | 4 × ~322 行 |
| `docs/plans/book-character-agents/validation/2026-10-16-t12-window-{0..3}-dryrun.json` | 4 份 runner `--dry-run` 报告（actual_native_calls=0 / publication=False） | 4 × ~226 行 |
| `tests/test_t12_question_set.py` | 15 项确定性契约测试 | 468 行 |

## 84 题金标准的具体分布

- **60 题 boundary**：knowable / unknowable / belief / emotion 各 15 题
  - 石猴 45 题 + 黛玉 15 题
  - 覆盖《西游记》水帘洞 / 弼马温 / 八卦炉 / 五行山 / 蟠桃 / 白骨精等场景
  - 覆盖《红楼梦》葬花 / 潇湘 / 凹晶馆联诗 / 寒塘渡鹤影 / 燕窝等场景
- **24 题 expression**：answer / challenge / comfort / disagree / unknown_expression /
  cross_book_hearsay 各 4 题
  - 石猴 12 题 + 黛玉 12 题
  - cross_book_hearsay 4 题必带双书 ID，强制跨书边界在数据层

每题结构：
```json
{
  "case_id": "boundary-knowable-stone-water-curtain-cave",
  "tier": "boundary",
  "class": "knowable",
  "target_actor_indices": [0],
  "book_ids": ["efc80c04-df9b-48e2-ace5-833de34d63fe"],
  "discussion_mode": "natural",
  "mode": "ask",
  "questions": ["..."],
  "gold_standard": {
    "verdict": "knowable",
    "required_claims": ["铁板桥", "我进去！我进去！", "..."],
    "forbidden_claims": ["把'群猴'写成'同伴'", "改字", "..."],
    "expected_source": "《西游记》第一回 灵根育孕源流出 心性修持大道生"
  },
  "expected": [
    {"id": "...", "expected": "..."}
  ]
}
```

`required_claims` 与 `forbidden_claims` 均锚定 `tmp/book-corpus/{西游记,红楼梦}.txt`
的真实段落（由 `tests/test_t12_question_set.py::test_v2_pool_v1_consistency_with_corpus_anchors`
逐项断言），确保未来重生成不漂移。

## 切片器覆盖不变式

`slice_t12_pool.py` 是纯函数 `deterministic_window`：
- 15 个 canonical v1 窗口（`--extension-set` 不传）→ dataset_version=t12-pilot-eight-v1
  覆盖 60 boundary + 16 expression = 76 题（4 个 canonical expression 类各 4 题）
- 15 个 v1-extension-a 窗口（`--extension-set a`）→ dataset_version=t12-pilot-eight-v1-ext
  覆盖 4 unknown_expression + 4 题的某 canonical 子集
- 15 个 v1-extension-b 窗口（`--extension-set b`）→ dataset_version=t12-pilot-eight-v1-ext
  覆盖 4 disagree + 4 题的某 canonical 子集
- 45 个窗口合计覆盖全部 84 题

runner 兼容窗口（canonical）必须满足：
1. 4 boundary 类：knowable / unknowable / belief / emotion
2. 4 canonical expression 类：answer / challenge / comfort / cross_book_hearsay
3. window_size=8、native_call_ceiling=32、dataset_version=t12-pilot-eight-v1

extension 窗口带 `-ext` 后缀，runner 在 `validate_dataset` 直接拒绝；用于离线审计与
金标准全量复核，不进 8-pilot 跑。

## 0 模型调用验证矩阵

| 操作 | 调用数 | 退出码 | 报告位置 |
| --- | --- | --- | --- |
| `slice_t12_pool.py --window-index 0..3` | 0 | 0 | `t12-quality-cases-v1-window-{0..3}.json` |
| `t12-quality-runner.py --dry-run --dataset window-{0..3}` | 0 | 0 | `2026-10-16-t12-window-{0..3}-dryrun.json` |
| `pytest tests/test_t12_question_set.py` | 0 | 0 | 15 项全过 |

dry-run 报告统一字段：
- `mode = "dry_run"`
- `actual_native_calls = 0`
- `publication = False`
- `quality_pass = False`
- `dataset_version = "t12-pilot-eight-v1"`
- 含 `dataset_sha256` / `actors_source_sha256` / `runner_sha256` 三段字节级指纹

## 15 项契约测试一览

| # | 测试名 | 锁定不变量 |
| --- | --- | --- |
| 1 | `test_v2_pool_has_exactly_84_cases` | 60+24=84 总数 |
| 2 | `test_v2_pool_class_distribution_matches_protocol` | 4×15 boundary + 6×4 expression |
| 3 | `test_v2_pool_covers_both_books_and_both_characters` | 每类双书双角色 |
| 4 | `test_v2_pool_v1_subset_class_set_is_superset_of_v1` | v1 ⊂ v2 且 v2 覆盖全部 6 expression |
| 5 | `test_v2_pool_case_ids_are_unique` | case_id 无重复 |
| 6 | `test_v2_pool_schema_fields_match_v1` | 顶层 schema 镜像 v1 |
| 7 | `test_v2_pool_each_case_has_required_fields` | 每题必填字段齐全 |
| 8 | `test_v2_pool_native_call_ceiling_keeps_v1_invariant` | ceiling=32 不变 |
| 9 | `test_v2_pool_forbidden_claims_avoid_paraphrase_drift` | 60 boundary 题均带改字/改写/改词守卫 |
| 10 | `test_slicer_emits_v1_shape_8_pilot_window` | 切片器发出 v1 schema 窗口 |
| 11 | `test_slicer_covers_pool_across_windows` | 15+15+15 窗口 = 84/84 覆盖 |
| 12 | `test_extension_windows_are_not_runner_compatible` | 扩展窗口带 `-ext` 后缀 |
| 13 | `test_slicer_dry_run_through_runner_actually_loads` | 切片器→runner `--dry-run` 端到端接线 |
| 14 | `test_v2_pool_v1_consistency_with_corpus_anchors` | 语料锚点漂移守卫 |
| 15 | `test_v2_pool_hearsay_cases_target_both_books` | cross_book_hearsay 4 题必带双书 ID |

15/15 通过，模型调用 0；`tests/test_book_task_contracts.py` 9 项 T04–T11/T16 单任务
契约测试同时通过；`tests/test_book_proposition_alignment.py` 8 项 T17 trait lint
测试通过。

## 仍阻塞事项

- **真实 8-pilot 模型跑**：`remaining_work` 第 3 项核心子项
  - provider 选择：kimi-coding-plan · K3 待授权
  - 预算授权：T12 单次跑 32 调用 × 实际模型计费
  - 阻塞期间 runner 在 `--dry-run` 模式下可重复验证 schema 与接线
- **修正版 trait 重生成 + 矩阵 A/B 复跑**：依赖 `rephrase_claim` 修订操作扩展或
  下次真实 persona 构建触发
- **浏览器 3D 圆桌 + 同步气泡操作验收**：依赖真实模型输出
- **跨工作区读写矩阵独立复核**：依赖完整应用部署

本文件不替模型质量背书；T12 真实 acceptance 仍以
`t17-matrix-v2-agent-review.json` 的 `t12_complete=False` 为准。
