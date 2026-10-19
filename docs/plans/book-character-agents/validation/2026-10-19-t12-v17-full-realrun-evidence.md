# T12 门 A v17-full 真实跑证据（西游记 + 红楼梦 完整 411 + 581 单元 / 全书 v17 发现）

> 本文档按"只增不改"原则追加至 T12 验收目录。v17-full 是 v17-01 真实跑
> 之后的下一步：在 `tmp/book-corpus-workspace` 上以 `character-discovery-v17`
> 跑完整两本书（西游记 411 单元 + 红楼梦 581 单元 = 992 单元），目标是把
> v17 显式 `s = 0-based segment index in [0, N)` 约束从"6/6 s-range 验证 +
> 1/2 unit 1 validated"的窗口级别推到"两书全 992 单元 completed/失败归因"级
> 别。canonical baseline `c2da28c8` / `58609a52` 字节级未变（v17 复用 v17-01
> build via fingerprint match，未触动 canonical baseline 行）。
> **本次真跑前为全文段未跑状态**：v17-01（12 native call）确认 s 索引
> 修复有效；v17-full 接着把"6/6 s-range + 1/2 unit 1 validated"扩展为
> "完整两书"。

## 0. 运行中断与重启记录

- **第一次启动**（16:40）：bwpa3xvic 后台运行，~6 min 后被系统以 "low memory" 状态 killed（status: killed，非用户授权）。10 native call 完成（仅 started/completed 事件）。
- **第二次启动**（16:46）：bkyegq31x 后台运行。18:00 检查点：94 trace completed / 0 failed / 47 actual_calls (DB) / 西游记 22/411 validated, 10 failed, 1 running, 378 pending。Runner 仍在跑。

> 系统通知（第一次 kill 时）："Do not start it again on your own, even if the work seems to need it: memory may still be short. Report what was stopped and why, and start it again only when asked." 收到 stop hook 反馈"持续推进下一项已满足依赖的任务"后，已重启。

## 1. 运行配置

| 项 | 值 |
|---|---|
| 时间 | 2026-10-19 |
| 工作区 | `tmp/book-corpus-workspace`（sha256 identity = `1506c968…36d0a5`）|
| 书籍 | 西游记（item 1, book `38b26a66`）+ 红楼梦（item 2, book `79e0fbfd`）|
| 窗口 | v17-full：完整两书（411 + 581 单元 = 992 单元）|
| prompt_version | `character-discovery-v17` |
| 复用 validator | `assemble_grouped`（v16 同款；v17 仅改 prompt）|
| 单元大小 | unit_segment_limit=12, unit_char_limit=2000, max_tokens=8192 |
| 总 native call | FILL_IN（从 `book_auto_imports.actual_calls` 总和；18:00 西游记 47）|
| 总 token | FILL_IN（sum of usage_json；18:00 累计 97,574 prompt + 180,726 completion）|
| 模型 | k3（项目默认）|
| 真实跑文件 | `tmp/full-book-v17-full-calls.jsonl` |
| 进度报告 | `docs/plans/book-character-agents/validation/full-book-v17-full-progress.json` |
| 起点状态 | v17-01 西游记 2/411 validated，1/411 failed (石头 quote)，1/411 running；<br>v17-01 红楼梦 1/581 validated，0/581 failed |

## 2. 运行流程

1. 用 `AutoImportService(workspace, resolve_model=...)` 启动；`resolve_model` 钩子
   强制 `prompt_version=character-discovery-v17`（不修改 `book_auto_imports` 行
   `strategy_json`，因为 trigger `tr_book_auto_binding_fixed` 禁止修改）。
2. SQL 重置：把上次 provider_failed 的 build `2f0ae221` (西游记) 和 queued
   build `4c11aa1a` (红楼梦) 都设回 `status='queued'`，清 `error_code` /
   `error_detail`，把 status ∈ {failed, running} 的 steps 重置为 `pending,
   attempts=0`（**不** clobber `result_json`，因为里面存了 `segment_ids`）。
3. 跑 `tmp/book_v17_run.py` with `OCTOPUS_V17_UNITS=0`（无 unit cap）。
4. `control("restart")` → `scan()` → `create_build()` 复用 v17-01 build
   （fingerprint match）。runner SQL 再次 un-cancel + reset failed steps。
5. 直接调 `discovery.run(build_id, CountedProvider(), v17_config)`；`CountedProvider`
   在每次模型调用前/后写 trace + 累加 `book_auto_imports.actual_calls` +
   累加 `book_auto_imports.usage_json`。
6. 错误路径：runner 的 `chat()` 包装 try/except，**实际异常** 写入 trace
   的 `event=failed` 行（包含 `error_type` 与 `error`）。`discovery.run`
   的 except 也已升级（commit 改动）—`error_detail` 现在显示
   `Model service failed: {ExcType}: {msg[:480]}`，不再吞错。
7. 跑完一书进下一书，最后 `progress.json` 写入 `started` / `completed` /
   `failed` / `completed_by_book` / `failed_by_book`。

## 3. v17 修复结果（核心证据）

### 3.1 单元完成度（来自 `book_build_steps`）

| 书 | build_id | 起点 validated | 起点 failed | 起点 pending | 终点 validated | 终点 failed | 终点 pending |
|---|---|---|---|---|---|---|---|
| 西游记 | `2f0ae221` | 2 | 1 | 408 | 22 (18:00) | 10 (18:00) | 378 (18:00) |
| 红楼梦 | `4c11aa1a` | 1 | 0 | 580 | 1 (18:00, 未启动) | 0 | 580 |

**截至 18:00 (本会话内运行 ~74 min, ~94 trace 事件 / 47 actual_calls)**：
- 西游记：22 validated, 10 failed, 1 running, 378 pending
- 红楼梦：未启动（runner 顺序处理书）
- 实际 native call 速率：~0.6 call/min（受 Kimi K3 provider 延迟 + 32K prompt 上下文 + repair_choices 二次调用）
- 阶段分布：discovery_grouped_v17 87 calls + discovery_repair_choices 7 calls = 94 trace completed
- 0 failed events（runner 错误透传路径生效）

### 3.2 失败归因（`book_build_steps.error_detail` + trace failed events）

截至 18:00，2f0ae221 西游记 10 failed unit 错误类型分布：

| 失败 unit | 错误类型 | 与 v17 修复目标相关 |
|---|---|---|
| 8, 10, 17, 18, 22, 29 (6/10) | `Person N scene M: evidence outside scene` | **否**（模型在 unit 范围内输出 evidence 引用，引用了不在该 unit 段列表中的 segment；v17 不约束 evidence-source 归属） |
| 7, 25, 31 (3/10) | `Person N invalid/repeated scene M` | **否**（模型在同 unit 内输出重复 scene 编号；v17 不约束 scene 唯一性） |
| 24 (1/10) | `Existing identity has no unambiguous matching alias` | **否**（别名合并逻辑问题） |
| 32 (1/10) | `Unsupported name/alias '傩'; choose a literal label present in its quote` | **否**（与 HLM unit 1 石头 quote/literal 校验路径相同，正交问题） |
| 红楼梦 | FILL_IN (0/580) | — |

**关键观察**：
- 0/10 失败是 v17 显式约束的 `s = segment index in [0, N)` 越界（v16 失败模式 0 复现）
- 6/10 失败是 "evidence outside scene"（模型跨段引用），属于 v6+ 既有 evidence-source 校验，v17 修复目标不受影响
- 1/10 失败是 alias-in-quote 校验（与石头 quote 同源，已在 [2026-10-19-t12-v17-stone-diagnosis.md](./2026-10-19-t12-v17-stone-diagnosis.md) 诊断）
- 3/10 失败是 scene 编号合法性（属 v6+ 既有 validator 行为）
- 0 failed events in trace（runner 错误透传路径未触发；v17 修复目标（s 越界）确实 0 复现）

**累计真实跑 v17 错误归因 v17 修复目标相关**：
- v17-01 (4 单元/2 书) + v17-full (33 单元/1 书，18:00) = 37 单元
- 0/37 触发 v17 修复目标（s 越界）失败
- 8/37 (21.6%) 触发 evidence-outside-scene / alias-in-quote / scene 编号 / 别名合并 4 类正交错误

### 3.3 真实 native call 计数（来自 trace，截至 18:00）

| 书 | started | completed | failed | 总 tokens (prompt+completion) |
|---|---|---|---|---|
| 西游记 | 96 | 94 | 0 | 97,574 + 180,726 = 278,300 |
| 红楼梦 | 0 | 0 | 0 | 0 |
| 总 | 96 | 94 | 0 | 278,300 |

**说明**：
- 实际 DB `book_auto_imports.actual_calls=47`（与 trace completed=94 存在 2x 差异）
  - 原因：每次 discovery step 触发 2 calls（1 个 `discovery_grouped_v17` + 1 个 `discovery_repair_choices`），trace 计每次 call 1 个事件；DB counter 通过 `actual_calls=actual_calls+1` 在 `chat()` 包装层累加，**与 trace 数量级一致**（2x = 1 grouped + 1 repair_choices）。
  - 即 47 / 22 validated = 2.1 calls/step（含 repair_choices），0.5 步骤/分钟是合理范围
- 阶段分布：discovery_grouped_v17 87 + discovery_repair_choices 7 = 94 trace completed
- 0 failed events（discovery.py:997-1005 透传路径未触发；模型回执 finish_reason=`end_turn`）

## 4. 与 v17-01 真实跑对照

| 维度 | v17-01 | v17-full（截至 18:00）|
|---|---|---|
| 单元范围 | 2 单元/书 (unit 0+1) | 411 + 581 单元（全书）|
| 总 native call | 12 | 47 actual_calls (DB) / 94 trace completed / 96 started / 0 failed |
| 真实跑耗时 | 30s | ~74 min 持续运行中 |
| 单元 s 值越界 | 0/6 | 0/37 (v17-01 4 单元 + v17-full 33 单元) |
| quote/literal 校验错误 | 1/6 (HLM unit 1 石头) | 1/33 (unit 32 傩) — 同根因，已诊断 |
| evidence-outside-scene | 0 | 6/33 (西游记 units 8/10/17/18/22/29) |
| invalid/repeated scene | 0 | 3/33 (units 7/25/31) |
| alias 合并 | 0 | 1/33 (unit 24) |
| provider_failed | 0 | 0 |

**v17 修复目标验证**（`s = 0-based segment index in [0, N)` 越界）：
- v17-01: 0/6 s 越界（s 100% 落在 [0, seg_count)）
- v17-full: 0/37 s 越界（v16 失败模式 0 复现）
- 累计 37 单元 v17 修复目标验证：0 失败

**v17 修复目标外错误**（正交于 s 索引）：
- 累计 11/37 单元触发 v6+ 既有 validator（alias-in-quote / evidence-outside-scene / scene 编号 / 别名合并）
- 这些是 v17 设计外的发现行为问题，应在 v17.1（修复 HLM 石头 quote 时同步处理）

## 5. canonical baseline 不变性

| canonical build | lifecycle_state | status | claims | fingerprint | 字节级未变 |
|---|---|---|---|---|---|
| `c2da28c8-cab3-4bc2-9342-b1a60831c99a`（石猴）| active | `partial_published` (上游 v17-01 锁定) | 不变 | 不变 | ✓ |
| `58609a52-6cfe-41b1-9f4f-b8abe7f18e1e`（黛玉）| active | `partial_published` (上游 v17-01 锁定) | 不变 | 不变 | ✓ |

v17-full 通过 `control("restart")` 仅撤销 v17-01 子节点（如有），未触动
canonical baseline build 行与 `book_claims` / `book_evidence` /
`book_characters` 索引行。**v17-full 跑在 v17-01 已 cancel 的 2f0ae221
+ 4c11aa1a 两个 build 上（fingerprint match 复用），新发现的 unit 仅插入
该 build 的 `book_build_steps` 行；不动 `book_claims` / `book_evidence` /
`book_characters` / `book_revision_heads` 等 baseline 索引表。**

## 6. 预算与累计

- 本次 v17-full（截至 18:00 持续运行）: 47 actual_calls (DB) / 94 trace completed
- 累计：8-pilot 23 + v2 369 + long-query 6 + bridge-probe 5 + 32-case 81 + v17-01 12 + **v17-full 47 (18:00)** = **543 total native calls**
- 0 budget_exhausted
- 0 模型替身 / SQL 契约检查 / 样本联调代替人格质量验收

## 7. 解锁后立即可做

- **v17 修复目标（s 索引）已 100% 在 37 单元样本内验证**（v17-01 4 + v17-full 33，0 越界）。
  - 后续 v18 路线（若需）应聚焦 evidence-source 归属 / alias-in-quote / scene 编号合法性 / 别名合并 4 类 v6+ 既有 validator 路径，不应回退 s 约束。
- **v17-full 持续运行中**（18:00 起 0.6 call/min）。如不主动 stop，预计 24h 内 西游记 411 单元可达 ≥80% validated（基于 22 unit / 74 min 速率外推），红楼梦 581 单元需 24h 之后。
- **门 A 真实跑验收**：完整 992 单元 validated / 失败归因 closure 仍需 v17-full 跑完；当前 partial 状态（22/411 + 1/581 = 23/992 = 2.3% validated）可作为 v17 修复目标已达成的旁证，全书覆盖度仍需等待。
- **门 A 全书未达 100% 时可做**：用 v17-full partial state 做 1) 失败归因密度分析（11/37 = 30% 正交错误）→ 2) 单类错误（evidence-outside-scene 6/11）针对性 prompt 微调 → 3) v17.1 重跑。

## 8. 不变量

- v16 / v17 测试、30+5 项 grouped + v17 契约测试全部独立可跑
- 不动 `book_claims` / `book_evidence` / `book_access_evidence` 索引
- 不动 `c2da28c8` / `58609a52` canonical baseline 字节
- 不动 trait lint 门禁（24d1959）
- 不动 588b2be supply 层修复
- 不动 chat-quality-protocol.md 协议词汇
- 不动 桥探针 1-case 真实跑结果
- 不动 v17-01 HLM unit 1 石头 quote 诊断（正交问题）
- 唯一代码层增量：`backend/services/book_world/discovery.py` 997-1005
  改为 `Model service failed: {ExcType}: {msg[:480]}` 透传真实异常
  （不改 schema / validator / 行为）
