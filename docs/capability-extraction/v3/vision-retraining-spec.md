# Vision retraining spec — if v2 candidate fails locked holdout

Only needed if `latency_degraded_v2_effnet_det` fails fresh holdout **or** product requires Q_D closer to FULL.

## Minimum redesign target

```text
task:           binary Scratch verdict (unchanged)
semantics:      bbox auxiliary OK
Q_D,val target: ≥0.90 under PRIMARY_FPR_CAP=0.20 rule
latency p95:    ≤120 ms on NX crop probe (stretch: ≤100 ms)
architecture:   lightweight detector @640–768 + single strong classifier
```

## Why retraining may still be needed

Existing artifacts:

```text
effnet+det@960  → good latency (86 ms p95) but Q_D,val 0.888 vs FULL 0.916
classifier-only → locked Mission FAIL (domain shift)
detector-only   → fails val R target
smaller det     → no shipped weights in repo
```

## Recommended training experiments (vision team)

1. **P2 detector @640 or @768** — same data protocol; val-only selection  
2. **Distilled detector** from P2@960 teacher  
3. **Single classifier fine-tune** on hard normals identified in v1 failure analysis  
4. **Fresh holdout** sealed before any locked eval  

## Data requirements

```text
train_scratch / val_scratch — existing
NEW independent holdout   — mandatory before formal admission
test_scratch              — diagnostic_only forever for v1/v2 selection
```

## EdgeMedic interface

Deliver frozen bundle + registry row; Agent only switches `profile_id` after `mission_approved=true`.
