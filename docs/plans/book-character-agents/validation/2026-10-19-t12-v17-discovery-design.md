# T12 门 A v17 发现设计 — 修复 v16 窗口号 / 片段号混淆

> 本文档按"只增不改"原则追加至 T12 验收目录。v17 是 v16 的最小修复：schema 与
> validator 保持不变，仅在 prompt 中加入显式 `s = 0 起始片段编号` 约束。
> 2026-10-19 commit：discovery_v17.py 引入 + 5 项契约测试 + 现有 30 项 grouped 测试
> 全部通过（合计 55 项 0 回归）。canonical baseline `c2da28c8` / `58609a52` 字节级
> 未变（仅新增 1 个 Python 模块 + 5 个测试 + gitignore 1 行）。

## 1. 根因（v16 单元 1 失败）

v16 prompt（`backend/services/book_world/discovery_grouped.py:41-49`）的
关键句：

> scenes先按顺序分组s，完整覆盖每个片段恰好一次；每个scene只有s和可选l，人物不放scenes内。

[s16-01-progress.json](../full-book-v16-01-progress.json) 真实跑：
- 西游记 411 单元：单元 0 成功，单元 1 失败，错误
  `Discovery unit 1 failed twice: Scene 6 uses an unoffered segment`
- 红楼梦 581 单元：单元 0 成功，单元 1 失败，错误
  `Discovery unit 1 failed twice: Scene 7 uses an unoffered segment`
- book_auto_imports 状态：两个 job 均 `failed` / `error_code=discovery_failed`

[2026-10-15 嵌套发现验证](../2026-10-15-grouped-discovery-persona-validation.md)
明确描述失败原因：**"把窗口号用于片段号"**。模型把 unit_key（窗口号，如 6）
误当作 `scenes[6].s` 中的片段索引。`unit_segment_limit=12` 时，segments 范围是
`[0, 12)`，scene[6].s 写成 [6] 时偶发落在范围内，但当 scene 序号 = 7 / 8 / 9 ...
且 s 引用窗口外时立即被 validator 拒绝：

```python
# discovery_grouped.py:58
if any(s < 0 or s >= len(packet["original"]["segments"]) for s in scene.s):
    raise ValueError(f"Scene {index} uses an unoffered segment")
```

`Scene 6 uses an unoffered segment` 表示 scenes[6] 的 s 引用了
`>= len(segments)` 的索引。

## 2. v17 设计

**最小修复原则**：不变 schema、不变 validator、不动 v16 测试和现有 30 项 grouped
测试。仅在 prompt 中加入显式 `s` 约束并补充解释 `unit_key` ≠ 片段编号。

### 2.1 Prompt 增量（v16 → v17 唯一改动）

v17 prompt 在 v16 基础上扩展：

> scenes先按顺序分组s，完整覆盖每个片段恰好一次；每个scene只有s和可选l，人物不放scenes内。
> **s是本窗口中0起始的片段编号：本次窗口共有N个片段，s的每个整数都必须在[0, N)范围；
> 窗口号（unit_key、window number、第几个单元）不是片段编号，s中永远不要写窗口号。
> 例如本窗口有3个片段，s只可能是[0]、[1]、[2]、[0,1]、[0,1,2]这类组合，
> 不能出现3或更大的整数。**
> ...
> 每个appearance写scene(0起场景号)、n(该场景窗口中的原文字面称呼)、e(anchors给出的
> 原文窗口编号)、at(在场类型)...。
> **scene编号是scenes数组中0起的顺序号，与s中的片段编号不同，scene编号是场景的序号，
> s是片段编号。**

关键约束：
1. `s` 是 0 起始片段编号（不是窗口号）
2. `s` 必须在 `[0, N)` 范围（`N = 本窗口片段数`）
3. scene 编号（0 起顺序号）与 `s` 中的片段编号是不同的概念
4. unit_key / window number / 第几个单元 都不是片段编号

### 2.2 不动项

| 项 | v16 | v17 | 说明 |
|---|---|---|---|
| Schema | GroupedDiscovery | GroupedDiscovery | 复用 |
| Validator | assemble_grouped | assemble_grouped（透过 assemble_grouped_v17）| 复用 |
| discovery.py dispatch | GROUPED_VERSION | 新增 GROUPED_V17_VERSION | 5 处 tuple 加入 |
| DiscoveryConfig | 不变 | 不变 | 用户可在 config 中指定 prompt_version |
| unit_segment_limit | 默认 12 | 默认 12 | 不动；用户可自行调小 |
| unit_char_limit | 默认 8000 | 默认 8000 | 不动 |
| 30 项 grouped 测试 | 通过 | 继续通过 | 0 回归 |
| canonical baseline | 89f5f446… | 89f5f446… | 0 字节变化 |

### 2.3 文件改动

| 文件 | 类型 | 改动 |
|---|---|---|
| `backend/services/book_world/discovery_v17.py` | new | GROUPED_V17_VERSION + GROUPED_V17_PROMPT + assemble_grouped_v17 |
| `backend/services/book_world/discovery.py` | modify | 5 处 dispatch tuple 加入 GROUPED_V17_VERSION |
| `backend/services/book_world/discovery_models.py` | modify | 2 处 `discovery_model_input` tuple 加入 v17 |
| `tests/test_book_v17_discovery.py` | new | 5 项契约测试 |
| `.gitignore` | modify | 加 `!/tests/test_book_v17_discovery.py` |

合计 1 个新 Python 模块（36 行）+ 1 个新测试文件（5 项）+ 5 行 dispatch + 2 行
model_input + 1 行 gitignore。

## 3. 5 项契约测试（test_book_v17_discovery.py）

1. `test_v17_prompt_states_segment_index_constraint_explicitly`
   - 验证 prompt 包含 4 个关键约束（`s是本窗口中0起始的片段编号` / `[0, N)` /
     `unit_key` / `scene编号`）
2. `test_v17_version_is_distinct_from_v16`
   - 验证 `GROUPED_V17_VERSION == "character-discovery-v17"`
3. `test_v17_config_accepts_prompt_version`
   - 验证 DiscoveryConfig 接受 v17 字符串
4. `test_v17_reuses_v16_validator_and_catches_out_of_range_segment`
   - 验证 v17 仍用 v16 validator，且 v16 失败模式（`Scene 6 uses an unoffered
     segment`）仍被 v17 validator 拒绝
5. `test_v17_assembles_valid_reply_identical_to_v16`
   - 验证 v17 与 v16 在合法 reply 上产生相同结果

## 4. 实施验证（commit 时已落实）

- 55 项 0 回归（30 grouped + 5 v17 + 20 其他 discovery）
- 12 warnings（Pydantic V2 deprecation，pre-existing，与本改动无关）
- canonical baseline sha `89f5f446…c13d5c3` 未变（`tmp/book-corpus-workspace`
  未触发任何 build）

## 5. 解锁后立即可做

- **若 v17 修复确认有效**：在 `tmp/book-corpus-workspace` 上跑 v17 真实
  全书构建。DiscoveryConfig 指定 `prompt_version="character-discovery-v17"`。
  通过 `AutoImportRunner` 启动新 build_id（不污染 c2da28c8 / 58609a52）。
  24-call budget 起步，每窗口 12 call / 12 book。
- **若 v17 仍失败**：root cause 在 model 训练层（无法用 prompt 修），退回
  §2.1 不变 `unit_segment_limit=1` 路径，每个 unit 1 片段强制 `s: [0]`。
  西游记 3311 call / 红楼梦 2665 call / 总 ~6000 call，需用户预算授权。

## 6. 不变量

- v16 测试、30 项 grouped 测试、5 项 v17 测试全部独立可跑
- 不动 `book_claims` / `book_evidence` / `book_access_evidence` 索引
- 不动 `c2da28c8` / `58609a52` canonical baseline（仅代码层增量）
- 不动 trait lint 门禁（24d1959）
- 不动 588b2be supply 层修复
- 不动 chat-quality-protocol.md 协议词汇
