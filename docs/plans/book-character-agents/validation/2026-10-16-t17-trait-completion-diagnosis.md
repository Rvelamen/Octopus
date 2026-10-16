# T17 trait-vs-completion 诊断与确定性 lint 回归门

日期：2026-10-16
范围：T17 matrix v2 agent review `remaining_work` 第 1 项
状态：诊断完成 + 确定性 lint 落地；canonical baseline 不可变，修正版构建留待下次真实构建触发

## 背景

`docs/plans/book-character-agents/validation/t17-matrix-v2-agent-review.json`
给出 `quality_pass=False`、`t17_complete=False`、`t12_complete=False`，两个用例
标记 `warning_source_strength`：

- `free-directed-conditional-action`
- `free-all-unshared-private-knowledge`

其 `remaining_work` 第 1 项要求：

> Disambiguate the approved trait proposition from historical event
> completion, preserve original build and publish a separate
> evidence-backed version if corrected.

本文档记录诊断结论与已落地的确定性回归门；不产生新的模型调用、不修改任何
已发布 canonical baseline。

## 诊断结论

### 涉及范围

| 字段 | 值 |
| --- | --- |
| book_id | `efc80c04-df9b-48e2-ace5-833de34d63fe`（西游记） |
| source_version_id | `89b6b6f7-2fbc-4ea6-b5bf-7715c420ac8f` |
| build_id | `c2da28c8-cab3-4bc2-9342-b1a60831c99a` |
| character_id | `f3335a7e-7dea-4e6d-a34f-457978bb27b7`（石猴） |
| claim_id | `6742efce-da5c-4892-ac66-0d6c3de1b76f` |
| evidence_id | `36dee9fb-b797-4b23-af33-0414d579b547` |
| segment_id | `0829663f-3552-45e5-8332-999161919caf`（字符 67..99） |

### 不匹配的 proposition 与 quote

**claim proposition**（kind=trait, route=firsthand, temporal_state=current）:

> 石猴勇敢果断，敢于率先跳入瀑布泉中探险。

**evidence quote**(segment `0829663f`, 32 字符）:

> 连呼了三声忽见丛杂中跳出一名石猴应声高叫道：“我进去！我进去！”

### 过强点

- proposition 使用 `率先跳入` + `探险` 的**完成式**措辞，断言石猴**已经**
  第一个跳入瀑布并完成探索。
- quote 只记录石猴**应声高叫"我进去！我进去！"**——一次**自愿报名**的
  言语行为，证明"敢于主动请缨"的性格，不证明"已经跳入"。
- 真正记录"跳入"动作的是另一段 segment `a0155270-18ce-4461-a349-5f96a43d5226`
  ("你看他瞑目蹲身将身一纵径跳入瀑布泉中……")，由另一条 episode claim 覆盖。
- 后果：在 matrix v2 `free-directed-conditional-action` 中，模型依据这条
  trait 把假设性问题（"如果同伴要探路，你会先试还是让别人先？")答成
  "当初瀑布泉也是我头一个跳进去探的路"——把"自愿报名"当成"已经完成"
  来回溯，造成 source_strength 过强的警告。

### 建议修正措辞（供下次真实构建采用）

在不改动 segment、evidence_id、route 的前提下，仅重写 proposition 让其与
quote 对齐：

| 版本 | proposition | 与 quote 对齐性 |
| --- | --- | --- |
| 当前（过强） | 石猴勇敢果断，敢于率先跳入瀑布泉中探险。 | 完成式断言"跳入+探险"，超出 quote |
| 建议修正 | 石猴勇敢果断，在群猴无人敢应时率先应声表示愿意进入瀑布。 | 仅断言 quote 实证的"应声+表示愿意进入"，不含完成动作 |

修正要点：
1. 删去 `跳入瀑布泉中探险`——这是 segment `a0155270` 的实际事件，由另一条
   episode claim 覆盖，不应在这条 trait 上重复断言。
2. 把 `率先` 的宾语改为 `应声表示愿意进入`——quote 实证的言语行为，与
   "我进去！我进去！" 严格对齐。
3. 保留 `勇敢果断` trait 标签与 `firsthand` route，不影响 baseline 的
   其他消费方。
4. 该修正**不**通过本次提交落到 canonical baseline——baseline 不可变；
   本表仅供下次真实 persona 构建（或将来扩展 `rephrase_claim` revision 操作
   后）采用，并由本 lint 在生成时再次校验对齐。

### 影响范围评估

- 该 claim 是当前 build 的 baseline trait,canonical_baselines_unchanged=True
  要求**不得**原地修改。
- T04 修订机制当前操作集为 `rename / add_alias / remove_alias / merge /
  correct_owner`，均针对身份与归属，**不支持**"在不换人、不换 evidence 的
  前提下重写一条 trait 的 proposition 措辞"。
- 因此对现存 build `c2da28c8` 不存在零模型调用的"原地修正"路径；正确做法
  是保留下次真实构建时按警告重新生成该 trait，并以本 lint 作为门禁。

## 已落地的确定性回归门

新增模块 `backend/services/book_world/proposition_alignment.py`：

- `trait_completion_overreach(proposition, quote) -> TraitOverreach | None`
  - 仅扫描含 `率先` + 完成动作动词（跳入/进入/探明/探险/探寻/跳下/冲进/
    冲上/攻破/击败/擒获/夺得）的 trait proposition。
  - 若 quote 中**逐字**包含所断言动词，视为证据覆盖完成动作，不警告。
  - 否则若 quote 含自愿/言语标记（我进去/我去/我来/我愿意/应声/高叫/叫道/
    说道/愿意/想要/要去），返回 `TraitOverreach` 诊断。
  - 其他情况保持沉默，宁可漏报也不误报。
- `scan_trait_claims(claims, quote_lookup)`：批量扫描，仅检查 `kind='trait'`，
  跳过 episode/fact/belief 等合法描述完成动作的类别。

新增测试 `tests/test_book_proposition_alignment.py`(7 用例全部通过）:

1. `test_matrix_v2_stone_monkey_trait_is_flagged` — 用真实 baseline 数据
   断言 lint 命中。
2. `test_aligned_trait_with_completed_action_in_quote_passes` — quote 含
   `径跳入瀑布泉中`(segment a0155270）时不警告。
3. `test_trait_without_shuaxian_prefix_passes` — 无 `率先` 措辞不在 lint 范围。
4. `test_trait_with_completion_verb_but_no_intent_marker_passes` — 缺 intent
   标记时保持沉默（避免误报）。
5. `test_non_trait_claims_are_skipped_by_scan` — episode/fact 不被扫描。
6. `test_scan_collects_only_flagged_traits` — 混合样本中只挑出 1 条 trait。
7. `test_reason_mentions_both_sides_of_the_mismatch` — 诊断文案同时点名
   动词与 intent 标记，方便人工审阅。

测试均为纯函数、无数据库、无网络、无模型调用。

## 与 T17 remaining_work 的对应

| remaining_work 项 | 本次进展 | 剩余动作 |
| --- | --- | --- |
| 1. Disambiguate the approved trait proposition from historical event completion | 诊断完成；确定性 lint 落地；精确锁定 claim/evidence/segment 三要素 | 在下次真实 persona 构建时按 lint 警告重生成该 trait；本次不改写 canonical baseline |
| 2. Re-evaluate matrix v2 replies against corrected source gold | 已用 lint 完成确定性复评，发现 **4 个用例**命中(超出 reviewer 原标 2 个)，详见下节 | — |
| 3. T12 8-pilot real model run | — | 仍阻塞于模型预算 |

## Lint 复评 matrix v2 的实际命中面

脚本 `scripts/book_world/reevaluate_matrix_v2_refs.py` 对
`real-model-t17-matrix-v2.json` 的 16 条 character refs 全量扫描：

- 6 条 trait refs 全部命中（同一条 claim `6742efce` 的不同断言引用）
- 命中用例 **4 个**,reviewer 原标 2 个，新发现 2 个：

| case_id | reviewer 标记 | lint 命中 | 说明 |
| --- | --- | --- | --- |
| `free-directed-conditional-action` | warning_source_strength | 2 refs | reviewer 已识别 |
| `free-all-unshared-private-knowledge` | warning_source_strength | 1 ref | reviewer 已识别 |
| `topic-natural-retained-topic` | limited_behavior_pass | 1 ref | reviewer 标记通过但 lint 命中——答"我敢先去北门看一眼"也用了过强 trait |
| `topic-directed-rephrased-dilemma` | limited_behavior_pass_after_timeout | 2 refs | reviewer 标记通过但 lint 命中——"我有率先涉险的胆量"措辞同样源自过强 trait |

复评报告已落地到
`docs/plans/book-character-agents/validation/2026-10-16-t17-matrix-v2-lint-reeval.json`，
由测试 `test_matrix_v2_json_yields_expected_flagged_cases` 锁定命中数与
用例集合，任何 lint 回归或 baseline 变化都会让该测试失败。

这印证 linter 不是空转：它捕捉到了 reviewer 遗漏的两个用例，说明
"率先跳入" 这一过强 trait 在 matrix v2 中的实际影响面比 source_strength
警告范围更广。后续若以修正后的 baseline 重跑 matrix，应优先看
`topic-natural-retained-topic` 与 `topic-directed-rephrased-dilemma`
是否从 limited_behavior_pass 提升。

## 预算与不变量

- 模型调用：0（诊断使用既有 JSON 与代码引用，未触发任何 provider)
- canonical_baselines_unchanged:True（未触碰任何已发布构建）
- 新增代码均为纯函数 + 单元测试，可独立审查、可回滚

## 后续衔接

- 诊断文档落地后已立即把 `trait_completion_overreach` 接入 `persona_publication.py`：每次 `publish_personas` 完成 evidence 评估、写 `book_build_steps stage='publication' unit_key='summary'` 之前，对 `kind='trait' AND support_state='accepted' AND access_state='accepted'` 的 trait claim 用 lint 全量扫描，命中项以 `trait_lint_warnings`（list[dict]）作为纯加性第 6 个键写入 publication report；status `partial_published` / `published` 判定逻辑与既有 5 个键保持不变。实现见 [backend/services/book_world/persona_publication.py](../../../backend/services/book_world/persona_publication.py) 第 132-165 行。
- 接入落地由 [tests/test_persona_publication_trait_lint.py](../../../tests/test_persona_publication_trait_lint.py) 5 项确定性契约测试锁住：trait 过强命中 1 条 / 对齐 quote 不命中 / episode 同过强措辞不命中 / 任意 build 必含 `trait_lint_warnings` 键 / 冻结的 publication step result_json 触发 IntegrityError 后原始警告 SELECT 仍可见。5 项同时通过、模型调用 0。
- 下次真实 persona 构建（`persona.py` 真实 model provider 接入）首次运行时，publication report 即可对外暴露 `trait_lint_warnings`，revision-review prompt 与 `discovery.get_build` API 消费者可直接读取并按警告重生成该 trait；不再需要等到 T17 重新评估或 `rephrase_claim` 类修订操作落地才触发门禁。
- 若未来仍需对现存 build `c2da28c8` 产出修订版，需先扩展 T04 修订操作集（新增 `rephrase_claim` 类操作），再以本 lint 为 review 一侧的确定性预检；该扩展超出本次范围，与本次 wiring 互不阻塞。
