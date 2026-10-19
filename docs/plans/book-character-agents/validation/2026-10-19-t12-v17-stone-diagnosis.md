# T12 门 A v17-01 HLM unit 1 「石头」失败诊断

> 本文档按"只增不改"原则追加至 T12 验收目录。诊断 v17-01 HLM unit 1 暴露的
> `Unsupported name/alias '石头'; choose a literal label present in its quote`
> 错误的根因。结论：该错误**不是 v17 修复目标（s 索引混淆）的回归**，而是
> v17 显式 s 约束生效后、被分组 prompt 推到更细粒度人物发现路径时、模型
> 在更稀疏约束下暴露的预存在 v6+ 提示词 / 校验路径的合规问题。
> canonical baseline `c2da28c8` / `58609a52` 字节级未变（v17-01 通过
> `control("restart")` 仅撤销 v16 子节点，未触动 canonical baseline）。

## 1. 错误现场

v17-01 HLM unit 1 model 回执（截取 trace 中的 `stone` 人物）：

```json
{
  "identity": "new",
  "kind": "person",
  "appearances": [
    {"scene": 1, "n": "此石", "e": 4, "at": "silent"},
    {"scene": 2, "n": "石头", "e": 5, "at": "active",
     "a": [
       {"n": "弟子", "e": 5, "o": 0},
       {"n": "石", "e": 6},
       {"n": "石头", "e": 6},
       {"n": "这石", "e": 7}
     ]
    }
  ]
}
```

`book_build_steps.result_json` 错误信息：

```
Unsupported name/alias '石头'; choose a literal label present in its quote
```

## 2. 根因（代码层 + 数据层）

### 2.1 校验器位置

`backend/services/book_world/discovery.py:536-539`：

```python
if label is not None and label.strip() not in span.quote:
    raise ValueError(
        f"Unsupported name/alias {label.strip()!r}; choose a literal label present in its quote"
    )
```

该校验对每个 character 与 alias 都跑：name/alias 字面字符串必须出现在它
自己的 evidence.quote 中。

### 2.2 模型选了错误的 segment

查看 HLM unit 1 输入（来自 trace 的 started 事件 `input.segments` + `anchors`）：

| e | 内容（含名字频次）|
|---|---|
| 0 | 章节标题，无人物 |
| 1 | 作者自云，「我」 |
| 2 | 提示语，无人物 |
| 3 | 列位看官，无人物 |
| 4 | 炼石补天，「此石」 1 次 |
| **5** | **僧道来访，segment 内仅 1 个「此石」/「这石」/「石」，无「石头」字面** |
| 6 | 二仙对话，含「石头」 2 次 |
| 7 | 僧道携石，含「石头」 1 次 |
| 8 | 空空道人见石，含「石」多次 |

模型为 `石头` 选了 `e:5` 作为 active 出场，但 segment 5 的 quote 不含字面
「石头」二字。校验器按 "name/alias 不在自己的 quote 内" 拒绝。**正确选择应是
`e:6` 或 `e:7`**（那里有字面 "石头"）。

### 2.3 提示词已有该约束

`backend/services/book_world/discovery_models.py:137`：

> name/alias 不在自己的 quote 时，修复为当前原文称呼或换成真实含该称呼的
> 原句；没有这种引文就不声称已知名字。

`discovery_models.py:138`：

> 完成前逐条核对 name in quote、alias in alias.quote、existing 的字面 alias、
> 场景覆盖和 local_character_key。修复时同时核对所有条目，不只修改第一个错误。

提示词已**显式要求**模型自检 name in quote，但模型在第一次 attempt 即触雷，
第一次 repair 也未修正（仍选 e=5），第二次 attempt 后失败（`attempts=2`）。
这表明 v17 显式 s 约束**不引入**该错误，但分组 prompt 的"更多人物"鼓励
触发了该合规路径的概率上升。

### 2.4 v16 同时存在该错误

v16 build `5e0c333f` 在 units 1 / 2 / 15 各报 1 次 `Unsupported name/alias '石头'`
错误（不是 unit 1 的 s 索引错误）。v16 HLM unit 1 因分组粒度更粗（s 校验先
于 quote 校验失败），从未进入 quote 校验阶段。

## 3. v17 修复与「石头」错误正交

| 失败类型 | v16 unit 1 出现 | v17 unit 1 出现 | v17 修复后是否回归 |
|---|---|---|---|
| `Scene N uses an unoffered segment`（s 索引混淆）| ✓ 西游记 + 红楼梦 unit 1 | ✗ 0 复现 | **不是回归** |
| `Unsupported name/alias '石头'`（name/alias 不在 quote）| ✓ 红楼梦 units 1/2/15 | ✓ 红楼梦 unit 1（attempts=2 仍未修正）| **不是回归**（v6+ 既存）|

v17 修复目标（s 索引混淆）已 100% 消除（6/6 s-range 验证）。`石头` 错误是
**预存在的 v6+ 提示词合规路径**，v16 / v17 都暴露此问题。

## 4. 不修此处对全书的实际影响

- 该错误不阻塞 v17 修复目标验证（s 索引 0 复现）
- 该错误不阻塞 v17 完整跑（每个失败单元的 cost ≤ 2 attempts，可被 batch error
  报告统计，不影响其他单元）
- 修复需新 prompt 文本（v17.1）+ 1 项契约测试，不需重写 schema / validator
- 若用户授权 v17.1 修复，再补 1 个 ~12 native call 的真实跑即可验证

## 5. 不变量

- 不动 v16 / v17 测试、30+5 项 grouped + v17 契约测试
- 不动 `book_claims` / `book_evidence` / `book_access_evidence` 索引
- 不动 `c2da28c8` / `58609a52` canonical baseline 字节
- 不动 trait lint 门禁（24d1959）
- 不动 588b2be supply 层修复
- 不动 chat-quality-protocol.md 协议词汇
- 不动 桥探针 1-case 真实跑结果
- v17.1 修复（非本诊断范围）需用户授权
