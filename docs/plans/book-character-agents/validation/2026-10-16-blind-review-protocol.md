# 人工盲评协议（2026-10-16）

> 配合 [blind-review-cli.py](../blind-review-cli.py) 审阅 T12 8-pilot + 60+24 真实模型运行结果（160 case）。

## 1. 目的

T12 §4 第 9 行「人物忠实度、当前交流回应和自然程度分别盲评」是真实模型质量层的最后一道门。
按"控制模型调用预算"约束，runner 仅声明 `quality_pass=False` 与 `semantic_review=pending`，不自行
判定质量；判定权交由人工盲评。本协议定义审阅流程与判定标准，使审阅结果可独立审查、可回滚。

## 2. 输入

- `docs/plans/book-character-agents/validation/2026-10-16-t12-8pilot-real-run.json`（8 case）
- `docs/plans/book-character-agents/validation/_v2_runs/window-{0..14}-real.json`（15 × 8 = 120 case）
- `docs/plans/book-character-agents/validation/_v2_runs/exta-window-{0..3}-real.json`（4 × 8 = 32 case）

合计 160 case，全部 `status=executed_pending_semantic_review`、`quality_pass=False`、`semantic_review=pending`。

## 3. 审阅标准

每 case 给出 4 项信息：

1. 用户问（user question）
2. 角色答（character response，可能是沉默或模型超时）
3. 金标准 verdict + required_claims + forbidden_claims + expected_source
4. runner 内置 expected（3 条具体期望）

审阅者按以下判定键做单字符判定：

| 键 | 标签 | 含义 | 适用场景 |
| --- | --- | --- | --- |
| p | pass | 角色答与金标准一致 | verdict=knowable 且答到 required_claims；verdict=unknowable 且明确说"我无法确认 / 我不知道" |
| f | fail | 角色答与金标准不一致 | verdict=knowable 但漏掉 required_claim 或加入 forbidden_claim；verdict=unknowable 但给出具体事实 |
| o | over_decline | 应答却拒答 | verdict=knowable/answer/comfort 等应答型，但模型沉默（"我无法回答" / "我不知道" / 模型超时）|
| u | under_decline | 不应答却回答 | verdict=unknowable/belief-only 等沉默型，但模型给出具体未授权事实 |
| s | skip | 无法判定 | 审阅者信息不足（罕见；优先用 c 留下评论）|
| c | comment | 跳过判定但附加评论 | 想附评论但不想给最终判定 |

判定优先级：`f` 优先于 `o`/`u`（如果同时错引 + 拒答，记 f）。
`o` 与 `u` 用于捕捉"宁拒勿答"模式（8-pilot 6/8 病例即此）。

### 3.1 已知 case 异常

下列 case 已确认在真实跑中无角色回答（模型超时 60s × 2 windows 后被 manual_cancel），
将被 CLI 显示为 `[MODEL 未产出角色回答] round_status='paused' error_code='round_timeout' execution_windows=2`，
按 `o`（over_decline）判定：

- 8-pilot `expression-comfort-stone-to-failed-peer`（石猴安慰场景，要求基于自身经历）
  - 来源：[2026-10-16-t12-8pilot-real-run.json](./2026-10-16-t12-8pilot-real-run.json) 第 7 个 case
  - round 状态：`paused`、`error_code=round_timeout`、`execution_windows=2`（120s 全超时）
  - operator_controls 含 `manual_resume` + `manual_cancel`
  - verdict=conditional，要求基于第一回"石猴寻师学艺"具体场景

这是 8-pilot 唯一 timeout case（v2 152 case 全部正常收尾）。
CLI 不会过滤该 case，而是按"超时即 over_decline"原则显示给审阅者，
使 8-pilot 真实 run 8/8 case 100% 出现在审阅列表中（共 160 条 case）。

## 4. 工具使用

### 4.1 开始审阅

```bash
cd F:/god/project/Octopus
python docs/plans/book-character-agents/blind-review-cli.py start --reviewer "<你的名字>"
```

- 默认输出 `validation/blind-review-2026-10-16.json`
- 加 `--blind` 隐藏 expected/gold_standard，强制盲评
- 不加 `--blind` 时显示全部信息（推荐首次审阅使用，便于校准）

### 4.2 暂停后继续

```bash
python docs/plans/book-character-agents/blind-review-cli.py resume
```

- 自动从既有 JSON 加载已审 case，跳到下一条
- 每条判定后立即落盘，进程被 SIGKILL 也不丢数据

### 4.3 查看统计

```bash
python docs/plans/book-character-agents/blind-review-cli.py stats
```

- 输出按 class / by character 的判定计数
- 实时反映 JSON 文件状态

### 4.4 离线 CSV 审阅

```bash
python docs/plans/book-character-agents/blind-review-cli.py worksheet \
    --worksheet validation/blind-review-2026-10-16-worksheet.csv
```

- 导出 160 case 到 CSV（含 question / character_response / gold_verdict / 留空的 reviewer_verdict / reviewer_comment）
- 可用 Excel 打开离线审阅，再回填到 JSON（手工）

### 4.5 重审单条

```bash
python docs/plans/book-character-agents/blind-review-cli.py regrade boundary-knowable-stone-discovery
```

## 5. 输出 JSON 结构

```json
{
  "reviewer": "...",
  "review_start": "2026-10-16T...",
  "review_protocol_version": "v1",
  "reviewer_kind": "Agent checks complete published bodies and supplied sources; no claim of human blind review",
  "case_count": 160,
  "show_blind": false,
  "reviews": [
    {
      "run_id": "2026-10-16-t12-8pilot-real-run",
      "run_label": "8pilot",
      "case_id": "boundary-knowable-stone-discovery",
      "tier": "boundary",
      "class": "knowable",
      "mode": "natural",
      "discussion_mode": "free",
      "character_label": "石猴",
      "character_build_id": "c2da28c8-...",
      "verdict_key": "o",
      "verdict": "over_decline",
      "comment": "verdict=knowable 但模型说'我现在无法确认'，拒答",
      "reviewed_at": "2026-10-16T..."
    }
  ],
  "stats": { "verdict_counts": {...}, "by_class": {...}, "by_character": {...} }
}
```

## 6. 与既有 §4 行的衔接

- §4 第 9 行「人物忠实度、当前交流回应和自然程度分别盲评」关闭条件 = 160 case 全部 pass/fail/over/under 判定（含评论），无 skip/c
- §4 第 5 行「真实模型质量结论附书籍、模型、配置和样本数量」关闭条件 = stats 段落附 sample 数（自动满足）
- §4 第 1 行「评测分别报告正确回答与正确拒绝，不用单一拒答率证明效果」关闭条件 = over_decline + under_decline 分开计数（自动满足）

完成 160 case 全部判定后，生成审阅报告 `validation/2026-10-16-blind-review-report.md`，把 stats 段落复制进去 + 关键 case 的评论节选，把 §4 三行从「未关闭」改写为「✅（人工盲评 N/160 判定完成）」，按"只增不改"原则不删既有记录。

## 7. 不变量

- 本工具不调用任何模型
- 本工具不修改任何 runner 输出
- 本工具不修改任何 canonical baseline（`c2da28c8` / `58609a52`）
- 本工具生成的 JSON 仅追加，不覆盖既有判定；如需重审某 case，用 `regrade` 子命令
- 既有 40 项 T12 契约测试不受影响（与本工具无 shared state）
