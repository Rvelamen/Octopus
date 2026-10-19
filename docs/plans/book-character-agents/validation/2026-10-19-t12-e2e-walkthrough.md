# 门 D 操作验收 — 完整应用 E2E 演练

> 门 D 是 5 个未关闭 T12 条件中**不需模型预算**、**不需人工评审**的两门之一。本文档是操作员侧的逐步演练，操作员在浏览器中按 6 步走完首版用户路径（[implementation-plan.md §目标用户路径](../../implementation-plan.md)），即可关闭门 D。
> 关联文档：[2026-10-19-t12-five-remaining-gates.md §4](./2026-10-19-t12-five-remaining-gates.md)、[2026-10-16-state-of-play.md §3.1](./2026-10-16-state-of-play.md)、[release-and-rollback.md](../../release-and-rollback.md)。

## 0. 前置确认

| 项 | 命令 / 路径 | 期望 |
| --- | --- | --- |
| 后端测试全部通过 | `python -m pytest tests/ -q --no-header` | 652 passed / 13 skipped |
| 前端类型 + 构建通过 | `npm run build --prefix frontend` | exit 0 |
| `tmp/book-corpus/西游记.txt` 存在 | `ls tmp/book-corpus/西游记.txt` | OK |
| 主开发文档已读 | [implementation-plan.md §首版验收与回滚](../../implementation-plan.md) 第 287 行附近 | 4 条硬约束已记 |

环境变量（必须全开，否则降级为只读）：

```powershell
$env:OCTOPUS_BOOK_WORLD_ENABLED         = '1'
$env:OCTOPUS_BOOK_SINGLE_CHAT_ENABLED   = '1'
$env:OCTOPUS_BOOK_GROUP_CHAT_ENABLED    = '1'
$env:OCTOPUS_BOOK_AUTO_IMPORT_ENABLED   = '1'
```

启动后端 + 桌面应用。重启后新值生效，关闭后新值生效前已存在的浏览器会话会保留上一次拉到的服务能力。

## 1. 隔离工作区

```powershell
mkdir tmp\accept-e2e-workspace
```

不要使用真实 `book_library` 工作区 — 这是一份临时验收夹具，结束后可整目录删除。

## 2. 6 步演练（每步完成后打勾）

| # | 动作 | 期望 | 关联任务 |
| --- | --- | --- | --- |
| 1 | 浏览器打开设置 → TXT 图书馆 → 上传 `tmp/book-corpus/西游记.txt` | 来源出现在列表；source_version_id 可在 SQLite 中查到 | T18 |
| 2 | 触发 build（手动按钮）→ 等 `discovery → extract → review → publication` 完 | persona 出现在档案页；build_id 可查；trait_lint_warnings 字段存在（可能为空数组） | T01-T03、T05 |
| 3 | 档案页 → 进入石猴 → 修改一项 trait → 保存 → 撤回 | history 保留 2 行；旧 trait 行冻结 | T03、T05 |
| 4 | 单聊 → 输入"水帘洞" → 等回应 | 回应含 铁板桥/桥下/瀑布 至少 1 个原文锚点；超时按秒数窗口暂停 | T06 |
| 5 | 圆桌 → 创建房间 → 加石猴 + 1 个其他人物 → 自由聊天 → @石猴 → 全体提问 | 3D 圆桌同步气泡 + 右栏同 seq 出现；@石猴定向；全体触发 | T08-T09、T16 |
| 6 | 暂停 → 等超过秒数 → 手动继续 | 暂停时圆桌 + 右栏冻结；继续后从快照恢复 | T09 |

每步期望与 [implementation-plan.md](../../implementation-plan.md) §目标用户路径一一对应；任何一步未达期望，先记录实际值（截图 + SQLite 行 + 网络响应），再回到状态交接或实施计划诊断；不要中途放开关或绕过授权。

## 3. 提交报告

按 [2026-10-16-t12-blind-review-report-template.md](./2026-10-16-blind-review-report-template.md) 同结构写一份 ≤ 1 页的 E2E 报告：

- 验收人 + 验收时间
- 工作区路径（`tmp/accept-e2e-workspace`）
- 6 步每步期望 vs 实际（异常时附 SQLite 行 / 截图）
- 已知异常（不做关账，仅记录）
- 与 T12 验收索引 §4 的衔接（本门不直接对应任何行，列入"操作验收"独立项）
- 不变量（4 条硬约束：跨工作区 / 过期 / 重复槽位 / 回写原著，本演练每步隐含确认）

报告路径：[2026-10-19-t12-e2e-acceptance-report.md](./2026-10-19-t12-e2e-acceptance-report.md)（新建）。

## 4. 关账

- 报告中 6 步全部打勾 → 门 D 关闭
- 任一步未通过 → 不关闭门 D；保留报告 + 截图 + SQLite 行作诊断，按"只增不改"原则追加 [2026-10-19-t12-e2e-acceptance-failure.md](./2026-10-19-t12-e2e-acceptance-failure.md) 并指明阻塞点

## 5. 关账后

按 [2026-10-16-state-of-play.md §3.1](./2026-10-16-state-of-play.md) 第 4 补充说明把 T12 验收索引 §4 操作验收行改为「✅（E2E 演练 6 步完成，2026-10-19）」。

## 6. 与门 E 的差异

| 维度 | 门 D（本门） | 门 E（盲评） |
| --- | --- | --- |
| 执行人 | 1 名操作员 | 1 名评审员 |
| 时间 | 不超过 1 小时（含 1 次 build） | 30-60 分钟 |
| 工具 | 浏览器 + 后端日志 + SQLite | `blind-review-cli.py` start / worksheet / import |
| 输出 | 1 份 E2E 报告 | 1 份盲评报告 + 评审记录 |
| 不需模型预算 | ✓ | ✓ |

两门独立可并行：操作员在等 build 的间隙评审员可同时启动盲评。
