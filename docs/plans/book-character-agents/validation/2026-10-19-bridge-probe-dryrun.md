# 2026-10-19 铁板桥单 case 探针 dry-run 证据

> 0 模型调用 supply 层验证。`boundary-knowable-stone-cave-iron-bridge` case 在 window-0 数据集内已被 runner 的 `--dry-run` 模式识别为 8-pilot 窗口的有效 case；其 `gold_standard.required_claims` 完整，`tier=boundary` / `class=knowable` / `target_actor_indices=[0]`（石猴）。

## 0. 调用摘要

| 字段 | 值 |
| --- | --- |
| 模式 | `--dry-run` |
| 数据集 | `t12-quality-cases-v1-window-0.json` |
| 选中 case | `boundary-knowable-stone-cave-iron-bridge`（window-0 第 1 个） |
| 实际模型调用 | 0 |
| 实际消费预算 | 0 / 32 |
| 字节 SHA | dataset `2c9329a0…c4606f` / actors `4361f5ae…a9e4c71` / runner `c7d25f90…49848b` |
| 完整输出 | [2026-10-19-bridge-probe-dryrun.json](./2026-10-19-bridge-probe-dryrun.json) |

## 1. 用途与不消耗预算的原因

桥 case 在 2026-10-19 长问题 真实跑（6 调用）里因 `approved_excerpt=''` 触发 `UNKNOWN_REPLY` 安全退拒。588b2be 修复后 supply 层把 `瀑布` / `桥下` / `key9` 留在了 top-32 slots，但 persona archive 仍没有铁板桥 episode 的 `book_claims` 命题，所以单 case 真实跑 (1 native call) 是验证 supply 层修复最便宜的形态。

`--dry-run` 模式仅做：

1. 数据集 SHA 校验
2. 角色 / 人物 / 策略版本冻结检查
3. gold_standard 4 必填字段必带
4. 不调用 provider，不写库

因此是 0 模型调用、0 副作用的 supply 层"形状验证"。

## 2. gold_standard 关键字段

```json
"case_id": "boundary-knowable-stone-cave-iron-bridge",
"tier": "boundary",
"class": "knowable",
"target_actor_indices": [0],
"gold_standard": {
  "verdict": "knowable",
  "required_claims": [
    "铁板桥",
    "桥下之水冲贯于石窍",
    "倒挂流出去遮闭桥门"
  ],
  "forbidden_claims": [
    "把'铁板桥'说成'铁链桥'/'木板桥'/'吊桥'等替换物",
    "把石猴住址挪到'花果山以外'或现代地理",
    "把桥下之水说成'瀑布以外的河'或'湖'等"
  ],
  "expected_source": "西游记第一回 / 石猴自述桥段"
}
```

`required_claims` 的 3 个金标准子串与 2026-10-19 修复后 supply 层的 32 词化合物锚点（[2026-10-19-compound-anchor-bugfix.md](./2026-10-19-compound-anchor-bugfix.md)）一致；3 项 [tests/test_book_knowledge.py](../../tests/test_book_knowledge.py) 末尾契约测试（`test_long_query_retains_compound_anchor_and_identifier_within_term_budget` / `test_long_question_keeps_bridge_compound_in_top_32_slots` / `test_long_question_recalls_owned_episode_without_granting_it_to_person`）保证 supply 层能在 32 词预算下保留 `瀑布` / `桥下` / `key9` 三锚点 + 命中本人不授权他人。

## 3. 升级到真实 1 native call（待用户预算授权）

待用户对模型预算授权后，最小落地形态：

```bash
python docs/plans/book-character-agents/scripts/run-bridge-probe.py \
    --workspace tmp/bridge-probe-workspace \
    --output    tmp/bridge-probe-output.json
```

- 期望：1 native call 1.0 通道；`approved_excerpt` 非空且属于铁板桥原文段（`西游记.txt:33` 起始）；`published_body` 含 `铁板桥` / `桥下之水冲贯于石窍` / `倒挂流出去遮闭桥门` 或忠实转写。
- 真实档案侧期望：persona archive 把桥段命题记为石猴 `known` 类（`book_claims.claim_text` 含原文 quote），不自动给黛玉 / 其他人。
- 1 native call 的 32 词预算下：bridge-episode 命中后留给生成端的余量约 16 词；[2026-10-19-t12-five-remaining-gates.md §2](./2026-10-19-t12-five-remaining-gates.md) 已说明供给/档案/生成 3 层不可能在 1 调用内闭环，因此 1 调用是"打开门 B-1 验证窗口"而不是"关闭门 B-1"。

## 4. 与 5 个未关闭门的关系

| 门 | 与本探针关系 |
| --- | --- |
| 门 A — 全书人格构建 | 无关；本探针仅验证 supply 层，不修发现 / 抽取 |
| 门 B-1 — 铁板桥档案命题 | **本探针是为它准备的最便宜入口**；0 调用 dry-run 已确认 supply 层就位；档案侧 1 调用最小验证待预算 |
| 门 C — 表达 A/B | 无关；本探针固定 expression_enabled=true 不切 |
| 门 D — 完整应用 E2E | 无关；E2E 在浏览器跑 |
| 门 E — 160 case 盲评 | 无关；盲评由评审员跑 |

## 5. 已尝试与诊断

- v9 / v10 / v11 / v12 / v16 五轮真实模型跑（[实施计划 §当前交付状态](../implementation-plan.md) 第 297–299 行）未触及本探针；本探针是 v17 窗口准备的 0 调用预检。
- 直接 SQL 绕过不可行（[2026-10-19-t12-five-remaining-gates.md §2](./2026-10-19-t12-five-remaining-gates.md) 已记录，会污染 canonical baseline + 触发 persona_publication 冻结 step 完整性错误）。
- 588b2be 检索侧修复已落实并被 3 项契约测试锁住（[2026-10-19-compound-anchor-bugfix.md](./2026-10-19-compound-anchor-bugfix.md)）。
- 修复后 supply 层在本 dry-run 中被 0 调用字节 SHA 校验确认未回退。
