# Scratch V3 — lightweight false-positive veto / distillation spec

```text
mode: EXPLORATION SPEC (not implemented)
semantics: Scratch-exact (NOT Scratch∨MissingHole)
formal: train/val only for development
fresh holdout: SEALED until primary V3 frozen
test_scratch: CONSUMED — direction signal only; never for tuning
```

## Motivation (from V2)

V2 proved moderate Mission-latency recovery at S1, but deleted ResNet’s FP veto:

```text
S1 V2 p95 ≈ 178 ms
Mission gate     = 190 ms
headroom         ≈ 12 ms
```

FULL−V2 under S1 ≈ 48 ms ≈ cost of restoring a second ResNet-class backbone → **forbidden**.

```text
V3 goal:
recover most of ResNet’s false-positive suppression
with ≤ ~10–12 ms extra integrated wall p95 under S1 pressure
relative to V2 (~178 → must stay < 190)
```

## Hard requirements

| axis | requirement |
| --- | --- |
| Semantics | Scratch-exact binary |
| Quality | Recover substantial FP suppression; `Q_D,val` ≥ Mission floor; preferably approach FULL |
| Latency healthy | Clearly below FULL integrated |
| Latency S1 | wall p95 **&lt; 190 ms** (preserve FULL FAIL / V3 PASS envelope) |
| Architecture | **Do not** restore a ~50 ms second backbone |
| Formal | train/val only until freeze; fresh holdout sealed |
| Registry | stay closed until explicit `mission_approved` |

## Latency budget (derived, frozen for design)

```text
budget_extra_p95_s1_ms ≈ 190 − 178 ≈ 12 ms
prefer target ≤ 10 ms margin for thermal variance
```

Any V3 candidate that breaks S1 p95 ≥ 190 is a **latency FAIL** even if quality improves.

## Exploration priority (ordered)

### P1 — Cheap negative veto on already-computed features

Reuse EffNet score + detector score / conf / count / cheap detector features:

```text
EfficientNet score
Detector score
Detector confidence / count / features
        ↓
tiny learned or calibrated veto (logistic / small MLP / calibration head)
        ↓
final verdict
```

Almost no extra backbone inference. Preferred first path.

### P2 — Distill ResNet FP-veto into single EfficientNet

Not generic distillation. Specialize student on the decision boundary:

```text
FULL says normal
EfficientNet alone tends to say defect
```

Construct only from legal train/val pairs. Goal: recover FP suppression without a second CNN.

### P3 — Ultra-light second veto branch (last resort)

MobileNetV3 / ShuffleNet-class **only if** measured extra S1 p95 ≲ 10–12 ms.  
Default assumption: this will be hard under pressure; try P1/P2 first.

## Explicit non-goals

- Do not spend fresh holdout on V2 or unfrozen V3 trials
- Do not retune V2 threshold / fusion / imgsz from `test_scratch`
- Do not restore FULL ResNet18 as the A3 profile
- Do not claim A3 effectiveness from exploration

## Acceptance gates (when a primary is frozen)

```text
1. Identity freeze (SHA, config_hash, threshold provenance)
2. Val Mission contract (Q_D / U) with QL=QS=1 assumptions documented
3. NX healthy latency < FULL
4. NX S1 paired: FULL gate FAIL, V3 gate PASS (repeatable)
5. Production path still rejects until mission_approved
6. Only then: one-shot sealed fresh holdout
```

## Research chain

```text
SPARSE → no real workload cut → recovery fails
V2     → real workload cut → moderate recovery → FP veto lost
V3     → restore FP veto at ≤~12 ms S1 budget
```

## Status

```text
SPEC READY
V3-1: ENGINEERING-QUALIFIED CANDIDATE
  - engineering freeze package complete
  - NX S1 paired latency PASS (delta_p95 ≈ +2.0 ms; p95 ≈ 178 < 190)
  - NOT validated / NOT mission_approved
V3-2: NOT STARTED (not required)
V3-3: NOT STARTED
HOLD OUT: SEALED — see v3-1-fresh-holdout-preregistration.md (NOT EXECUTED)
REGISTRY: UNCHANGED
PARAM LOCK: no V3-1 changes before holdout adjudication
```

See [v3-1-gate-completion.md](v3-1-gate-completion.md),
[v3-1-engineering-freeze/v3-1-engineering-freeze.md](v3-1-engineering-freeze/v3-1-engineering-freeze.md).
