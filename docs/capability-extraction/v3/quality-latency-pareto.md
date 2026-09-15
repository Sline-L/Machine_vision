# Quality × latency Pareto (v3) — exploratory val + NX

**Not formal admission.** Threshold rule: `PRIMARY_FPR_CAP=0.20`, key `(fpr≤cap, recall, -fpr, precision)`.

Detector per-image scores back-calculated from frozen FULL val CSV + classifier CSV (α=0.25 mean).

## Quality (val_scratch, n=150)

| candidate | components | Q_D,val | U_val | R | FPR | target_met |
| --- | --- | ---: | ---: | ---: | ---: | :---: |
| FULL α=0.25 mean | cls1+cls2+det@960 | **0.9159** | 0.9579 | 0.9767 | 0.0841 | yes |
| **effnet_det α=0.25** | **cls1+det@960** | **0.8879** | **0.9439** | **0.9767** | **0.1121** | **yes** |
| classifier_mean | cls1+cls2 | 0.9065 | 0.9533 | 0.9535 | 0.0935 | yes |
| effnet only | cls1 | 0.8785 | 0.9393 | 0.9535 | 0.1215 | yes |
| detector only | det | 0.8224 | 0.9112 | 0.8837 | 0.1776 | no |

Full table: `results/lightweight_capability_v2/val_pareto/pareto_summary.json`

## Latency (NX crop probe, 34 crops, PT)

| candidate | p50 (ms) | p95 (ms) | vs FULL p95 |
| --- | ---: | ---: | ---: |
| FULL | 120.9 | **246.4** | 1.00× |
| classifiers_only | ~50 | ~58 | ~0.24× |
| **effnet_det α=0.25** | **69.1** | **85.9** | **0.35×** |

Source: NX `results/lightweight_capability_v2/latency/vision_v2_latency_summary.json` (2026-09-15).

## Pareto reading

```text
Quality–latency trade-off (existing frozen weights):

  FULL          — best Q_D,val; highest latency
  effnet+det    — keeps detector; −65% p95 vs FULL; Q_D,val −0.028 vs FULL
  cls-only paths — faster but locked Mission FAIL (classifier_only_v1)
```

**Design conclusion:** v2 should **keep detector**, drop ResNet, not pursue classifier-only rescues.

Smaller detector @640/512 (V2-D) requires **weights not in repo** → training/redesign.

## Candidate tags

| candidate | tag |
| --- | --- |
| FULL | baseline (production) |
| classifier_mean | REJECTED path |
| effnet_det_a0.25 | **NEXT_CAPABILITY_CANDIDATE** (exploratory) |
| detector resize variants | blocked (no shipped weights) |
