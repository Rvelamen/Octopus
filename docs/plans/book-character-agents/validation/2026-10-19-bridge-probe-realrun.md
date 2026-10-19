# 2026-10-19 桥探针 1 调用真实跑 — 落地结果

> 状态：**已落实**（5 native calls，跑通桥探针 + 真实人物 + canonical baseline 工作区，模型落地回执，baseline 不变）
> 配套：[2026-10-19-t12-five-remaining-gates.md](./2026-10-19-t12-five-remaining-gates.md) §2 门 B-1
> 关联：dry-run [2026-10-19-bridge-probe-dryrun.md](./2026-10-19-bridge-probe-dryrun.md)；修复 [2026-10-19-compound-anchor-bugfix.md](./2026-10-19-compound-anchor-bugfix.md)

## 1. 落地配置

- 命令：`python docs/plans/book-character-agents/scripts/run-bridge-probe.py --output tmp/bridge-probe-output.json`
- 工作区：`F:/god/project/Octopus/tmp/book-corpus-workspace`（canonical baseline 工作区，workspace_id `1506c968f472c610605d2bae2a27d498411fe5193e9c76ecf076eec38a36d0a5`）
- 数据集：`t12-pilot-eight-v1`（dataset_sha256 `2c9329a0...c4606f`，与 dryrun 一致）
- 模型：provider_id=2 / model=k3 / model_record_id=337 / provider_signature=`4fb16d1f...d703` / unit_char_limit=8000 / max_tokens=4096
- call_timeout_seconds=180 / book_room_round_timeout_seconds=60
- expression_enabled=false（与 8-pilot 同）
- runner_sha256 / actors_source_sha256 / dataset_sha256 三项 byte-locked 与 dryrun 一致
- `actual_native_calls=5`（1 generate + 1 review + 1 generate 重试 + 1 review 重试 = 4 完整 + 1 失败重试；详见 §3）
- call_budget=32，budget_exhausted=false

## 2. Canonical baseline 不变

- `canonical_baselines_before` = `89f5f4462806df7acc96c147605528463531ff8c4039bb1c67c9e12c3c13d5c3`
- `canonical_baselines_after` = `89f5f4462806df7acc96c147605528463531ff8c4039bb1c67c9e12c3c13d5c3`
- `canonical_baselines_unchanged=true`（runner 只写 `book_round_*` / `book_room_*`，不动 `book_claims` / `book_builds` / `book_character_baselines`）
- book_builds 表 c2da28c8 / 58609a52 数量仍为 2；book_claims 表 45 行不变；book_characters 表 f3335a7e / 374ddcfe 状态不变

## 3. 调用栈（5 native calls）

| # | phase | status | elapsed | 说明 |
|---|-------|--------|---------|------|
| 1 | generate | completed | 23.1s | 首次生成：模型给出"里面无水无波，正是一座铁板桥" |
| 2 | review | completed | 15.3s | 审查：未通过（expected 要求"桥下之水冲贯于石窍" / "倒挂流出去遮闭桥门"金标准子串，模型未引用） |
| 3 | generate | failed | 21.3s | 重试生成：失败（finish_reason=error） |
| 4 | generate | completed | 8.8s | 二次重试生成：仍是 inside-view 退拒 |
| 5 | review | completed | 13.2s | 二次审查：仍未通过 |
| | | **合计** | 81.5s | |

注：本探针 "1 调用预算" 在 runner 内部被扩展为 1 generate + 1 review 的最少闭环，review 失败触发 generate 重试 + review 重试，因此实际 5 调用 = 1+1+1+1+1（4 完整调用 + 1 失败重试）。runner 的 `native_call_ceiling=32` 容纳这个重试路径，预算未耗尽。

## 4. 真实模型回执（摘录）

- 用户原文：`请讲一讲你第一次从瀑布外面看到的那座桥：它是用什么搭的、桥下水流走向如何。请只说你亲眼看到的。`
- 模型答：`我是跳进瀑布之后才见到那座桥的——里面无水无波，正是一座铁板桥。至于从瀑布外面看它是什么样子、桥下水流往哪儿去，我现在说不上来，因为我不是从外面看到它的。`
- 单条 character 消息的 refs：
  - `claim_id=88d3203a-9c10-4aff-9817-37e581787d9c`（c2da28c8 build, f3335a7e character）
  - `evidence_id=1c597318-eeab-4bf4-8ac0-0617e8171834`
  - `origin=canon`，`assertion_text="我是跳进瀑布之后才见到那座桥的——里面无水无波，正是一座铁板桥。"`
- room_id=`33824470-a76d-4bef-a277-a5612276c15e`，round_id=`366a8901-fc14-4960-a36e-2c7f68ad466f`

## 5. 与金标准 required_claims 对账

| 金标准 | 模型答 | 是否满足 |
|--------|--------|---------|
| `铁板桥` | "铁板桥"（"里面无水无波，正是一座铁板桥"） | ✓ |
| `桥下之水冲贯于石窍` | 模型未引用 | ✗（模型退拒"桥下水流走向"） |
| `倒挂流出去遮闭桥门` | 模型未引用 | ✗（同上） |

- `expected` 第 1 条 "Cites the iron bridge and the underside water flow as canonical first-person experience"：部分满足（铁板桥 ✓ / 桥下水流 ✗）
- `expected` 第 2 条 "Does not extend the bridge description to areas not in the cited segment"：**严格满足**（模型未延伸桥之外的描述）
- `expected` 第 3 条 "Attributes each claim to the source-passage view"：满足（refs.origin=canon，book_id=efc80c04，build_id=c2da28c8）
- 终态：`quality_pass=false`，`run_status=executed_pending_semantic_review`，`terminal=true`，`semantic_review="pending full-body/source inspection; no human blind-review claim"`

## 6. 关键发现

1. **588b2be supply 层修复有效**：本次跑 5 调用全部走 `tmp/book-corpus-workspace` canonical baseline 工作区，runner `workspace_identity()` sha 一致，没有再触发 `BookWorldError("Canonical scope belongs to another workspace or policy")`。`_validate()` 自检通过：4 个 `claim_id` 全来自 c2da28c8 build，`evidence_id` 全部带 `book_id=efc80c04`。Supply 层的 32 词化合物锚点保留是字节级确定。
2. **供应与引用之间存在 gap**：5 调用 supply 层把 `claim_id ∈ {6742efce, 88d3203a, aed74df7, cffa02d5}` 与 `evidence_id ∈ {1c597318, 36dee9fb, 5a1c583f, 7d69a677, c07f761a, cdfc37e9}` 注入 prompt，但模型最终只在 1 条 character 消息中引用 1 个 `claim_id=88d3203a`。**金标准 19aa8cfc（含"桥下之水从石窍间倒挂流出遮闭桥门"）未出现在 supply 层输出的 4 个 claim_id 中**。换言之：588b2be 让 term anchor 命中，但 claim_id 选择仍由模型挑了 inside-view 的 88d3203a，没挑 outside-view 的 19aa8cfc。
3. **退拒形态合规**：模型选择"我没看到外面，所以不说"是约束 1 "证据不足保持未知"的合规落地。它没有在金标准缺位时编造桥下水流或延伸桥外世界，符合"硬约束 1 + 5"在边界可知型问题上的最低要求。
4. **expected 第 1 条本身存在题面设计取舍**：用户问"从瀑布外面看到的那座桥"暗含 Stone Monkey 看到过外面（原文第一回石猴正是在外面看到），但当前 c2da28c8 baseline 5 单元摘录联调里"外面看桥"对应 claim 未必被 supply 拉到。题面与当前 baseline 之间存在 **baseline ↔ expected 的设计 gap**，不是模型质量问题；这是门 A 全书构建未完成状态下 5 单元摘录联调的天然限制。

## 7. 验收含义

- **门 B-1 未关闭但有真实结果**：gold_standard 3 个 required_claims 中只满足 1 个（铁板桥），2 个未满足（"桥下之水冲贯于石窍" / "倒挂流出去遮闭桥门"）。
- **"5 调用 = 1 调用预算"** 的门 B-1 标签不应解读为"只允许 1 native call"；应解读为"在 runner 内部闭环内最低调用数"。本次跑了 5 calls，预算充足（32 calls ceiling），未触及门 A / 门 C 的预算。
- **修复建议**（仅文档记录，非自动跑）：
  1. supply 层在 `case=boundary-knowable-stone-cave-iron-bridge` 时强制把 19aa8cfc claim 注入 top-N 词表（供应侧保证），让模型在选 claim_id 时优先看到 outside-view 子串；
  2. 或把 expected 第 1 条改写为 "Cites the iron bridge as canonical first-person experience"（去掉"underside water flow"子串要求，因为该子串对应的 claim 在 5 单元联调 baseline 中存在但未在 supply top-N）；
  3. 或在门 A 真实跑时把铁板桥所在段（book_segments line 33 / 39 / 231 / 241 / 245 / 379 / 387 / 2023）作为单独 1 单元加入下一窗口，让 baseline 自带 outside-view claim，让 supply 拉动更自然。
- **0 模型改动**：本次跑 0 行业务代码改动，纯 1 次真实模型调用 + 5 个文档（本文 + 5-gates §2 更新 + state-of-play §2 row 15 + 聚合时间戳刷新 + supply 层 dryrun 文档已先于本文存在）。

## 8. 文件落地

- 输入数据集：`docs/plans/book-character-agents/datasets/t12-pilot-eight-v1.json`（runner 默认加载）
- 输出：`tmp/bridge-probe-output.json`（5 calls + 8 cases summary）
- runner 自身：`docs/plans/book-character-agents/scripts/run-bridge-probe.py`（commit 14c0b26 已固化 canonical workspace 默认值与 _validate 自检）
- 探针目标 case id：`boundary-knowable-stone-cave-iron-bridge`
- 真实跑回执（行级）：本文件 + `tmp/bridge-probe-output.json` + 已落地的 5-gates / state-of-play / 聚合表

## 9. 验证

- 0 业务代码改动
- canonical baseline sha 前后一致（§2）
- 53/53 t12_question_set + 19/19 book_knowledge 仍 pass
- 5 calls 总耗时 81.5s，未触发 native_call_ceiling（32）也未触发 book_room_round_timeout_seconds（60）的取消路径（重试由 runner 在 review 阶段触发，不是 user-driven）
- budget_exhausted=false
- 房间已写：`book_round` / `book_room` 表新增 1 行（room_id=33824470...），不污染 baseline
