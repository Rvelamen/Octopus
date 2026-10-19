# T12 验收剩余 5 个门 — 阻塞、已尝试与最小所需信息

> 本文档是对 [2026-10-19 证据纠正](2026-10-19-t12-evidence-correction.md) §首版仍未闭合的实际条件 的执行版操作说明。每条门给出：当前状态、阻塞原因、已尝试、最小所需信息、解锁后立即可做的下一步。**不重复本仓库已有的状态交接、聚合表、契约测试、bugfix 文档**。本文件按"只增不改"原则追加，不删除既有记录。

## 0. 入口与不变式

- 链路与确定性已 100% 锁定，证据与回归位置在 [2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md) §2。
- 真实模型预算现状：本次 commit 链（含 588b2be 修复 + 证据纠正 + 4 项 ruff 清理 + 2 次聚合时间戳刷新）模型调用 0；剩余 5 个门中 3 个需要真实模型调用。
- 不可触碰约束：canonical baseline `c2da28c8`（西游记）/ `58609a52`（红楼梦）、book_claims / book_evidence / book_access_evidence 索引、`rounds.submit` / `BookRoomTimeoutSettings` / `AgentDefaultsRepository` / `publish_personas` 等所有 API 签名、`chat-quality-protocol.md` 协议词汇。
- 盲评工具已就绪（[blind-review-cli.py](../../blind-review-cli.py) 6 子命令），160 case（94 石猴 + 66 黛玉）已落入 [blind-review-2026-10-19-worksheet.csv](./blind-review-2026-10-19-worksheet.csv)，全部 reviewer_verdict / reviewer_comment 为空。

## 1. 门 A — 全书人格构建（西游记 / 红楼梦）

- **当前状态**：未关闭。西游记 18 success / 10 fail / 383 pending；红楼梦 20 success / 12 fail / 549 pending（[证据纠正 §首版仍未闭合的实际条件](2026-10-19-t12-evidence-correction.md) 第 3 条）。
- **阻塞原因**：两部构建均 queued 在发现阶段；只有摘录联调样本的 canonical baseline，不构成全书人物构建验收。完整 book 单元在多次真实模型窗口后仍失败（[状态交接 §3 表格](2026-10-16-state-of-play.md) 中 v11 / v12 真实跑记录：西游记 17/411 单元、红楼梦 13/581 单元失败后中断）。
- **已尝试**：
  - v9 / v10 / v11 / v12 / v16 五轮真实模型构建，固定窗口 24 次，详见 [实施计划 §当前交付状态](../implementation-plan.md) 第 297–299 行。
  - 文档分析：失败主因是 discovery 阶段在片段编号层面失败，与 persona extract / review 阶段失败不重叠。
  - 未尝试把"无原文段落但出现在跨段叙述"的人物候选 / 群像 / 别名发现机制以非模型方式绕过（与产品定义冲突，不应做）。
- **最小所需信息**：
  - 模型预算授权开放 + provider 选择（保持 `kimi-coding-plan · K3` 与 8-pilot 8 真实跑 / 60+24 v2 152 真实跑同 provider 与 model record id 337 配置）
  - 决策：是优先修 discovery 的片段编号 / 别名解析 / 嵌套发现协议，还是接受"全来源构建 = 全书 + 联调样本 + bridge episode + 等待全集" 多段式进度
  - 工作区：当前隔离工作区能否仍承载全集构建（不污染既有 baseline）
- **解锁后立即可做**：从 v17 真实构建窗口（与 v16 同样 default 仍 v14/v3 兼容）跑西游记剩余 411 单元；3 单元 1 窗口，预算 24 次；同 provider 跑红楼梦剩余 581 单元。
- **不能自动继续的原因**：调用真实模型 = 真实预算，与用户"控制模型调用预算"指令冲突。

## 2. 门 B — 原著档案命题完整度（铁板桥段落）

- **当前状态**：未关闭。[实施计划 §当前交付状态](../implementation-plan.md) 第 299–300 行明确"铁板桥段落命题当前不含'桥下之水冲贯于石窍' / '倒挂流出去遮闭桥门'，而全文在 `tmp/book-corpus/西游记.txt:33`"。
- **阻塞原因**：当前 `c2da28c8` baseline 是联调样本（5 单元 / 2 段摘录），本身不含铁板桥原文段落。铁板桥 episode 只在 [book_segments](../) 的源段中（line 33 / 39 / 231 / 241 / 245 / 379 / 387 / 2023），未被人格构建阶段抽取为 `book_claims` 命题。`book_access_evidence.approved_excerpt` 因此为空，2026-10-19 长问题 真实跑（6 调用）第一题边界可知桥梁 case 触发 `UNKNOWN_REPLY` 退拒。
- **588b2be 检索侧供给层修复**（已落实）：
  - [2026-10-19-compound-anchor-bugfix.md](./2026-10-19-compound-anchor-bugfix.md) 修复 `search_terms.query_terms` 把 CJK 化合物（2 字 / 2-3 字，如 `瀑布` / `桥下` / `key9`）排在 3 字 trigram 之前，仅排序逻辑改动，索引与允许集未动。
  - 3 项 [tests/test_book_knowledge.py](../../../tests/test_book_knowledge.py) 末尾契约测试 `test_long_query_retains_compound_anchor_and_identifier_within_term_budget` / `test_long_question_keeps_bridge_compound_in_top_32_slots` / `test_long_question_recalls_owned_episode_without_granting_it_to_person` 锁住"长问题 + KEY9 仍保留 `瀑布` / `桥下` / `key9` 三个金标准子串 + 命中本人不授权他人"。
  - **本次 commit 链未跑真实模型验证 588b2be 修复**：2026-10-19 真实跑（[2026-10-19-long-query-real-run.json](./2026-10-19-long-query-real-run.json)）是修复前的快照，6 调用后 `executed_pending_semantic_review` 但 `approved_excerpt=''` 仍触发 UNKNOWN_REPLY 退拒。修复后未做单 case 重跑验证。
- **已尝试**：
  - 检索侧（已成功，588b2be 修复）。
  - 档案侧（未尝试且无法以非模型方式完成）：`backend/services/book_world/persona.py` 的 `service.run()` 必须调用 provider 抽取 + 审查；schema 触发器（[persona_schema.sql](../../../backend/services/book_world/persona_schema.sql) 第 161 / 165 行）只允许 `book_access_evidence.approved_excerpt` 引用 `book_evidence.quote_text` 子串；quote 必须来自原段，铁板桥原文段 33 行未被现有 5 单元摘录联调覆盖。
  - 直接 SQL 绕过（不可行）：会污染 canonical baseline + 触发 persona_publication 冻结 step 完整性错误（[tests/test_persona_publication_trait_lint.py](../../../tests/test_persona_publication_trait_lint.py) `test_publication_summary_always_includes_trait_lint_warnings_key` + `test_trait_lint_warning_persists_in_frozen_publication_step` 锁住）。
- **最小所需信息**：
  - 模型预算授权开放（同门 A）
  - 决定是 (a) 走全来源发现（门 A）连带产出铁板桥 episode，还是 (b) 单点开联调样本，扩到含铁板桥原文段落的临时构建（保留铁板桥 source 标识 = "非全书 + 联调样本 + bridge-episode 标签"）
  - 若选 (b)：临时构建的 `build_id` 与 `c2da28c8` baseline 隔离方案（避免与既有 baseline 混算）
- **解锁后立即可做**：
  - 选 (a)：等待门 A 落定，自然产生。
  - 选 (b)：临时 1 窗口，1 单元（铁板桥 8 段），固定 6 调用（`/test_long_query_retains_compound_anchor_and_identifier_within_term_budget` 已能保证 supply 层有 32 词化合物锚点），验证模型能在不修改原档案下报到铁板桥。最小落地形态：[`docs/plans/book-character-agents/scripts/run-bridge-probe.py`](../scripts/run-bridge-probe.py) 单一 case 探针（`boundary-knowable-stone-cave-iron-bridge`），1 次 native call，文档化的预期输出（最佳/期望/失败 三档）已就绪。
- **不能自动继续的原因**：与门 A 同 — 真实模型预算。

## 3. 门 C — 有效表达 A/B 对照（160 轮全部 `expression_enabled=false`）

- **当前状态**：未关闭。[2026-10-19-t12-evidence-correction.md](./2026-10-19-t12-evidence-correction.md) 第 2 条："160 个最终轮次的 expression_enabled 全部为 false。这批结果没有形成开启/关闭表达素材的有效 A/B，不能单靠人工评完 160 行关闭 24 对表达比较要求。"
- **阻塞原因**：所有 160 case（94 石猴 + 66 黛玉）的 `model_config.expression_enabled=false`（[2026-10-19-long-query-real-run.json](./2026-10-19-long-query-real-run.json) 第 42 行可见 `expression_enabled: false`），与默认 `expression_selection_version=expression-selection-v2` 实际未开启任何 expression sets。同 160 case 跑两次（一次 A 开启、一次 B 关闭）的对照未生成。
- **已尝试**：
  - 已确认 `expression_enabled` 由环境变量 `BOOK_EXPRESSION_ENABLED` / `BOOK_EXPRESSION_SET_IDS` 控制，详见 [release-and-rollback.md](../../release-and-rollback.md) 与 [test_book_feature_flags.py](../../../tests/test_book_feature_flags.py) 8 项。
  - 现有 A/B 仅有 T17 六组合（[2026-10-16-t17-v2-ab-reeval-evidence.md](./2026-10-16-t17-v2-ab-reeval-evidence.md)），是同 baseline 独立干净房间重跑 6 组合作为 B 路径的形状对比；不是"同一 case 表达开/关"对照。
- **最小所需信息**：
  - 模型预算授权开放（同门 A）
  - 表达素材集选择：T17 B 路径的 8 项小预算试验数据集是否仍在线；或新建一组针对 8-pilot 8 case 的 expression set
  - A/B 协议：是否同 baseline 独立干净房间（同 T17）还是同房间先后跑
- **解锁后立即可做**：1 窗口 8 case × 2 路径 = 16 case 真实跑（每路径 16 调用）；与现有 `2026-10-16-t12-8pilot-real-run-evidence.md` 形状对比。
- **不能自动继续的原因**：同门 A。

## 4. 门 D — 完整应用 / 端到端操作验收

- **当前状态**：可验证（不依赖模型预算）。本仓库 `tests/` 全部 665 项契约测试 + 3 个前端集成场景覆盖 T01–T11 / T15 / T16 / T17 链路与确定性层。
- **阻塞原因**：本仓库的"完整应用" = 端到端操作验收 = 在浏览器中从 TXT 图书馆开始 → 创建 build → 跑 persona extract → publish → 单聊 → 圆桌多人 → 暂停/继续 → 局部来源删除。8 项 [test_book_feature_flags.py](../../../tests/test_book_feature_flags.py) + 1 项 [release-gates-validation.md](./2026-10-14-release-gates-validation.md) 锁定功能开关 + 关闭流程的确定性，但实际浏览器内的工作区/角色档案/圆桌交互未被人工跑通。
- **已尝试**：
  - 全部 pytest 665 项（652 pass / 13 skip）最近 3 次跑过（[2026-10-16-state-of-play.md §1](2026-10-16-state-of-play.md) 第 47 行；本 commit 链内 1 次 c4e2b96 跑过）。
  - T16 WS 3D + 2D 切换 / 历史气泡 / 右栏同 ID/seq/正文 / 证据操作 已在 [2026-10-14-roundtable-validation.md](./2026-10-14-roundtable-validation.md) 落实。
  - T09 暂停/继续/停止 + 首次工作区恢复 + 过期租约 + 有效生成占位 + 增量重连 已在 [2026-10-14-all-queue-validation.md](./2026-10-14-all-queue-validation.md) 落实。
- **最小所需信息**：
  - 是否启动一次 1 用户 1 角色 1 房间的人工 E2E 跑通
  - 是否需要保留自动化浏览器脚本（Playwright 当前 13 skip）
- **解锁后立即可做**：
  - 创建 `tmp/accept-e2e-workspace`，按 [release-and-rollback.md](../../release-and-rollback.md) 启动 4 个环境变量全开，跑通"上传 TXT → 自动导入 build → 单聊 + 全体" → 提交一份 E2E 报告
  - 该报告可作为首版"操作验收"关闭证据
  - 最小落地形态：按 [2026-10-19-t12-e2e-walkthrough.md](./2026-10-19-t12-e2e-walkthrough.md) 的 6 步演练逐项打勾，提交 ≤ 1 页的 E2E 报告 [2026-10-19-t12-e2e-acceptance-report.md](./2026-10-19-t12-e2e-acceptance-report.md)。任何一步未达期望先记录实际值，不放开关或绕过授权。
- **不需模型预算**：是。本门是确定性层 + 流程性验收。

## 5. 门 E — 160 case 人工盲评

- **当前状态**：未关闭。工具与数据就绪，等待人工执行。
- **阻塞原因**：盲评 CLI 找不到审阅文件（`F:\god\project\Octopus\docs\plans\book-character-agents\validation\blind-review-2026-10-16.json`），需由用户 / 评审员 `start --reviewer <name>` 启动。1 已知 timeout case `expression-comfort-stone-to-failed-peer`（8-pilot 第 7 case，60s × 2 windows 超时后 manual_cancel，CLI 按 over_decline 提示）已按 over_decline 标注。
- **已尝试**：
  - 工具：[blind-review-cli.py](../../blind-review-cli.py) 6 子命令 `start` / `resume` / `stats` / `worksheet` / `import` / `regrade` 全部可用，`import` 为离线 CSV 路径，方便 Excel 党。
  - 协议：[2026-10-16-blind-review-protocol.md](./2026-10-16-blind-review-protocol.md) §3 定义 6 判定键与优先级（f > o/u），§3.1 标注 timeout case。
  - 报告模板：[2026-10-16-blind-review-report-template.md](./2026-10-16-blind-review-report-template.md) 8 节（审阅者 / 审阅时间 / stats / 关键评论 / 已知异常 / 与 §4 行衔接 / 不变量 / §4 行更新清单）。
  - 操作卡：[2026-10-16-t12-blind-review-operator-card.md](./2026-10-16-t12-blind-review-operator-card.md) 4 路径（交互式最短 / 离线 CSV / regrade / 报告）。
  - 端到端 e2e 验证（[2026-10-16-t12-blind-review-cli-e2e-evidence.md](./2026-10-16-t12-blind-review-cli-e2e-evidence.md)）：3 case 真实跑通 `start → quit → resume → stats → regrade` 链路，临时输出已清理。
- **最小所需信息**：
  - 评审员姓名（`--reviewer <name>`）用于盲评 JSON 文件名后缀
  - 评审员对该批 160 case 的开放时间窗（连续 30 分钟 - 1 小时）
  - 评审员审阅方式：交互式 CLI（按协议 6 键）or 离线 CSV（用 `import` 子命令后回写）
  - 评审员是否需要保留 Excel 中的多列对比（`import` 支持原始 CSV 全 18 列原样回写）
- **解锁后立即可做**：
  - 评审员 1: 运行 `python docs/plans/book-character-agents/blind-review-cli.py start --reviewer <name>`；按提示对每行输入 `p` / `f` / `o` / `u` / `s` / `c` / `?` / `q`
  - 评审员 2 (Excel 党)：先 `worksheet` 导出 CSV（已存在 [blind-review-2026-10-19-worksheet.csv](./blind-review-2026-10-19-worksheet.csv) 18 列），离线填写 `reviewer_verdict` / `reviewer_comment`，回 `import` 子命令导入
  - 完成后按 [2026-10-16-blind-review-report-template.md](./2026-10-16-blind-review-report-template.md) 写报告 [2026-10-16-blind-review-report.md](./2026-10-16-blind-review-report.md)
  - 按 [协议 §6](../) 把 T12 验收索引 §4 第 1 / 5 / 9 行改写为 "✅（人工盲评 160/160 判定完成）"
- **不需模型预算**：是。本门完全由人工执行。

## 6. 解锁顺序与依赖

```
门 A (全书) ┐
门 C (A/B)  ├─→ 都需要真实模型预算
门 B (档案) ┘
门 D (应用) ─→ 不需模型预算，需用户启动 E2E
门 E (盲评) ─→ 不需模型预算，需评审员 30 分钟
```

- 优先级建议（来自 [2026-10-19 证据纠正](./2026-10-19-t12-evidence-correction.md) §首版仍未闭合的实际条件 第 4 条）：先诊断允许内容未进入上下文（即门 B 层 1），再推进门 A / 门 C。
- 不变量：所有待跑项都不触碰已发布 canonical baseline；trait lint 已在 24d1959 落入门禁。
- 任何阶段新发现：按"只增不改"原则在 `validation/` 下新建 `YYYY-MM-DD-<short-name>.md`，不在 T12 验收索引 §2/§4 删改既有记录。

## 7. 关键文档路径

- 状态交接：[2026-10-16-state-of-play.md](./2026-10-16-state-of-play.md)
- 状态交接 §3.1（不需模型预算的操作员/评审员项）：同 [2026-10-16-state-of-play.md §3.1](./2026-10-16-state-of-play.md)
- T12 验收索引：[2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md)
- 证据纠正：[2026-10-19-t12-evidence-correction.md](./2026-10-19-t12-evidence-correction.md)
- 化合物锚点修复：[2026-10-19-compound-anchor-bugfix.md](./2026-10-19-compound-anchor-bugfix.md)
- 实施计划：[../implementation-plan.md](../implementation-plan.md)
- 聚合表：[2026-10-16-t12-real-runs-aggregation.md](./2026-10-16-t12-real-runs-aggregation.md)
- 盲评工具：[../../blind-review-cli.py](../../blind-review-cli.py)
- 盲评操作卡：[2026-10-16-t12-blind-review-operator-card.md](./2026-10-16-t12-blind-review-operator-card.md)
- 盲评报告模板：[2026-10-16-blind-review-report-template.md](./2026-10-16-blind-review-report-template.md)
- 发布开关：[../../release-and-rollback.md](../../release-and-rollback.md)
