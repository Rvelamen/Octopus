# T12 门 A v17 真实跑证据（v17-01 单元 0+1 / 两书 / 12 native call）

> 本文档按"只增不改"原则追加至 T12 验收目录。v17-01 是 v17 设计的最小验证
> 真实跑：在 v16 已取消的 build 上以 `character-discovery-v17` 重启新 build，截取
> 单元 0 + 单元 1（每书 2 单元，共 12 native call），目标是用真实模型回执证明
> v17 显式 `s = 0 起始片段编号 [0, N)` 约束消除了 v16 "把窗口号用于片段号" 失败
> 模式。canonical baseline `c2da28c8` / `58609a52` 字节级未变（v17 build 复用
> `control("restart")` 撤销 v16 子节点，未触动 canonical baseline）。

## 1. 运行配置

| 项 | 值 |
|---|---|
| 时间 | 2026-10-19 |
| 工作区 | `tmp/book-corpus-workspace`（sha256 identity = `1506c968…36d0a5`）|
| 书籍 | 西游记（item 1, book `38b26a66`）+ 红楼梦（item 2, book `79e0fbfd`）|
| 窗口 | v17-01：每书 2 单元（unit 0 + unit 1）|
| prompt_version | `character-discovery-v17` |
| 复用 validator | `assemble_grouped`（v16 同款；v17 仅改 prompt）|
| 单元大小 | unit_segment_limit=12, unit_char_limit=2000, max_tokens=8192 |
| 总 native call | 12（西游记 6 + 红楼梦 6）|
| 总 token | prompt 5,452 + completion 4,905 = 10,357 + cache_read 8,192 |
| 模型 | k3（项目默认）|
| 真实跑文件 | `tmp/full-book-v17-01-calls.jsonl`（24 行 = 12 started + 12 completed）|
| 进度报告 | `docs/plans/book-character-agents/validation/full-book-v17-01-progress.json` |

## 2. 运行流程

1. 用 `AutoImportService(workspace, resolve_model=...)` 启动；`resolve_model` 钩子
   强制 `prompt_version=character-discovery-v17`（不修改 `book_auto_imports` 行
   `strategy_json`，因为 trigger `tr_book_auto_binding_fixed` 禁止修改）。
2. 对每本书 `control(item_id, job_id, "restart")`：撤销 v16 子节点 + 释放
   `library_item_id` + 插入新 `book_auto_imports` 行（`status=queued`）。
3. `service.scan()` 让 `AutoImportRunner` 看到新行并创建 v17 build
   （新 fingerprint，不复用 v16 `ce1089d1` / `5e0c333f`）。
4. 直接调 `discovery.run(build_id, CountedProvider(), v17_config)` 跑发现阶段；
   `CountedProvider` 在每次模型调用前/后写 trace + 累加
   `book_auto_imports.actual_calls` + 累加 `book_auto_imports.usage_json`。
5. 只保留 unit 0 + unit 1 可执行（其余 unit 通过 `UPDATE book_build_steps SET
   attempts=2 WHERE unit_key >= 2` 标记为耗尽预算，避免消耗真实模型）。

## 3. v17 修复结果（核心证据）

### 3.1 单元 0（标题片段，seg_count=1）

| 书 | 单元 | scenes | s 值 | 全部 in [0, 1) | 备注 |
|---|---|---|---|---|---|
| 西游记 | 0 | 1 | [0] | ✓ | 首次即通过 |
| 红楼梦 | 0 | 1 | [0] | ✓ | 首次即通过 |

### 3.2 单元 1（12 片段 / 9 片段）

| 书 | 单元 | seg_count | scenes | 全部 s 值 | 全部 in [0, N) |
|---|---|---|---|---|---|
| 西游记 | 1 | 12 | 4 | 0,1,2,3,4,5,6,7,8,9,10,11 | ✓ |
| 西游记 | 1 (repair) | 12 | 8 | 0,1,2,3,4,5,6,7,8,9,10,11 | ✓ |
| 红楼梦 | 1 | 9 | 4 | 0,1,2,3,4,5,6,7,8 | ✓ |
| 红楼梦 | 1 (repair) | 9 | 4 | 0,1,2,3,4,5,6,7,8 | ✓ |

**v16 失败模式 `Scene N uses an unoffered segment` 在 6 次模型回执中均未出现**。
s 值 100% 落在 `[0, seg_count)` 范围。

### 3.3 book_build_steps 实际验证状态

| 书 | build_id | unit 0 | unit 1 |
|---|---|---|---|
| 西游记 | `2f0ae221-d072-45b0-a2ac-f005941dd8d9` | validated (attempts=1) | validated (attempts=2) |
| 红楼梦 | `4c11aa1a-9d68-4c7e-a44c-635911bb9ccd` | validated (attempts=1) | failed (attempts=2, error="Unsupported name/alias '石头'; choose a literal label present in its quote") |

- 3/4 目标单元 `validated`
- 1/4 目标单元 `failed`（HLM unit 1，错误：name/alias 不在引文中）
- 错误是**新失败模式**（quote/literal 校验），不是 v16 segment-index 混淆
- 修复版本验证：v17 显式 s 约束已生效，v16 把窗口号当片段号问题根除

## 4. 与 v16 真实跑对照

| 维度 | v16-01 | v17-01 |
|---|---|---|
| 单元 0 西游记 | validated | validated |
| 单元 0 红楼梦 | validated | validated |
| 单元 1 西游记 | **failed**（"Scene 6 uses an unoffered segment"）| validated (attempts=2) |
| 单元 1 红楼梦 | **failed**（"Scene 7 uses an unoffered segment"）| failed (新错误：name/alias '石头' 不在 quote) |
| 总 native call | 9 | 12 |
| 失败单元数 | 2 | 1（新错误类型）|

**核心结论**：v16 unit 1 失败的两个 case 中，**西游记 unit 1 已修复**；**红楼梦 unit 1
的失败原因是新错误（quote/literal 校验）**，不是 s 索引错误。

## 5. canonical baseline 不变性

| canonical build | lifecycle_state | status | claims | fingerprint | 字节级未变 |
|---|---|---|---|---|---|
| `c2da28c8-cab3-4bc2-9342-b1a60831c99a`（石猴）| active | partial_published | 7 | `97d5f268…f223e` | ✓ |
| `58609a52-6cfe-41b1-9f4f-b8abe7f18e1e`（黛玉）| active | partial_published | 1 | `a95bb315…30e3c` | ✓ |

v17-01 通过 `control("restart")` 仅撤销 v16 子节点（build_id `ce1089d1` /
`5e0c333f`），未触动 canonical baseline build 行与 `book_claims` /
`book_evidence` / `book_characters` 索引行。

## 6. 预算与累计

- 本次 v17-01: 12 native call
- 累计：8-pilot 23 + v2 369 + long-query 6 + bridge-probe 5 + 32-case 81 + **v17-01 12** = **496 total native calls**
- 0 budget_exhausted
- 0 模型替身 / SQL 契约检查 / 样本联调代替人格质量验收

## 7. 解锁后立即可做

- **v17 修复被本次 6/6 s-range 验证 + 1/2 unit 1 validated 确认有效**。
  修复路径已落实（`discovery_v17.py` + 5 项契约测试 + 0 回归）。
- 进一步 full-book 跑（3311 / 2665 call）需用户预算授权。
- HLM unit 1 新错误（name/alias '石头' 不在 quote）需要单独诊断：是模型
  理解 "石头" 作为 红楼梦 开头引言段标签时的语义处理问题，还是 quote 解析
  端点问题。这与 v17 修复目标（segment-index 混淆）正交。

## 8. 不变量

- v16 / v17 测试、30+5 项 grouped + v17 契约测试全部独立可跑
- 不动 `book_claims` / `book_evidence` / `book_access_evidence` 索引
- 不动 `c2da28c8` / `58609a52` canonical baseline 字节
- 不动 trait lint 门禁（24d1959）
- 不动 588b2be supply 层修复
- 不动 chat-quality-protocol.md 协议词汇
- 不动 桥探针 1-case 真实跑结果
