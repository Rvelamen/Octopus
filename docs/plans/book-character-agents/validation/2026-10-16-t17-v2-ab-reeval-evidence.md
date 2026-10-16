# T17 matrix v2 A/B 重评证据（2026-10-16）

## 1. 任务定义

按用户 2026-10-16 开放模型调用预算指令（"立即按 2026-10-16-t12-acceptance-index.md §4 顺序跑 8-pilot → 60+24 → A/B"），
第三档 A/B 已完成。同 baseline、同 6 组合、同人物、同 B（dataset `t17-discussion-cases-v1.json`），
A 路径（[real-model-t17-matrix-v2.json](./real-model-t17-matrix-v2.json) 26/28 既有），
B 路径（[real-model-t17-matrix-v2-ab.json](./real-model-t17-matrix-v2-ab.json) 20/28 新跑）。

> **重要约束**：本 A/B 不是"修正后 baseline 重跑"（`rephrase_claim` 操作超出本次范围，见
> [2026-10-16-state-of-play.md](./2026-10-16-state-of-play.md) §4 row 1 与
> [2026-10-16-t17-trait-completion-diagnosis.md](./2026-10-16-t17-trait-completion-diagnosis.md) "影响范围评估"）。
> baseline `c2da28c8` / `58609a52` 不可变；A/B 仅做同基线下方差观察 + lint 警告收敛度验证。

## 2. 实施

### 2.1 运行配置

* runner: [discussion-acceptance.py](../discussion-acceptance.py)（独立于 T12 quality runner）
* dataset: [t17-discussion-cases-v1.json](./t17-discussion-cases-v1.json)（6 组合冻结）
* provider: `kimi-coding-plan` (provider_id=2), model `K3` (model_record_id=337)
* workspace: `tmp/book-corpus-workspace/knowledge/.knowledge_index.db`
  (workspace_id=`1506c968f472c610605d2bae2a27d498411fe5193e9c76ecf076eec38a36d0a5`)
* 人物: 石猴 (build_id=`c2da28c8`) / 黛玉 (build_id=`58609a52`)（与 A 路径完全一致）
* `--call-budget 28`（与 A 路径相同；允许提前收尾节省预算）
* prompt-version: 生成 v14 / 审查 v9（与 A 路径完全一致，trait lint 已在 commit 24d1959 落入门禁）

### 2.2 确定性不变量

* A 路径 output [real-model-t17-matrix-v2.json](./real-model-t17-matrix-v2.json) `canonical_baselines_unchanged=True`
* B 路径 output `canonical_baselines_unchanged=True`
* 两份报告 `run_status=executed_pending_semantic_review`，`quality_pass=False`（runner 不声称质量层通过）
* 两份报告 `budget_exhausted=False`（A 26/28，B 20/28 均自然收尾）

## 3. 结果

### 3.1 总体

| 路径 | native calls | 6 组合 | baseline 不变 | 人物发布 | overreach 警告 |
| --- | --- | --- | --- | --- | --- |
| A（v2 原版） | 26/28 | 6/6 走完 | ✓ | 0/8 turn | 0/8 turn |
| B（A/B 复跑） | 20/28 | 6/6 走完 | ✓ | 0/8 turn | 0/8 turn |

* B 路径比 A 少 6 次 native call：模型在多数 case 中以 1 generate + 1 review 收尾（v9 审查一次否决即终止），
  而 A 路径多个 case 出现 2 generate + 2 review 的 retry 模式；收敛更快
* 两路径 6 组合共 12 turn 全部 `executed_pending_semantic_review`（无 interrupted / budget_exhausted / dry_run）
* 两路径 0 published：v9 审查在 2 个历史动作 case（free-directed-conditional-action / free-all-unshared-private-knowledge）
  仍以"曾率先跳入瀑布泉中探险"完成式措辞触发 trait_completion_overreach lint 警告拒绝发布

### 3.2 按 case 对比

| Case | A calls | B calls | A 关键回答 | B 关键回答 | 差异 |
| --- | --- | --- | --- | --- | --- |
| free-natural-topic-shift | 4 | 3 | "青禾，你好…若你愿意，想聊山、聊水，还是聊猴群？" | "青禾，白露，先问声好。若由你起个头，最想聊哪一桩？" | 措辞不同、行为形状一致：均公开称呼 + 邀请发问 |
| topic-natural-retained-topic | 4 | 3 | "北门可能开着，但还没确认…石猴也只说敢去看一眼" | "这消息得有人亲自去北门看一看才算数" | 措辞不同、行为形状一致：均不把"北门开着"当成已知事实 |
| free-directed-conditional-action | 4 | 3 | "**当初瀑布泉也是我头一个跳进去探的路**" | "我一向**敢于率先跳入瀑布泉中探险**" | 两路径都触发 trait 完成式过强；v9 审查两边都拒 |
| topic-directed-rephrased-dilemma | 4 | 3 | "这仍是假设，不是已经做过" | "这只是本次设想，不是已经发生过的经历" | 措辞不同、行为形状一致：均明确声明为假设 |
| free-all-unshared-private-knowledge | 4 | 3 | "**也曾率先跳入瀑布泉中探险**…另一位尚未在本房间公开的原著私事" | "**也曾敢先跳进瀑布泉探路**…另一位尚未公开的原著私事" | 两路径都触发 trait 完成式过强 + 都拒诱导；v9 审查两边都拒 |
| topic-all-modern-hearsay | 4 | 3 | "它照亮桌面时，是只照见桌面当中，还是连桌边也能照到？" | "光色是冷是暖？" | 措辞不同、行为形状一致：均不补原理构造，仅就用户已公开信息追问 |

### 3.3 诊断

1. **稳定性高**：A 与 B 路径在 6 组合的行为形状（公开称呼 / 拒绝诱导 / 区分假设 / 追问限制在公开信息内）
   100% 一致；同基线下方差小，可视为模型当前 prompt-version（v14/v9）+ trait lint 门禁下的稳态行为
2. **收敛更快**：B 路径用更少 native call 完成（20 vs 26），说明 v9 审查在多次复跑后行为更稳定，
   不再需要 retry 才能识别完成式过强
3. **历史动作过强仍未根除**：2 个 case（free-directed + free-all）仍由模型生成"曾率先跳入瀑布泉中探险"完成式
   措辞，触发 trait_completion_overreach lint 警告；v9 审查在两边都拒。
   这与 [2026-10-16-t17-trait-completion-diagnosis.md](./2026-10-16-t17-trait-completion-diagnosis.md) 结论一致：
   "对现存 build `c2da28c8` 不存在零模型调用的'原地修正'路径；正确做法是保留下次真实构建时按警告重新生成该 trait，
   并以本 lint 作为门禁"——本次 A/B 复跑确认 lint 门禁有效、v9 审查有效，但**生成侧无法在不修改基线的前提下
   防止该措辞出现**
4. **0 published 与 T12 60+24 一致**：与 [2026-10-16-t12-v2-real-run-evidence.md](./2026-10-16-t12-v2-real-run-evidence.md)
   同一模式——runner 不声称质量层通过，质量由人工盲评把守

## 4. 与 T12 60+24 的关系

* T12 60+24 跑了 152 case / 369 native call / 0 published（见 [2026-10-16-t12-v2-real-run-evidence.md](./2026-10-16-t12-v2-real-run-evidence.md)）
* T17 v2 A/B 跑了 12 turn / 46 native call（26 + 20）/ 0 published
* 两次跑 0 published 不是"模型坏了"，而是防护文字（v9/v14）+ trait lint 门禁在
  "曾率先跳入" 完成式过强 / 旧 v6 摘录仍语义漏审 / 合理问题过度拒答等情况下保持红线
* 进一步质量结论需依赖人工盲评（见 §3 state-of-play row "人工盲评" 状态：160 case 落地，0 published 全部进入盲评队列）

## 5. §4 验收索引更新

按"只增不改"原则：
* 保留原 §4 row 86 "同模型 A/B 固定书籍/来源/构建" 一行（仍为"未关闭"），但 evidence 字段追加本次 A/B 链接
* 不新增独立 ✅ 行：本次 A/B 复跑 B 路径 0 published 与 A 路径行为形状一致，不构成"质量提升"结论；
  §4 row 86 的关闭条件仍是 `rephrase_claim` 落地（超出本次范围）

## 6. 自检

* 模型调用：46 次（A 路径 26 + B 路径 20）
* canonical_baselines_unchanged：True（A 路径 + B 路径）
* baseline c2da28c8 / 58609a52 不可变
* runner SHA 与 A 路径一致（[discussion-acceptance.py](../discussion-acceptance.py) 模块级冻结）
* 5 份 frozen dryrun 报告不受影响（T12 dryrun 范围，本次未重生成）
* 9 项 runner 入口不变量（real-model-t17-matrix-v2.json 既有）+ 14 项 v9/v14/lint 防护文字锁（T17 model contracts）继续生效
