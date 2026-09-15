# NX skip-detector latency pretest — result

Date: 2026-09-14 (NX)  
Harness: `edgemedic/latency_probe_skip_detector.py`  
Claim: **latency pretest only** — `CLASSIFY_ONLY` API not opened; Mission unchanged.

## Setup

```text
replay: tests/replay (gearpro-replay-v1, locked_test=false)
locator: model/model1.pt (PT)
model2: model/model2 FULL bundle
crops with gear detect: 34
warmup: 5
```

## Results (v5 stage-sum ms)

| order | FULL p50 / p95 | classifiers-only p50 / p95 | Δp95 | ratio |
| --- | --- | --- | --- | --- |
| full_first | 117.6 / 275.6 | 46.5 / **62.0** | **213.7** | 0.22 |
| cls_first | 123.3 / 260.6 | 46.1 / **63.7** | **196.9** | 0.24 |

FULL detector alone: p50 ≈ 68–75 ms, p95 ≈ 214–219 ms (dominant / high-tail).

## Verdict for Primary A step 1

```text
worth_continuing_classifier_only_route: YES
```

Skipping detector **materially** cuts per-inference V5 latency (cls-only p95 ~62–64 ms vs FULL p95 ~260–276 ms on this probe).  
Direction stays open → proceed to **step 2: Candidate A val-freeze** (B as fallback). Still do **not** open GearPro `CLASSIFY_ONLY` until contract + Mission acceptance.

Note: absolute FULL p95 here is higher than Stage-C healthy envelope (~178–186 ms) because this is a crop-level stage probe, not the live worker Mission window. Use for **relative** skip-detector gain, not to retune Mission bars.

Artifacts on NX:

```text
results/latency_probe_skip_detector/
results/latency_probe_skip_detector_cls_first/
```
