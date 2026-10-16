# T12 真实模型运行聚合（8-pilot + v2 60+24 = 160 case 链路）

> 聚合时间：2026-10-16T13:03:58Z  |  来源文件：20 份（v1, v1ext 协议）  |  模型调用：0

## 1. 总体

- 窗口数：20
- 调用总数：392（已完成 387 / 未完成 5）
- prompt_tokens 总和：271,931
- completion_tokens 总和：108,682
- cache_read_input_tokens 总和：577,303
- cache_creation_input_tokens 总和：0
- elapsed_seconds 总和：4363.2
- elapsed_seconds 平均/调用：11.131
- elapsed_seconds 最大/调用：40.641

## 2. 按窗口

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

## 3. 按 class（按窗口 case 数等分归因 token/elapsed）

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

## 4. 按角色（从 case_id slug 解析 primary actor）

| 角色 | cases | 已完成 | tok_in 平均 | tok_out 平均 | elapsed 平均 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 石猴 | 91 | 91 | 1719.6 | 685.3 | 27.49 |
| 黛玉 | 69 | 69 | 1672.0 | 670.3 | 26.97 |

## 5. 按 phase（generate vs review）

| phase | 调用 | 完成 | 未完成 | tok_in | tok_out | elapsed 总和 | elapsed 平均 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| generate | 207 | 204 | 3 | 98,114 | 59,872 | 2399.0 | 11.589 |
| review | 185 | 183 | 2 | 173,817 | 48,810 | 1964.2 | 10.617 |

## 6. 按 call status

| status | 调用 | elapsed 总和 |
| --- | ---: | ---: |
| completed | 387 | 4262.1 |
| failed | 5 | 101.1 |

## 7. 归因方法说明

- per-class / per-character 的 token 与 elapsed 通过按窗口 case 数等分归因（窗口 totals / case_count）。
- 这是 runner 输出 schema 不在 ``calls`` 层携带 case_id 时的确定性近似：每个窗口内 8 个 case 通常共享相同 runner budget，所以等分是稳定近似。
- published 永远为 0：8-pilot + v2 真实跑全部进入 ``executed_pending_semantic_review`` 终态，质量层不声明通过；T12 §4 row 9 的人工盲评接收这一信号。

