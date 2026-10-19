# 2026-10-19 长问题检索预算化合物锚点回归修复

本轮修复 evidence 未进入 model 上下文的检索侧问题：在 32 词检索预算下，先把 CJK 化合物（2 字及以上，如 `瀑布`）排在三字 N-gram（`从瀑`/`你第`/`你亲`）之前，使长问题保留关键概念。语料、允许集或 agent definition 不变。

## 触发用例与失败原因

2026-10-19 远端 window-0 长问题 "请讲一讲你第一次从瀑布外面看到的那座桥..." 8-pilot 真实跑产生了 `executed_pending_semantic_review` 终态但消息正文仅为 "这件事我没有足够的依据，无法确定"。审计发现 reader_evidence 已包含 6 行（4 行片段桥发生过/桥下细节/相关副 idea 与 trait，1 行 猴王约定 fact 带 quote，1 行 群猴 relation）；检索侧真正失败：

- `query_terms()` 对长问题按 trigram 顺序去重 32 词，`从瀑`/`你第`/`你亲`/`一次的` 等覆盖了多数槽位；`瀑布` 与 `桥` 这两个化合物丢失，导致 FTS5 MATCH 实际落到不相关的 trait 上，episode 索回但 `approved_excerpt` 为空（model 缺 quote，安全策略退拒）。
- `key9`/`KEY9` 这类 identifier 是从原文段标记里来的，会被大小写处理淹没；`query_terms()` 默认 lowercase，但忘了归一 NFKC 之前也没去重。

## 修复

- 仅排序逻辑改动。`backend/services/book_world/search_terms.py::query_terms` 在 generic 过滤后再按 `bool(re.fullmatch(r"[㐀-鿿]{3}", term))` 排序，把 2 字/2-3 字化合物放 trigram 前。索引与允许集未动。这是只影响 query selection 的纯函数。`persona_acquisition.py` 未做类型收紧（初稿尝试加 `cast(...)` 被 mypy 标 `redundant-cast`，在 amend 中已撤回）。

## 验证

- `tests/test_book_knowledge.py` 末尾追加 3 项：
  - `test_long_query_retains_compound_anchor_and_identifier_within_term_budget` 验证长问题 + 记录号 `KEY9` 经 `query_terms` 后 `瀑布` 与 `key9` 都在前 32 槽；
  - `test_long_question_keeps_bridge_compound_in_top_32_slots` 验证长问题 + 记录号同时保留 `瀑布`/`桥下`/`key9` 三个金标准子串；
  - `test_long_question_recalls_owned_episode_without_granting_it_to_another_person` 验证带 `铁板桥` episode 的 retrieve 在长问题下仍命中本人，不授权他人。
- **重要**：测试 query 用问题本身，不是把 passage 当 query——passage 自身的 37 个 2 字 bigram 会顶掉 3 字化合物 `铁板桥`；问题里的 `瀑布`/`桥下`/`key9` 才是 actor context 真正交给 FTS5 的检索子串。
- 19 项 `test_book_knowledge.py` 通过。`backend/services/book_world/search_terms.py` Ruff 通过；`persona_acquisition.py` 未改动。

## 不动内容

- 不修改任何索引 schema、book_segments、book_evidence、book_claims 或 allowed_access。
- 不修改 canonical baseline（`c2da28c8` / `58609a52`）。
- 不发起任何真实模型调用。
- 不修改 T12 任何不接受谓、review 提示词、生成提示词、chat_provider 或 room_queue。

## 下一步

- 重复跑 8-pilot 真实 window-0，下游 keeper 拿现有 6 行 reader_evidence 加长问题 term budget，验证模型是否能在不修改原档案下报到铁板桥。
