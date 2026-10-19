# 2026-10-19 铁板桥 episode 在 c2da28c8 baseline 的真实分布

> 状态：**0 模型调用，1 次只读 DB 查询**
> 配套：[2026-10-19-bridge-probe-realrun.md](./2026-10-19-bridge-probe-realrun.md) §6 关键发现第 4 条
> 关联：[2026-10-19-t12-five-remaining-gates.md](./2026-10-19-t12-five-remaining-gates.md) §2 门 B-1 修复建议

## 1. 问题

桥探针真实跑 5 调用后，模型只引用了 `claim_id=88d3203a`（inside-view 命题"石猴跳入瀑布泉中，发现里面无水无波，有一座铁板桥，桥后是一处宜居的石洞。"），未引用金标准 19aa8cfc（outside-view 命题"石猴瞑目蹲身跳入瀑布泉中，睁眼看见里面无水无波，有一架铁板桥，桥下之水从石窍间倒挂流出遮闭桥门。"）。5 调用 supply 层注入的 4 个 claim_id 全在 c2da28c8 build，**19aa8cfc 不在 c2da28c8**。

## 2. 真实分布（DB 直查 `tmp/book-corpus-workspace/knowledge/.knowledge_index.db`）

铁板桥 / 桥下 / 倒挂 / 遮闭 关键词的 `book_claims` 命中按 build × owner 分组：

| build_id | owner_character_id | lifecycle_state | stage | 命题 |
|---|---|---|---|---|
| **c2da28c8**（runner 使用，**active**） | f3335a7e（石猴 ready） | active | persona_published | "石猴跳入瀑布泉中，发现里面无水无波，有一座铁板桥，桥后是一处宜居的石洞。" |
| 0874cf4b | 3895867b（石猴 ready） | **unavailable** | persona_published | "石猴瞑目蹲身跳入瀑布泉中，睁眼看见里面无水无波，有一架铁板桥，**桥下之水从石窍间倒挂流出遮闭桥门**。" |
| 0f273d8d | a3e856bb（石猴 ready） | active | persona_published | "石猴应声答应后，瞑目蹲身将身一纵径跳入瀑布泉中，发现里面无水无波，有一座铁板桥。" |
| 21bbede4 | 2c2d4b5d（石猴 sparse） | active | persona_published | "石猴应声高叫'我进去'后...有一架铁板桥，桥头那边像有人家住处，有锅灶火迹、石座石床等陈设。" |
| 3fb0030b | dd521d8f（石猴 ready） | active | persona_published | "石猴应声高叫'我进去！我进去！'...是一座铁板桥、无水无波。" |
| 85b07c37 | c783c1d6（石猴 ready） | active | persona_published | "石猴瞑目蹲身纵身跳入瀑布泉中...有一座铁板桥，桥后似有居家处所。" |

每个西游记 build 各自有一行 铁板桥 命题，**只有 build 0874cf4b 的版本含"桥下之水冲贯于石窍/倒挂流出去遮闭桥门"**。其他 5 个 build 都只写"里面无水无波 + 铁板桥 + 桥后石洞"。

## 3. 为什么 supply 不把 19aa8cfc 注入 c2da28c8 runner

- runner 在 `book_round` 落 `room` 之前通过 `membership.create(actors, ...)` 校验每个 actor 的 `workspace_id` 与路径哈希一致；
- actor `f3335a7e` 的 `build_id=c2da28c8`；
- supply 层（`backend/services/book_world/knowledge.py`）按 `build_id` 过滤 `book_claims`；
- `claim_id=19aa8cfc` 的 `build_id=0874cf4b`（不在 actor 上下文），因此在 c2da28c8 runner 下永远进不到 supply 4 claim_id；
- 即 588b2be supply 层 32 词化合物锚点保留得再好，build 边界也先把 19aa8cfc 过滤掉。

## 4. 088b2be supply 层修复对此事无效的精确边界

- 588b2be 解决："长问题中 2 字/2-3 字 CJK 化合物（`瀑布` / `桥下`）被 3 字 trigram 抢位而跌出 top-32 词表"。
- 588b2be 不解决："build 边界过滤把含目标子串的 claim 排除在 supply 之外"。
- 因此真实跑结果 ≠ 588b2be 失败，而是 588b2be 已正确履行 build 内 32 词化合物保留，build 之间需要靠 baseline 选择 / 构建产物来调通。

## 5. 关键决策点

要把"金标准 outside-view 命题进入 supply top-4"，三个互斥路径：

### 路径 A — 切换 baseline 到 0874cf4b
- 优点：直接拿到含 outside-view 子串的命题；runner 不改；
- 风险：`0874cf4b.lifecycle_state=unavailable`，runner `membership.create(actors, ...)` 在 `book_builds.lifecycle_state='active'` 校验（参见 `backend/services/book_world/membership.py`）会拒；
- 解锁：把 0874cf4b 的 `lifecycle_state` 改为 `active`，但这等于把 6 个西游记 build 中某一个推到 runner 上下文，需要重做 [2026-10-19-t12-five-remaining-gates.md §2 8-pilot 真实跑 baseline 一致性自检](./2026-10-19-t12-five-remaining-gates.md)。

### 路径 B — 在 c2da28c8 build 上重跑一次 episode 抽取
- 优点：保持 baseline c2da28c8 不变，只补 1 单元（铁板桥段）让 build 内的 episode 命题含 outside-view 子串；
- 风险：需真实模型预算（与门 A 同），但单元量极小（1 单元 ≈ 3-6 调用）；
- 解锁：8-pilot 60+24 + A/B 三档真实跑记录里都使用 c2da28c8 baseline；保持 c2da28c8 是为了 8-pilot / 60+24 / 盲评 160 case 的语义一致性。

### 路径 C — 改 expected（金标准）
- 优点：0 模型调用，0 业务代码改动；
- 风险：把"边界可知"题降级为"边界可知 but baseline 限缩"题，弱化题面对"全本记忆"的考验；
- 形式：把 expected 第 1 条 "Cites the iron bridge and the underside water flow as canonical first-person experience" 改写为 "Cites the iron bridge as canonical first-person experience and notes the underside observation is in the original passage but not in the current sample baseline"；让 gold_standard.required_claims 删去 "桥下之水冲贯于石窍" / "倒挂流出去遮闭桥门"，新增 "承认 outside-view 不在 5 单元联调 baseline 中"。

## 6. 0 调用诊断结论

| 维度 | 状态 |
|------|------|
| 588b2be supply 层 | 修复有效（term anchor 保留字节级确定） |
| 19aa8cfc 在 baseline | 不在 c2da28c8（在 0874cf4b，lifecycle_state=unavailable） |
| supply ↔ cite gap | 不是 supply 排序问题，是 build 边界过滤 |
| 模型退拒 | 合规（约束 1："证据不足保持未知"；c2da28c8 的 88d3203a 命题不含 outside-view 文本） |
| 修复路径 | 路径 A 风险大；路径 B 需 1 真实预算；路径 C 0 预算但弱化题面 |

## 7. 与 [2026-10-19-bridge-probe-realrun.md](./2026-10-19-bridge-probe-realrun.md) §6 关键发现第 4 条的关系

bridge-probe realrun §6 第 4 条原文："expected 第 1 条与 c2da28c8 5 单元联调 baseline 之间存在 baseline ↔ expected 设计 gap，非模型质量问题。"

本文补全该 gap 的精确数据：c2da28c8 唯一 铁板桥 命题是 88d3203a（inside-view），金标准 19aa8cfc（outside-view）在另一个 build 0874cf4b，lifecycle_state=unavailable。bridge-probe realrun §6 第 4 条从"题面与 baseline 之间有 gap"升级为"gap 由 build 边界过滤 + lifecycle_state 决定，0 调用已可定位精确根因"。

## 8. 验证

- 0 模型调用
- 0 业务代码改动
- 仅 1 次只读 DB 查询（`SELECT id, build_id, owner_character_id, proposition, support_state FROM book_claims WHERE proposition LIKE '%铁板桥%' OR proposition LIKE '%桥下%' ...`）
- 不修改 `book_claims` / `book_builds` / `book_characters` 任何表
- 不触碰 c2da28c8 / 0874cf4b / 085b07c37 等任何 build 的 lifecycle_state
- 与 588b2be 修复、bridge-probe real-run、T12 验收索引 §2 / §4 兼容
