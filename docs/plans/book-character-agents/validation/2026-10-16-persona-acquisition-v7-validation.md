# 显式获知审查（v4） 验证记录

日期：2026-10-16。

## 范围

- 真实新增独立 per-recipient 获知审查阶段，仅可撤销规范授权（monotone veto），不可越过 canonical review 的语义/范围限制。
- 修改 `backend/services/book_world/persona.py` `_save` 接收可选 `canonical_review` 与 `acquisition_review`，原 `review` 仅含 veto 后的最终授权；分离存储保证原版审查和读者档案不受影响。
- 修改 `backend/services/book_world/persona.py` `run` 中增加 v7 review prompt 的 acquire_review 阶段；缺 access 提案时直接发出空 recipients。
- 修改 `backend/services/book_world/persona.py` `get_character` 把 `acquisition_review` 投射到 access grant 的 `knowledge_review` 字段，仅供 reader 视图，不进入 Agent definition。
- 新增 `backend/services/book_world/persona_acquisition.py`：`ACQUISITION_PROMPT`、`ACQUISITION_REVIEW_VERSION`、`RecipientKnowledgeReview`、`AcquisitionReview`、`validate_acquisition_review`、`apply_acquisition_veto`。
- 新增 `REVIEW_PROMPTS["persona-review-v7"]`，内容继承 v6 但允许独立 per-recipient veto 阶段。
- 前端 `CharacterPersonaModal.jsx` 增加知识范围详情（whole/partial/unproven、unknown_parts、knowledge_evidence、excerpt_reason），仅在 reader 视图中显示。
- i18n 新增 `knowledgeScopeLabel`、`knowledgeScope.whole/partial/unproven`、`unknownKnowledgeParts`、`excerptSafetyReason`，中英文一致。
- `.gitignore` 把 `tests/test_book_persona_acquisition.py` 加入精确例外。
- 新增 `tests/test_book_persona_acquisition.py`：12 项真实回归。
- 真实诊断冻结输入已存于 `real-model-persona-acquisition-controls-v4.json`，未启用为默认；本任务未切换默认 prompt。
- 真实全书窗口状态（v16-pending-03、retention-03）保持上一阶段快照，未启动新窗口。

## 确定性测试

- `tests/test_book_persona_acquisition.py`
  - `test_acquisition_prompt_matches_frozen_diagnostic_without_promoting_default`：提示哈希与冻结诊断匹配，默认 review 仍为 v3。
  - `test_knowledge_review_is_a_monotone_veto_and_reader_only_audit`：参数化 `scope ∈ {partial, unproven, whole, whole}`、`canonical ∈ {True, False}`；验证
    - `support_state == "accepted"`，
    - `access_state` 与 `allowed = (scope == "whole") and canonical` 同步，
    - `knowledge_review.knowledge_scope` 等于 scope、含 reason 与 knowledge_evidence 引用，
    - Agent definition 中既无 `knowledge_review` 也无 `unknown_parts`（reader-only 隔离），
    - step 中 `canonical_review` 保持原始 canonical 决定、`review`（最终授权）等于 `allowed`、`acquisition_review` 保留 scope。
  - `test_invalid_knowledge_review_stops_after_one_repair_and_publishes_no_claim`：参数化 `invalid ∈ {missing, duplicate, foreign, contradiction, empty_proof}`；phase 序列为两轮 `extract/review/review_acquisition`，失败单元 1、`book_claims` 为 0、`book_build_steps.attempts == 2`。
  - `test_cancel_during_knowledge_review_cannot_save_late_proof_or_claim`：取消在 acquire_review 阶段生效；`status == cancelled`，`book_claims` 为 0，步骤 `result_json` 不含 `acquisition_review`。

- 全量结果：test_book_persona / test_book_persona_acquisition / test_book_persona_cognition / test_book_revisions 共 **65 项**通过；test_book_persona_acquisition 12 项全过。

## 类型与代码质量

- `python -m mypy backend/services/book_world/persona.py backend/services/book_world/persona_acquisition.py backend/services/book_world/persona_models.py`：仅保留无关历史错误，变更文件零新增错误。
- `python -m ruff check backend/services/book_world/persona.py backend/services/book_world/persona_acquisition.py backend/services/book_world/persona_models.py`：All checks passed!
- `npm run build --prefix frontend`：构建成功（约 3m58s），未引入新警告。

## 真实模型

- 未运行新真实模型调用。
- `real-model-persona-acquisition-controls-v4.json` 中 4 次 frozen-call 诊断结果仍作为不变快照保留；本任务未启用 v7 为默认 review prompt。
- 全书窗口 `full-book-v16-pending-03-progress.json` 与 `pending-discovery-window-03-retention.json` 为上一阶段保留下来的快照，本任务未启动新窗口。

## 已知限制

- Reader-only 视图只在 `CharacterPersonaModal` 启用；尚未接入群聊右侧详情或 reader-only endpoint 之外的展示。
- v7 prompt 仅在显式配置 `review_prompt_version == "persona-review-v7"` 时启用；默认 review 仍为 v3，未自动切换。
- 本任务未声称全书人格/真实聊天质量通过；A/B 仍属 T12。
