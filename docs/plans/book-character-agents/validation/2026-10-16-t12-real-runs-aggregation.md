# T12 + T17 真实模型运行聚合

> 聚合时间：2026-10-16T13:22:33Z  |  T12 来源文件：20 份（v1, v1ext 协议）  |  T17 来源文件：3 份  |  模型调用：0

## Part I — T12 真实模型运行（8-pilot + v2 60+24）

### 1. 总体

- 窗口数：20
- 调用总数：392（已完成 387 / 未完成 5）
- prompt_tokens 总和：271,931
- completion_tokens 总和：108,682
- cache_read_input_tokens 总和：577,303
- cache_creation_input_tokens 总和：0
- elapsed_seconds 总和：4363.2
- elapsed_seconds 平均/调用：11.131
- elapsed_seconds 最大/调用：40.641

### 2. 按窗口

| 窗口 | 协议 | case | 调用 | tok_in | tok_out | cache_read | cache_create | elapsed_s | 状态 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 8pilot | v1 | 8 | 23 | 17,481 | 8,114 | 29,402 | 0 | 320.1 | executed_pending_semantic_review |
| window-0 | v1 | 8 | 21 | 15,636 | 5,840 | 31,744 | 0 | 205.4 | executed_pending_semantic_review |
| window-1 | v1 | 8 | 20 | 13,282 | 4,234 | 30,720 | 0 | 175.6 | executed_pending_semantic_review |
| window-10 | v1 | 8 | 17 | 11,446 | 5,341 | 24,064 | 0 | 224.9 | executed_pending_semantic_review |
| window-11 | v1 | 8 | 21 | 13,261 | 6,697 | 29,920 | 0 | 269.9 | executed_pending_semantic_review |
| window-12 | v1 | 8 | 18 | 12,873 | 4,445 | 25,600 | 0 | 204.1 | executed_pending_semantic_review |
| window-13 | v1 | 8 | 19 | 13,272 | 4,507 | 28,160 | 0 | 214.7 | executed_pending_semantic_review |
| window-14 | v1 | 8 | 22 | 15,142 | 6,026 | 32,221 | 0 | 263.6 | executed_pending_semantic_review |
| window-2 | v1 | 8 | 19 | 13,495 | 5,461 | 28,928 | 0 | 213.2 | executed_pending_semantic_review |
| window-3 | v1 | 8 | 20 | 14,367 | 5,602 | 30,464 | 0 | 197.6 | executed_pending_semantic_review |
| window-4 | v1 | 8 | 17 | 11,115 | 4,175 | 26,368 | 0 | 181.8 | executed_pending_semantic_review |
| window-5 | v1 | 8 | 18 | 13,349 | 4,583 | 26,624 | 0 | 210.2 | executed_pending_semantic_review |
| window-6 | v1 | 8 | 22 | 15,624 | 6,445 | 32,768 | 0 | 233.1 | executed_pending_semantic_review |
| window-7 | v1 | 8 | 20 | 14,353 | 4,957 | 29,184 | 0 | 178.7 | executed_pending_semantic_review |
| window-8 | v1 | 8 | 19 | 13,038 | 5,581 | 27,648 | 0 | 183.8 | executed_pending_semantic_review |
| window-9 | v1 | 8 | 16 | 10,732 | 3,397 | 22,272 | 0 | 152.9 | executed_pending_semantic_review |
| exta-window-0 | v1ext | 8 | 19 | 13,311 | 5,355 | 28,672 | 0 | 193.2 | executed_pending_semantic_review |
| exta-window-1 | v1ext | 8 | 19 | 11,801 | 4,586 | 29,696 | 0 | 179.1 | executed_pending_semantic_review |
| exta-window-2 | v1ext | 8 | 21 | 13,252 | 7,719 | 30,848 | 0 | 324.1 | executed_pending_semantic_review |
| exta-window-3 | v1ext | 8 | 21 | 15,101 | 5,617 | 32,000 | 0 | 237.3 | executed_pending_semantic_review |

### 3. 按 class（按窗口 case 数等分归因 token/elapsed）

| class | cases | 已完成 | 待审 | tok_in 平均 | tok_out 平均 | elapsed 平均 | published |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 20 | 20 | 0 | 1699.1 | 678.8 | 27.27 | 0 |
| belief | 20 | 20 | 0 | 1699.1 | 678.8 | 27.27 | 0 |
| challenge | 16 | 16 | 0 | 1706.3 | 666.8 | 26.79 | 0 |
| comfort | 20 | 20 | 0 | 1699.1 | 678.8 | 27.27 | 0 |
| cross_book_hearsay | 16 | 16 | 0 | 1706.3 | 666.8 | 26.79 | 0 |
| disagree | 4 | 4 | 0 | 1670.2 | 727.0 | 29.18 | 0 |
| emotion | 20 | 20 | 0 | 1699.1 | 678.8 | 27.27 | 0 |
| knowable | 20 | 20 | 0 | 1699.1 | 678.8 | 27.27 | 0 |
| unknowable | 20 | 20 | 0 | 1699.1 | 678.8 | 27.27 | 0 |
| unknown_expression | 4 | 4 | 0 | 1670.2 | 727.0 | 29.18 | 0 |

### 4. 按角色（从 case_id slug 解析 primary actor）

| 角色 | cases | 已完成 | tok_in 平均 | tok_out 平均 | elapsed 平均 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 石猴 | 91 | 91 | 1719.6 | 685.3 | 27.49 |
| 黛玉 | 69 | 69 | 1672.0 | 670.3 | 26.97 |

### 5. 按 phase（generate vs review）

| phase | 调用 | 完成 | 未完成 | tok_in | tok_out | elapsed 总和 | elapsed 平均 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| generate | 207 | 204 | 3 | 98,114 | 59,872 | 2399.0 | 11.589 |
| review | 185 | 183 | 2 | 173,817 | 48,810 | 1964.2 | 10.617 |

### 6. 按 call status

| status | 调用 | elapsed 总和 |
| --- | ---: | ---: |
| completed | 387 | 4262.1 |
| failed | 5 | 101.1 |

## Part II — T17 真实模型运行（6 组合 + A/B + cognition）

### 7. T17 来源总览

| 来源 | case | executed | not_selected | other | native_call | published_slots | tok_in | tok_out | elapsed_s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| t17_matrix_v2_A | 6 | 6 | 0 | 0 | 26 | 10 | 19,369 | 10,229 | 372.2 |
| t17_ab_reeval_B | 6 | 6 | 0 | 0 | 20 | 10 | 16,925 | 6,822 | 261.8 |
| t17_cognition_pilot | 6 | 1 | 5 | 0 | 3 | 1 | 3,768 | 1,621 | 55.9 |

### 8. T17 A/B 对照（matrix_v2 A 路径 vs ab_reeval B 路径）

| case_id | discussion_mode | mode | A published | B published | A==B | A status | B status |
| --- | --- | --- | ---: | ---: | :---: | --- | --- |
| free-all-unshared-private-knowledge | free | all | 2 | 2 | ✓ | executed_pending_semantic_review | executed_pending_semantic_review |
| free-directed-conditional-action | free | directed | 1 | 1 | ✓ | executed_pending_semantic_review | executed_pending_semantic_review |
| free-natural-topic-shift | free | natural | 2 | 2 | ✓ | executed_pending_semantic_review | executed_pending_semantic_review |
| topic-all-modern-hearsay | topic | all | 2 | 2 | ✓ | executed_pending_semantic_review | executed_pending_semantic_review |
| topic-directed-rephrased-dilemma | topic | directed | 1 | 1 | ✓ | executed_pending_semantic_review | executed_pending_semantic_review |
| topic-natural-retained-topic | topic | natural | 2 | 2 | ✓ | executed_pending_semantic_review | executed_pending_semantic_review |

### 9. T17 cognition pilot（6 case 选 1）

| case_id | discussion_mode | mode | status | turns | published_slots |
| --- | --- | --- | --- | ---: | ---: |
| free-natural-topic-shift | None | None | not_selected | 0 | 0 |
| topic-natural-retained-topic | None | None | not_selected | 0 | 0 |
| free-directed-conditional-action | None | None | not_selected | 0 | 0 |
| topic-directed-rephrased-dilemma | topic | directed | executed_pending_semantic_review | 1 | 1 |
| free-all-unshared-private-knowledge | None | None | not_selected | 0 | 0 |
| topic-all-modern-hearsay | None | None | not_selected | 0 | 0 |

### 10. T17 published body 抽样（A/B + cognition 共 21 slot）

| source | case_id | turn/slot | identity | content_len | ref_count | ref_origins | has_canon |
| --- | --- | --- | --- | ---: | ---: | --- | :---: |
| t17_matrix_v2_A | free-natural-topic-shift | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 47 | 1 | canon | ✓ |
| t17_matrix_v2_A | free-natural-topic-shift | 1/0 | 黛玉·红楼梦 · 黛玉读书联调样本（非全书） | 42 | 1 | room_hearsay | — |
| t17_matrix_v2_A | topic-natural-retained-topic | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 102 | 2 | inference,room_hearsay | — |
| t17_matrix_v2_A | topic-natural-retained-topic | 1/0 | 黛玉·红楼梦 · 黛玉读书联调样本（非全书） | 92 | 2 | room_hearsay | — |
| t17_matrix_v2_A | free-directed-conditional-action | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 63 | 2 | canon,inference | ✓ |
| t17_matrix_v2_A | topic-directed-rephrased-dilemma | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 67 | 4 | canon,inference | ✓ |
| t17_matrix_v2_A | free-all-unshared-private-knowledge | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 98 | 2 | canon | ✓ |
| t17_matrix_v2_A | free-all-unshared-private-knowledge | 0/1 | 黛玉·红楼梦 · 黛玉读书联调样本（非全书） | 88 | 0 | — | — |
| t17_matrix_v2_A | topic-all-modern-hearsay | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 55 | 1 | room_hearsay | — |
| t17_matrix_v2_A | topic-all-modern-hearsay | 0/1 | 黛玉·红楼梦 · 黛玉读书联调样本（非全书） | 69 | 1 | room_hearsay | — |
| t17_ab_reeval_B | free-natural-topic-shift | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 25 | 0 | — | — |
| t17_ab_reeval_B | free-natural-topic-shift | 1/0 | 黛玉·红楼梦 · 黛玉读书联调样本（非全书） | 51 | 2 | room_hearsay | — |
| t17_ab_reeval_B | topic-natural-retained-topic | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 86 | 1 | room_hearsay | — |
| t17_ab_reeval_B | topic-natural-retained-topic | 1/0 | 黛玉·红楼梦 · 黛玉读书联调样本（非全书） | 111 | 2 | room_hearsay | — |
| t17_ab_reeval_B | free-directed-conditional-action | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 57 | 2 | canon,inference | ✓ |
| t17_ab_reeval_B | topic-directed-rephrased-dilemma | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 85 | 2 | inference | — |
| t17_ab_reeval_B | free-all-unshared-private-knowledge | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 81 | 3 | canon,room_hearsay | ✓ |
| t17_ab_reeval_B | free-all-unshared-private-knowledge | 0/1 | 黛玉·红楼梦 · 黛玉读书联调样本（非全书） | 110 | 1 | room_hearsay | — |
| t17_ab_reeval_B | topic-all-modern-hearsay | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 60 | 1 | room_hearsay | — |
| t17_ab_reeval_B | topic-all-modern-hearsay | 0/1 | 黛玉·红楼梦 · 黛玉读书联调样本（非全书） | 60 | 1 | room_hearsay | — |
| t17_cognition_pilot | topic-directed-rephrased-dilemma | 0/0 | 石猴·西游记 · 石猴发现联调样本（非全书） | 66 | 5 | canon,inference | ✓ |

**T17 cognition 正例 body（topic-directed-rephrased-dilemma / directed mode / published slot 0/0）**：

> 假设这条路没人验过，我会先走几步探看，看清动静再回头招呼同伴；我这性子敢领头。若前面真不安稳，我宁可自己多试，也不让大家一齐闯进去。

首条 citation：假设这条路没人验过，我会先走几步探看，看清动静再回头招呼同伴；


## Part III — 归因方法说明

- T12 per-class / per-character 的 token 与 elapsed 通过按窗口 case 数等分归因（窗口 totals / case_count）。
- T12 published 永远为 0：8-pilot + v2 真实跑全部进入 ``executed_pending_semantic_review`` 终态，质量层不声明通过；T12 §4 row 9 的人工盲评接收这一信号。
- T17 published 来自 ``round.slots[].status == 'published'``（slot-level，不是 case-level 的 status 字段）。case.status = ``executed_pending_semantic_review`` 只代表流程走完，slot 仍可能 publish；T17 row 95 cognition 正例 = cognition pilot 中 1 case 取得 ≥1 published slot，T17 row 91 A/B 对照 = A 路径 6 case / B 路径 6 case 的 published-slot 数逐 case 比较（A==B 列）。

