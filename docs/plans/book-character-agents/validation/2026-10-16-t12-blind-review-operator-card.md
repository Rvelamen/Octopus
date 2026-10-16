# T12 人工盲评操作卡（2026-10-16）

> 真实模型质量层最后一道门 — §4 row 9 / row 81 / row 82 / row 84 / row 85 / row 87 / row 88 / row 89 / row 92 / row 95 / row 96 共 11 条「未关闭」项的统一收口（row 87 rephrase_claim 操作 + 12 条总条数变 11 条均由 T15 秒数设置关闭带来；按"只增不改"原则本卡原文保留 row 87 编号但 §4 表内已删除该行）。
>
> 本卡不调用任何模型、不修改任何 runner 输出、不修改任何 canonical baseline（`c2da28c8` / `58609a52`），仅指引审阅者完成 CLI 操作。

## 1. 当前已就绪

- **CLI**：`docs/plans/book-character-agents/blind-review-cli.py`（6 子命令：`start` / `resume` / `stats` / `worksheet` / `import` / `regrade`）
- **协议**：[2026-10-16-blind-review-protocol.md](2026-10-16-blind-review-protocol.md)（§1-§7，含 6 判定键 / 优先级 / 已知 timeout case / 输出 JSON 结构 / 关闭条件 / 不变量）
- **已填好的 160 case worksheet**：[blind-review-2026-10-16-worksheet.csv](blind-review-2026-10-16-worksheet.csv)（1 header + 160 行 = 8-pilot 8 + 15 canonical × 8 + 4 ext-a × 8；每行含 `case_id` / `run_label` / `tier` / `class` / `character` / `mode` / `question` / `character_response` / `round_status` / `round_error_code` / `has_response` / `gold_verdict` / `required_claims` / `forbidden_claims` / `expected_source` + 留空的 `reviewer_verdict` / `reviewer_comment`）
- **聚合报告**（盲评抽样用）：[2026-10-16-t12-real-runs-aggregation.md](2026-10-16-t12-real-runs-aggregation.md)（Part I 6 张 T12 表 + Part II 4 张 T17 表，含 by_class / by_character 抽样维度）
- **完成报告模板**：[2026-10-16-blind-review-report-template.md](2026-10-16-blind-review-report-template.md)（8 节骨架：审阅者 / 审阅时间 / stats / 关键评论 / 已知异常 / 与 §4 行衔接 / 不变量 / §4 行更新清单）

## 2. 审阅者最短路径（推荐首次）

```bash
cd F:/god/project/Octopus

# 1) 启动交互式审阅（默认 --reviewer 读 $USER 环境变量；不加 --blind 以便校准）
python docs/plans/book-character-agents/blind-review-cli.py start

# 2) 看到 case 时按 6 个单字符键：
#    p = pass / f = fail / o = over_decline / u = under_decline / s = skip / c = comment
#    ? = 当前 case 帮助 / q = 保存并退出（可 resume 续审）

# 3) 暂停后继续（自动跳过已审）：
python docs/plans/book-character-agents/blind-review-cli.py resume

# 4) 实时统计（按 verdict / class / character 三维）：
python docs/plans/book-character-agents/blind-review-cli.py stats
```

判定规则见协议 §3，优先级 `f` 优先于 `o`/`u`（同时错引 + 拒答记 `f`）。

## 3. 离线审阅路径（推荐 CSV 党）

```bash
# 1) 重导出 worksheet（已存在；只有改动源数据后才需要重导）
python docs/plans/book-character-agents/blind-review-cli.py worksheet \
    --worksheet validation/blind-review-2026-10-16-worksheet.csv

# 2) 用 Excel 打开 CSV，对每行填入 reviewer_verdict (p/f/o/u/s/c) + reviewer_comment

# 3) 导入回审阅 JSON：
python docs/plans/book-character-agents/blind-review-cli.py import \
    --worksheet validation/blind-review-2026-10-16-worksheet.csv

# 4) 跑统计看结果：
python docs/plans/book-character-agents/blind-review-cli.py stats
```

## 4. 重审单条

```bash
python docs/plans/book-character-agents/blind-review-cli.py regrade <case_id>
# 例：python docs/plans/book-character-agents/blind-review-cli.py regrade boundary-knowable-stone-discovery
```

## 5. 已知异常

- **8-pilot 第 7 case `expression-comfort-stone-to-failed-peer`**：模型 60s × 2 windows 全超时后被 `manual_cancel`，CLI 会按 `[MODEL 未产出角色回答] round_status='paused' error_code='round_timeout' execution_windows=2` 提示，按 `o`（over_decline）判定。详见协议 §3.1。
- 160 case 中**无其他已知异常**；其余 159 case 全部 `status=executed_pending_semantic_review`，按协议 §3 正常判定。

## 6. 完成后写报告

完成 160 case 全部判定后，按模板 [2026-10-16-blind-review-report-template.md](2026-10-16-blind-review-report-template.md) 生成审阅报告 `validation/2026-10-16-blind-review-report.md`：
1. 跑 `python docs/plans/book-character-agents/blind-review-cli.py stats --out validation/2026-10-16.json` 取得 stats
2. 把 stats 段落复制到模板第 3 节
3. 从 review JSON 选 3-5 条代表性 case 评论填到第 4 节
4. 按协议 §6 把 T12 验收索引 §4 三行（row 1 / row 5 / row 9）从「未关闭」改写为「✅（人工盲评 160/160 判定完成）」，按"只增不改"原则不删既有记录

模板已就绪在 [2026-10-16-blind-review-report-template.md](2026-10-16-blind-review-report-template.md)，可直接复制改名为 `2026-10-16-blind-review-report.md` 后填字段。

## 7. 不变量（与 CLI / 协议一致）

- 本工具不调用任何模型
- 本工具不修改任何 runner 输出
- 本工具不修改任何 canonical baseline（`c2da28c8` / `58609a52`）
- 本工具生成的 JSON 仅追加，不覆盖既有判定；如需重审某 case，用 `regrade` 子命令

## 8. 状态

- 51 项 T12 契约测试 + 14 项 T 任务契约测试 + 39 项 runner 守卫 + 7 项聚合守卫 = 111 项确定性层全过
- 160 case 真实跑数据已落 `validation/_v2_runs/` + 8-pilot 真实跑 + 3 份 T17 真实跑
- 聚合表 Part I（20 窗口 / 392 native call / 0 published）+ Part II（21 published body 抽样，1/6 cognition 正例身体已抽出）+ Part III（归因方法说明）已落
- **唯一外部条件**：人工盲评 160/160 判定
