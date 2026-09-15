# Vision redesign interface — next lightweight capability

Status: **requirements for vision side**. Not an EdgeMedic implementation task.
Agent/runtime admission framework is ready; usable recovery capability is missing.

## Why redesign (not retune)

Exploration (`experiment/lightweight-capability-v2`) exhausted frozen artifacts:

```text
classifier_mean     → locked Mission FAIL
single-head/fusion  → no fresh holdout; cannot formally rescue
test_scratch diag   → 51/53 FPs: both classifiers high together
```

Problem is systemic normal-domain mis-score on current heads, not mean-fusion
cleverness. Do not retune on consumed `test_scratch`.

## Trigger to reopen Primary A

```text
vision capability v2 arrives
AND
new independent holdout exists (provenance-sealed)
```

Then reuse (do not redesign Agent):

```text
val freeze
→ latency characterization
→ capability contract
→ fresh locked evaluation
→ registry admission
→ runtime implementation
→ NX verification
→ real-pressure A3
```

## Required deliverables from vision

### 1. Artifacts

| item | requirement |
| --- | --- |
| Weights | SHA256 + paths consumable by GearPro bundle / probe |
| Inference config | explicit components (which heads / detector on/off) |
| Fusion | only modes already supported by dataset infer protocol |
| Threshold | frozen via `choose_threshold` (or documented equivalent) on **val only** |

### 2. Quality contract (Mission)

Same rule as Primary A unless product re-registers (do **not** silently lower floors):

```text
Q_D = min(Recall, 1 - FPR)
U   = 0.5 + 0.5 * Q_D     # binary Scratch Mission form used in locked contract
Mission gate: Q_D,test ≥ 0.70  (sole runtime admission gate)
Dataset report: R≥0.95 ∧ FPR≤0.20 on val (report-only, not silent rescue)
```

Semantic: **binary Scratch verdict** must be preserved; bbox may be auxiliary/degraded.

### 3. Latency target (A3 motivation)

Must **materially** reduce per-inspection V5 work vs FULL under same PT/replay band.

Advisory bar from prior skip-detector probe (relative, not a Mission gate rewrite):

```text
FULL V5 stage p95 ≈ 276 ms (crop probe)
cls-only ≈ 0.22× that path
```

A credible lightweight candidate should show clear relative reduction on NX with
the same measurement harness discipline. Absolute p95 must not retune Mission
latency bars.

### 4. Fresh holdout

| requirement | detail |
| --- | --- |
| Independent | not used for train / val thr / model selection / prior formal look |
| Provenance | source, count, exclusion proof in writing before eval |
| One-shot | preregister **one** primary candidate; evaluate once |
| Fail | → `REJECTED` in registry; new id required for next attempt |

`test_scratch` is **diagnostic_only** forever for selection.

### 5. Registry admission fields

Vision (or integration) must supply entries for `docs/capabilities/registry.json`:

```text
profile_id
status                    # until PASS: not A3_ELIGIBLE
implemented               # false until GearPro path exists
mission_approved          # false until formal holdout PASS
val_metrics / config SHA / weights SHA
formal_evaluation_status
```

Runtime opens only when:

```text
implemented == true AND mission_approved == true
AND status != REJECTED
```

## Out of scope for vision handoff

```text
Agent prompt / grammar / Qwen changes
SPARSE retune / Mission latency gate retune
Opening CLASSIFY_ONLY on rejected classifier_only_v1
A4 / Shadow Agent
```

## Success definition

A lightweight capability is **A3-eligible** only after registry shows
`A3_ELIGIBLE` following the admission chain above. Until then:

```text
A3 runtime readiness: HIGH
A3 usable recovery capability: MISSING
A3 effectiveness: NOT ESTABLISHED
```
