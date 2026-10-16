# T12 人工盲评完成报告（模板）

> 使用本模板完成 160 case 全部判定后的报告：
> 1. 运行 `python docs/plans/book-character-agents/blind-review-cli.py stats --out validation/2026-10-16.json`，把 stats 段复制到第 3 节
> 2. 从 `--reviewer <name>` 后填的姓名复制到第 1 节
> 3. 从 review JSON 顶部 `review_start` / `review_end` 字段复制到第 2 节
> 4. 从 `reviews[].comment` 字段选择 3-5 条代表性评论复制到第 4 节
> 5. 完成后把本文件保存为审阅报告，并按 §6 协议更新 [T12 验收索引](./2026-10-16-t12-acceptance-index.md) §4 三行（row 1 / row 5 / row 9）为 ✅（人工盲评 160/160 判定完成）

## 1. 审阅者

- 姓名：
- 审阅环境：
- 备注：

## 2. 审阅时间

- 开始：
- 结束：
- 总耗时：
- 暂停次数（resume 次数）：

## 3. 审阅统计（来自 `blind-review-cli.py stats`）

```
case 总数: __
  pass:         __
  fail:         __
  over_decline: __
  under_decline:__
  skip:         __
  comment:      __
  带评论:        __

by_class:
  __class__:    __
  ...

by_character:
  __character__:__
  ...
```

## 4. 关键 case 评论节选

- `__case_id__`（__class__ · __character__ · __tier__）：verdict=__，理由=__
- `__case_id__`（__class__ · __character__ · __tier__）：verdict=__，理由=__
- `__case_id__`（__class__ · __character__ · __tier__）：verdict=__，理由=__

## 5. 已知异常 case 处置

- `expression-comfort-stone-to-failed-peer`（8-pilot 第 7 case · 60s × 2 windows 全超时 → manual_cancel）：
  - verdict：
  - 处置（per 协议 §3.1 按 over_decline 提示）：

## 6. 与 T12 §4 行的衔接

按 [2026-10-16-blind-review-protocol.md](./2026-10-16-blind-review-protocol.md) §6：

- §4 row 9「人物忠实度、当前交流回应和自然程度分别盲评」= 160 case 全部 pass/fail/over/under 判定（无 skip/c）
  - 当前：__ / 160
  - 状态：__
- §4 row 5「真实模型质量结论附书籍、模型、配置和样本数量」= stats 段落附 sample 数（自动满足）
  - 当前：✅（sample 数 = 160，见 §3）
- §4 row 1「评测分别报告正确回答与正确拒绝，不用单一拒答率证明效果」= over_decline + under_decline 分开计数（自动满足）
  - 当前：✅（over_decline = __、under_decline = __，见 §3）

## 7. 不变量复核

- 本工具不调用任何模型
- 本工具不修改任何 runner 输出
- 本工具不修改任何 canonical baseline（`c2da28c8` / `58609a52`）
- 本审阅结果仅追加，不覆盖既有判定（如需重审单条，用 `regrade` 子命令）

## 8. T12 验收索引 §4 行更新清单

完成本报告后，按"只增不改"原则在 [2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md) §4 表中：

- row 1「评测分别报告正确回答与正确拒绝」证据字段追加"§3 stats 段 over_decline / under_decline 单独计数 = __ / __"
- row 5「真实模型质量结论附书籍、模型、配置和样本数量」证据字段追加"§3 stats 段 sample 数 = 160（__ pass / __ fail / __ over_decline / __ under_decline）"
- row 9「人物忠实度、当前交流回应和自然程度分别盲评」状态从「未关闭（工具就绪，待人工执行）」改写为「✅（人工盲评 160/160 判定完成，详见 [2026-10-16-blind-review-report.md]）」，证据字段填入本报告 §3 / §4 / §5 关键数据

其余 §4 行按既有 evidence 字段保持不变（不在本审阅直接关闭的项）。
