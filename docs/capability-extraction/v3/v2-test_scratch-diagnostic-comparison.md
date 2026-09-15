# V2 vs FULL on consumed `test_scratch` — DIAGNOSTIC ONLY

```text
DIAGNOSTIC ONLY
THIS DATASET IS ALREADY CONSUMED.
THIS RESULT MUST NOT BE USED FOR FORMAL CAPABILITY ADMISSION.
fresh_holdout = false
mission_approved = false
admission_proposal = false
```

Artifacts: `docs/capability-extraction/v3/diagnostic-test_scratch-v2/`

## Frozen identity check

| check | result |
| --- | --- |
| EffNet SHA match frozen | PASS |
| Detector SHA match frozen | PASS |
| V2 threshold unchanged (0.265339…) | PASS |
| fusion α=0.25 classifier_single | PASS |
| config_hash | `5cc1730c…` |

No threshold / fusion / imgsz / model selection performed.

## Metrics

| Metric | FULL | V2 | Δ (V2−FULL) |
| --- | ---: | ---: | ---: |
| TP / FP / TN / FN | 25/20/99/6 | 26/46/73/5 | — |
| Recall | 0.8065 | 0.8387 | +0.0323 |
| FPR | 0.1681 | 0.3866 | +0.2185 |
| Specificity | 0.8319 | 0.6134 | −0.2185 |
| Precision | 0.5556 | 0.3611 | −0.1944 |
| F1 | 0.6579 | 0.5049 | −0.1530 |
| **Q_D** | **0.8065** | **0.6134** | **−0.1930** |
| U | 0.9032 | 0.8067 | −0.0965 |

## Two gates

| gate | FULL | V2 |
| --- | --- | --- |
| Dataset recall ≥ 0.95 | FAIL | FAIL |
| Dataset FPR ≤ 0.20 | PASS | FAIL |
| EdgeMedic Q_D ≥ 0.70 (QL=QS=1) | PASS | **FAIL** |

## Disagreement (ResNet marginal cost)

| class | count |
| --- | ---: |
| both correct | 98 |
| FULL correct / V2 wrong | **26** (all negatives) |
| FULL wrong / V2 correct | 1 |
| both wrong | 25 |
| ResNet changed verdict | 27 |
| ResNet rescues FN | **0** |
| ResNet suppresses FP | **26** |

Removing ResNet (plus frozen lower V2 threshold) mainly **fails to suppress false positives** on negatives. Not a FN-rescue story on this consumed set.

## Conclusion (diagnostic only)

```text
V2 HAS MATERIAL QUALITY RISK
ON CONSUMED DIAGNOSTIC TEST
```

ΔQ_D ≈ −0.193. Future V3 design evidence only — **do not retune V2**.  
Formal quality admission remains blocked on **fresh Scratch-only holdout**.

This quality chain does **not** reinterpret the latency severity sweep.
