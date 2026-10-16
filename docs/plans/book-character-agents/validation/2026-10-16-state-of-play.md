# 书籍人物 Agent 状态交接（State of Play）

日期：2026-10-16
范围：M1–M4 首版任务中所有可在不消耗模型预算情况下落实的子项
目的：让下一位接手人（或本人下次会话）能直接看到「已完成、待解锁、待条件」三档，避免重新推导

## 1. 已完成（确定性层，全部已 commit + push）

| 任务 | 验证位置 | 关键提交 | 备注 |
| --- | --- | --- | --- |
| T01 来源准备 | [2026-10-12-source-validation](./2026-10-12-source-validation.md) | (历史提交) | 51 通过 |
| T02 人物候选 | [2026-10-12-discovery-validation](./2026-10-12-discovery-validation.md) | (历史提交) | 77 通过 / 13 跳过 |
| T03 原著档案 | [2026-10-12-persona-validation](./2026-10-12-persona-validation.md) | (历史提交) | 94 通过 |
| T04 证据纠错 | [2026-10-12-revision-validation](./2026-10-12-revision-validation.md) | (历史提交) | 108 通过 |
| T05 知情与表达 | [2026-10-12-knowledge-expression-validation](./2026-10-12-knowledge-expression-validation.md) | (历史提交) | 124 通过 |
| T06 受限单聊 | [2026-10-12-single-chat-validation](./2026-10-12-single-chat-validation.md) | (历史提交) | 154 通过 |
| T07 房间记忆 | [2026-10-13-room-memory-validation](./2026-10-13-room-memory-validation.md) | (历史提交) | 172 通过 |
| T08 跨书多人 | [2026-10-14-group-room-validation](./2026-10-14-group-room-validation.md) | (历史) + (本批次) | 13 真实 k3 + 1 同名 @ 契约 |
| T09 全体与控制 | [2026-10-14-all-queue-validation](./2026-10-14-all-queue-validation.md) | (历史提交) | 暂停/继续/停止 |
| T10 自动导入 | [2026-10-14-automatic-import-validation](./2026-10-14-automatic-import-validation.md) | (历史提交) | 199 通过 |
| T11 来源生命周期 + 跨工作区矩阵 | [2026-10-14-source-lifecycle-validation](./2026-10-14-source-lifecycle-validation.md) + 矩阵契约测试 (本批次) | (历史) + (本批次) | 9 lifecycle + 1 矩阵 |
| T12 题集 + 切片器 | [2026-10-16-t12-v2-pool-slicer-evidence.md](./2026-10-16-t12-v2-pool-slicer-evidence.md) | 9073987 / bcced1d / 75f2af2 | 84 题金标准 + 45 窗口 |
| T15 秒数设置 | (无独立验证文档) | e29231c | 3 契约测试 |
| T16 圆桌 UI | [2026-10-14-roundtable-validation](./2026-10-14-roundtable-validation.md) | (历史提交) | WS 3D + 2D 切换 |
| T17 主题/自由 | [2026-10-15-discussion-matrix-v2-validation](./2026-10-15-discussion-matrix-v2-validation.md) + cognition 修复 | 70eed8e / 0e87b78 / 24d1959 | 26/28 + lint 门 |
| T18 TXT 图书馆 | 与 T01 同一来源链 | (历史提交) | — |

最近 10 个 commit（`git log --oneline -10`）：

```
3bc9548 docs(state): add state-of-play handoff summarizing closed deterministic gates and budget-blocked items
e29231c test(t15): pin saved timeout default flows into chat submit for directed + all modes
24d1959 docs(test): wire trait-completion lint into persona publication summary
75f2af2 docs(t12): record v2 84-case pool + slicer in acceptance index
bcced1d docs(t12): record v2 pool + slicer + 0-model-call verification evidence
9073987 test(t12): pin v2 84-case pool + slicer + 15 contract tests + dry-runs
0e87b78 test(t17): pin suggested correction wording passes the lint
70eed8e test(t17): pin trait-vs-completion lint + matrix v2 deterministic reeval
3183cb7 docs(implementation-plan): record 9-task contract test suite + 577 passed
ac1dcad test(t04-t11,t16): add 9 deterministic per-task contract tests
```

分支：`feature/pdf-annotation-chat-and-clip-fix`（已推送远端，与 `main` 同步无冲突）
完整项目 pytest：**609 通过 / 13 跳过**（13 跳过为既有 Playwright 缺失）

## 2. 当前确定性已锁定的"隐形护栏"

这些不是新功能，但在预算解锁后会让真实模型跑变得安全可审计：

1. **trait-vs-completion lint** 接入 `publish_personas`（commit 24d1959）
   - 文件：`backend/services/book_world/proposition_alignment.py` + `persona_publication.py:132-165`
   - 5 项契约测试：`tests/test_persona_publication_trait_lint.py` 全部通过
   - 下次真实构建首次触发即对外暴露 `trait_lint_warnings`，可作为 review 端门禁
2. **T15 秒数设置 read-path** 已锁（commit e29231c）
   - 3 项契约测试覆盖 directed + all 模式 + DB reopen
   - 文件：`tests/test_book_task_contracts.py` 末尾
   - 真实单聊/全体提问未来跑时，秒数不会再悄悄回到默认
3. **金标准 84 题池 + 切片器** 已落地（commit 9073987）
   - 文件：`docs/plans/book-character-agents/validation/t12-quality-cases-v2.json` + `scripts/book_world/slice_t12_pool.py`
   - 4 个 canonical 窗口已通过 runner `--dry-run`，数据层就绪
4. **T17 cognition 防护文字冻结**（85 项 model contracts 第 70–80 项）
   - `tests/test_book_model_contracts.py` 已锁 v9/v14/cognition 防护

## 3. 待解锁：模型预算授权

| 阻塞项 | 解除条件 | 解除后立即可做 | 预计预算 |
| --- | --- | --- | --- |
| T12 8-pilot 真实模型跑 | 开放 `kimi-coding-plan · K3` provider 授权 + 设定模型调用预算 | 在 4 个 canonical 窗口跑完 8-pilot；按 `--real` 模式记录 token/elapsed；与 dry-run 比对 | 小（≤ 50 次调用） |
| T12 84 题金标准真实跑 | 同上 + 接受更长时间窗 | 跑 15+15+15=45 个 8-pilot 窗口，累计 360 次 | 中（~360 次） |
| T17 matrix v2 A/B 重评 | 同上 | 用修正后 baseline（`rephrase_claim` 修订）重跑 matrix，预期 `topic-natural-retained-topic` 与 `topic-directed-rephrased-dilemma` 从 limited_behavior_pass 提升 | 小（~28 次） |
| 人工盲评 | T12 真实跑数据落地后 | 对 8-pilot × 4 窗口 = 32 条人物发布做忠实度/表达自然度盲评 | 人工（不计预算） |

**不变量**：所有待跑项都不会触碰已发布 canonical baseline；trait lint 已在 24d1959 落入门禁。

## 4. 超出本次范围（不会在首版中实现）

| 项 | 原因 | 评估 |
| --- | --- | --- |
| T04 修订机制新增 `rephrase_claim` 类操作 | T17 诊断明确标"超出本次范围" | 若未来仍需对现存 build `c2da28c8` 产出修订版，需先扩展操作集，再以 lint 为 review 一侧的预检；该扩展与本次 wiring 互不阻塞 |
| T17 cognition 第 3 题（条件推演 · 复杂分支） | 现有真实模型调用未稳定通过 | 待 v9 防护文字冻结后下次真实跑复评 |
| 60 项边界 + 24 项表达完整题集的真实跑 | 阻塞于预算 | 题集已撰写为 [t12-quality-cases-v2.json](./t12-quality-cases-v2.json)；仅运行层未跑 |

## 5. 接手人下一步操作清单

按用户"持续推进下一项已满足依赖的任务"指令和"不修改任何签名、不消耗预算"约束：

1. **若预算已解锁**：直接按 [2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md) §4 表格顺序执行 8-pilot → 60+24 → A/B 三档真实跑；每档独立 git commit + runner 输出保存
2. **若预算未解锁**：所有确定性已就绪；任何"未关闭"项均无法在零预算下推进；停止本分支工作并向用户回报状态
3. **若发现新问题**：在 `validation/` 下新建 `YYYY-MM-DD-<short-name>.md`，按"只增不改"原则追加到 T12 验收索引 §2/§4；不在实施计划里改写既有记录

## 6. 关键文档路径

- 实施计划：[docs/plans/book-character-agents/implementation-plan.md](../../implementation-plan.md)
- 详细设计：[docs/plans/book-character-agents/detailed-design.md](../../detailed-design.md)
- 任务清单：[docs/plans/book-character-agents/tasks/](../../tasks/)
- 验证记录：[docs/plans/book-character-agents/validation/](./)
- 验收索引：[2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md)
- 发布开关：[docs/plans/book-character-agents/release-and-rollback.md](../../release-and-rollback.md)
- 阶段验证（每任务）：同 `validation/` 目录
- 真实模型记录：`t17-matrix-v2-agent-review.json`、`t17-cognition-agent-review.json`
- 诊断与 lint：[2026-10-16-t17-trait-completion-diagnosis.md](./2026-10-16-t17-trait-completion-diagnosis.md)

## 7. 预算与不变量自检

- 模型调用：0（本 commit 链不消耗任何 provider 调用）
- canonical_baselines_unchanged：True
- 新增代码：纯函数 + 单元测试，可独立审查、可回滚
- 现有 API 签名变更：0（`rounds.submit` / `BookRoomTimeoutSettings` / `AgentDefaultsRepository` / `publish_personas` 全部不变）
- 发布开关：未变更（4 个环境变量与 [release-and-rollback.md](../../release-and-rollback.md) 一致）
- 文档原则：只增不改（按 [2026-10-16-t12-acceptance-index.md](./2026-10-16-t12-acceptance-index.md) §6）
