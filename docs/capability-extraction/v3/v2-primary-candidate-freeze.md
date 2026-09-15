# V2 primary candidate — exploratory freeze (NOT formal admission)

Status:

```text
VAL_FROZEN (exploratory)
LATENCY_CHARACTERIZED (NX)
MISSION_CONTRACT_FROZEN (pending product sign-off)
FORMAL_ADMISSION_BLOCKED_ON_FRESH_HOLDOUT
```

## Proposed profile

```text
profile_id:     latency_degraded_v2_effnet_det
display name:   EffNet + P2 detector @960 (α=0.25)
```

## Components

| component | artifact | SHA256 |
| --- | --- | --- |
| classifier | `model/model2/classifier_1.pt` (EffNet-B0@384) | `44461f4e03ff716266a3123bf1ba4611a1c965cf8776d0e523f128cf7c0b8438` |
| detector | `model/model2/detector.pt` (P2@960) | `4451e3f3664e3ad551926dc771e8cf4d0da9cd6648a9b841ea9d22bea86f15b3` |
| removed | `classifier_2.pt` (ResNet18) | — |

## Fusion / threshold (val-only freeze)

```text
fusion:     weighted α=0.25 on EffNet score + detector score
threshold:  0.2653394325872992
rule:       choose_threshold PRIMARY_FPR_CAP=0.20
```

## Val metrics (exploratory — not generalization claim)

```text
Recall:      0.9767
FPR:         0.1121
Q_D,val:     0.8879
U_val:       0.9439
target_met:  true (val)
```

## Latency (NX)

```text
p95:         85.9 ms
vs FULL:     0.35× (246.4 ms p95)
```

## Semantics

```text
Binary Scratch verdict: preserved
bbox:                   auxiliary (detector path active)
Mission contract:       same Q_D rule; Q_D,test≥0.70 on fresh holdout required
```

## Why this candidate (not classifier-only)

Locked failure showed **51/53 FPs dual-classifier high** — detector provides cross-domain stability.  
This path keeps detector, removes one classifier, achieves meaningful latency reduction on NX.

## Registry (when formal pass — do not enable now)

```json
{
  "profile_id": "latency_degraded_v2_effnet_det",
  "status": "MISSION_CONTRACT_FROZEN",
  "implemented": false,
  "mission_approved": false,
  "formal_evaluation_status": "BLOCKED_NO_FRESH_HOLDOUT"
}
```

## Do not

```text
implement runtime profile until fresh holdout PASS
retune on test_scratch
lower Mission floors
reuse classifier_only_v1 id
```
