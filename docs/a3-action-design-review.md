# A3 Action Design Review — latency-targeted degradation

```text
Line 1 — COMPLETE / REPRODUCED

A3 strategy study
Restart baseline      CHARACTERIZED
SPARSE latency        NOT SUPPORTED
SPARSE capacity       NOT SUPPORTED
classifier_only_v1    RUNTIME REJECTED BY MISSION CONTRACT

Primary A
BLOCKED ON ACCEPTABLE LIGHTWEIGHT VISION CAPABILITY

A3 effectiveness
NOT ESTABLISHED
```

Canonical matrix: [a3-strategy-matrix.md](a3-strategy-matrix.md).

> Current SPARSE is neither a per-inference latency recovery mechanism nor an
> effective capacity-shedding mechanism under `LatestFrame + single-worker`.

Retained findings: (1) Line 1 containment; (2) degradation must match fault; (3) capability contract refused fast-but-weak classifier-only; (4) SPARSE cadence shedding finds no capacity-continuity P1 (`inspect_wall ≳ interval`).

Do **not** invent new Agent A3 actions until a new lightweight vision capability passes frozen Mission contract. See extraction: [capability-extraction/README.md](capability-extraction/README.md).

## Corrected framing

Dataset pipeline already supports classifier-only:

```text
infer: detector=null + fusion classifier|classifier_mean|classifier_max
train: builds those candidates before detector fusion
evaluate_scratch_v5_test.py: --config reusable (one locked run per freeze)
```

FULL bundle already carries both classifiers + detector.  
`CLASSIFIER_ONLY` is likely **skip detector.pt + frozen classifier fusion/threshold**, not a new train.

Ask vision:

> Which pre-registered classifier-only candidate + threshold do we freeze, and what \(Q_D\) / Mission utility?

Do **not** ask: “can you invent classifier-only?”

## Boundary

| Owner | Owns |
| --- | --- |
| Vision (dataset) | Already owns infer/train protocol; freeze operating point + quality claim |
| Mission / product | \(Q_D\), utility floor vs 0.85 |
| GearPro | Expose named profile; atomic switch; Verify; rollback |
| EdgeMedic | Request whitelist profile only after runtime opens it |

Agent must not invent imgsz/thresholds or retune on `test_scratch`.

## Q1–Q4 (updated)

| # | Answer |
| --- | --- |
| **1** Reduce what? | Skip **P2 detector@960** inside one inspect; keep classifier path(s) |
| **2** Why latency↓? | Less GPU work per call under same `multi_bandwidth×3` — measure on NX before claim |
| **3** Mission semantics? | **PASS** — binary Scratch verdict preserved; bbox auxiliary/degraded; not Mission Verify gated |
| **4** Frozen switchable? | Dataset config yes; GearPro **not yet** (`scratch_v5` requires detector; manifest has no profiles map) |

### Known utility tension (unchanged discipline)

```text
placeholder CLASSIFY_ONLY Q_D=0.65 → U≈0.825 < Mission floor 0.85
```

Mission decision — not EdgeMedic knob.

## Pre-registered candidates (extraction)

| ID | Shape | Val thr | Val R / FPR | Status |
| --- | --- | --- | --- | --- |
| **A** `classifier_mean` both | **primary** | **0.598647…** | **0.9535 / 0.0935** | frozen; `target_met=true` |
| **B** single EfficientNet | fallback | 0.5429 | 0.9535 / 0.1215 | alternate; locked test not run |

Drafts: `docs/capability-extraction/configs/`.

## Ordered next steps (do not cross)

```text
1. Promote measurement infra → integration/injector-a3-measurement
   (see docs/integration-plan.md; exclude dataset_defects / failed prototypes)
2. Vision: new lightweight capability + fresh holdout Mission contract
3. Only then: runtime profile + Guardian/Verify + real pressure experiment
CLASSIFY_ONLY on rejected classifier_only_v1: DO NOT OPEN
Agent: no new A3 actions until step 2 lands
A3 effectiveness: NOT ESTABLISHED
```
