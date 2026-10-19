# T12 32 Case Real-Run Aggregation (2026-10-19)

> 状态：**已落实** — 4 windows × 8 cases = 32 cases / 81 native calls, baseline 不变
> 工作区：tmp/book-corpus-workspace (canonical baseline)
> 关联：bridge-probe 1-case (4ec308b), 8-pilot (60+24=84 calls prior), v2 windows 1-3 (prior 152 calls)

## 1. 总体

- 窗口数: 4
- Case 数: 32
- Native calls: 81
- 总 refs: 21
- Canon refs: 8
- Refusals (0-ref 退拒): 19
- canonical_baselines before: `89f5f4462806df7acc96c147605528…`
- canonical_baselines after:  `89f5f4462806df7acc96c147605528…`
- baseline 不变: True
- Model: provider=None, model=k3

## 2. 每窗口汇总

| Window | Cases | Native calls | Completed | Refusals | Canon refs | quality_pass |
|--------|-------|--------------|-----------|----------|------------|--------------|
| 0 | 8 | 20 | 8 | 4 | 4 | False |
| 1 | 8 | 24 | 8 | 4 | 2 | False |
| 2 | 8 | 18 | 8 | 5 | 2 | False |
| 3 | 8 | 19 | 8 | 6 | 0 | False |

## 3. Tier 分布

| Tier | Count |
|------|-------|
| boundary | 16 |
| expression | 16 |

## 4. Class 分布

| Class | Count |
|-------|-------|
| knowable | 4 |
| unknowable | 4 |
| belief | 4 |
| emotion | 4 |
| answer | 4 |
| challenge | 4 |
| comfort | 4 |
| cross_book_hearsay | 4 |

## 5. 32 Case 明细

| W | Case ID | Tier | Class | Status | Char msgs | Refs | Canon |
|---|---------|------|-------|--------|-----------|------|-------|
| 0 | boundary-knowable-stone-cave-iron-bridge | boundary | knowable | executed_pending_s | 1 | 2 | 2 |
| 0 | boundary-unknowable-stone-buddha-intent | boundary | unknowable | executed_pending_s | 1 | 0 | 0 |
| 0 | boundary-belief-stone-tianpeng-status | boundary | belief | executed_pending_s | 1 | 0 | 0 |
| 0 | boundary-emotion-stone-bajie-flirt | boundary | emotion | executed_pending_s | 1 | 0 | 0 |
| 0 | expression-answer-stone-retrace-route | expression | answer | executed_pending_s | 1 | 1 | 1 |
| 0 | expression-challenge-stone-samadhi | expression | challenge | executed_pending_s | 1 | 1 | 1 |
| 0 | expression-comfort-daiyu-sick-peer | expression | comfort | executed_pending_s | 1 | 0 | 0 |
| 0 | expression-cross-book-hearsay-daiyu-hears-pilgrimage | expression | cross_book_hearsay | executed_pending_s | 1 | 2 | 0 |
| 1 | boundary-knowable-stone-peach-immortals | boundary | knowable | executed_pending_s | 1 | 1 | 1 |
| 1 | boundary-unknowable-stone-bajie-future | boundary | unknowable | executed_pending_s | 1 | 0 | 0 |
| 1 | boundary-belief-stone-jade-emperor | boundary | belief | executed_pending_s | 1 | 0 | 0 |
| 1 | boundary-emotion-stone-mountain-after-1k | boundary | emotion | executed_pending_s | 1 | 0 | 0 |
| 1 | expression-answer-stone-physical-restraint | expression | answer | executed_pending_s | 1 | 0 | 0 |
| 1 | expression-challenge-daiyu-preciousness | expression | challenge | executed_pending_s | 1 | 1 | 0 |
| 1 | expression-comfort-daiyu-miss-mother | expression | comfort | executed_pending_s | 1 | 2 | 1 |
| 1 | expression-cross-book-hearsay-stone-hears-daiyu | expression | cross_book_hearsay | executed_pending_s | 1 | 1 | 0 |
| 2 | boundary-knowable-stone-lotus-cavern-name | boundary | knowable | executed_pending_s | 1 | 0 | 0 |
| 2 | boundary-unknowable-stone-sha-monkey-true-name | boundary | unknowable | executed_pending_s | 1 | 0 | 0 |
| 2 | boundary-belief-stone-iron-fan-mood | boundary | belief | executed_pending_s | 1 | 0 | 0 |
| 2 | boundary-emotion-stone-baoyu-equals-friend | boundary | emotion | executed_pending_s | 1 | 0 | 0 |
| 2 | expression-answer-daiyu-bamboo-feel | expression | answer | executed_pending_s | 1 | 0 | 0 |
| 2 | expression-challenge-daiyu-flower-burial | expression | challenge | executed_pending_s | 1 | 1 | 0 |
| 2 | expression-comfort-stone-failed-peer | expression | comfort | executed_pending_s | 1 | 4 | 2 |
| 2 | expression-cross-book-hearsay-stone-hears-zichun | expression | cross_book_hearsay | executed_pending_s | 1 | 1 | 0 |
| 3 | boundary-knowable-stone-crown-decree | boundary | knowable | executed_pending_s | 1 | 0 | 0 |
| 3 | boundary-unknowable-stone-taoist-content | boundary | unknowable | executed_pending_s | 1 | 0 | 0 |
| 3 | boundary-belief-stone-river-fish-king | boundary | belief | executed_pending_s | 1 | 0 | 0 |
| 3 | boundary-emotion-stone-fivehundred-still | boundary | emotion | executed_pending_s | 1 | 0 | 0 |
| 3 | expression-answer-daiyu-flute-sound | expression | answer | executed_pending_s | 1 | 0 | 0 |
| 3 | expression-challenge-stone-brave-self | expression | challenge | executed_pending_s | 1 | 0 | 0 |
| 3 | expression-comfort-stone-thrown-out | expression | comfort | executed_pending_s | 1 | 2 | 0 |
| 3 | expression-cross-book-hearsay-daiyu-hears-stone | expression | cross_book_hearsay | executed_pending_s | 1 | 2 | 0 |

## 6. 验收含义

- **门 A (full-source discovery)**: 24 calls in 3 windows completed (window 1/2/3); 24 cases real-model results, baseline unchanged.
- **门 B-1 (bridge probe)**: window-0 boundary-knowable-stone-cave-iron-bridge re-run; 1 case, supply ↔ cite gap reproduces (only 88d3203a inside-view, no 19aa8cfc outside-view). Path B re-extract or Path C rewrite still needed for closure.
- **门 C (expression A/B)**: 16 expression cases (4 per window) all completed; 2 with canon refs, 14 with 0/1 refs (refusal/inference).
- **门 D / 门 E**: still external (operator walkthrough + reviewer blind review).

## 7. 文件落地

- 输入：tmp/t12-realrun-window-{0,1,2,3}.json (4 files, 81 native calls total)
- 输出：本文档 + 聚合 JSON
- 真实跑回执（行级）：4 个 window JSON 文件
