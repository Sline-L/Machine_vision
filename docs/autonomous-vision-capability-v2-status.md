# Autonomous Vision Capability v2 — session status

```text
Final state: A
CAPABILITY V2 PRIMARY IDENTIFIED
FORMAL ADMISSION BLOCKED ON FRESH HOLDOUT
```

## Repo

| item | value |
| --- | --- |
| branch | `experiment/vision-capability-v2` |
| worktree | `G:/CODE/Machine_vision-vision-v2` |
| base | `srtp-web` @ `cfdbbe8` |
| backup | `backup/pre-vision-capability-v2-20260915-142247.txt` |
| measurement tag | untouched (`edgemedic-a2a3-measurement-baseline`) |
| push | see branch tip after session commits |

## 1. GitHub models

Full inventory: [v3/model-inventory.md](capability-extraction/v3/model-inventory.md).

`origin/dataset` @ `581647d` — scripts + splits + base YOLO weights; **production Scratch weights live in GearPro `model/model2/`**. Pilot `runs/` weights not in git.

## 2. Legal lightweight candidates (existing artifacts)

| route | verdict |
| --- | --- |
| classifier-only / mean | val ok, **locked FAIL** — do not rescue |
| effnet + det @960 α=0.25 | **v2 primary (exploratory)** |
| FULL | production baseline |
| smaller detector / standard det | weights **not shipped** |
| new training | spec if holdout fails — [vision-retraining-spec.md](capability-extraction/v3/vision-retraining-spec.md) |

## 3. Quality Pareto (val)

[v3/quality-latency-pareto.md](capability-extraction/v3/quality-latency-pareto.md)  
Machine output: `results/lightweight_capability_v2/val_pareto/pareto_summary.json`

Key row:

```text
effnet_det_a0.25:  Q_D,val=0.8879  R=0.9767  FPR=0.1121  target_met=yes
FULL:               Q_D,val=0.9159  R=0.9767  FPR=0.0841
```

## 4. NX latency Pareto

```text
FULL p95:           246.4 ms
effnet_det_a0.25:    85.9 ms  (0.35×)
classifiers_only:    ~58 ms   (not admissible)
```

NX artifact copy: `results/lightweight_capability_v2/latency/vision_v2_latency_summary.NX.json`

## 5. Fresh holdout?

```text
NO — test_scratch consumed; no new split in origin/dataset
```

[v3/data-split-provenance.md](capability-extraction/v3/data-split-provenance.md)

## 6. Primary candidate

```text
profile_id:   latency_degraded_v2_effnet_det
components:   EfficientNet-B0@384 + P2 detector@960
fusion:       weighted α=0.25
threshold:    0.2653394325872992 (val freeze)
```

[v3/v2-primary-candidate-freeze.md](capability-extraction/v3/v2-primary-candidate-freeze.md)

## 7. Formal evaluated?

```text
NO — blocked on fresh holdout
```

## 8. Registry status

Not updated on `srtp-web`. Proposed row remains `implemented=false`, `mission_approved=false` until holdout PASS.

## 9. Runtime implemented?

```text
NO — by design until formal PASS
gp/scratch_v5.py unchanged
```

## 10. Primary A reopened?

```text
NO — requires fresh holdout + runtime implementation + smoke first
```

## Design principles confirmed

1. **Keep detector** for cross-domain robustness (classifier-only locked FPR explosion).  
2. **Drop ResNet** for real per-inspection savings (~65% p95 on NX).  
3. **Smaller detector** needs vision retraining — not available from frozen bundle alone.

## Frozen research state (unchanged)

```text
Line 1: COMPLETE / REPRODUCED
A3 effectiveness: NOT ESTABLISHED
classifier_only_v1: REJECTED
Agent/runtime admission framework: ON MAINLINE (srtp-web)
```

## Next steps (vision team)

1. Seal **new independent holdout** (provenance doc).  
2. Preregister `latency_degraded_v2_effnet_det` one-shot eval.  
3. On PASS → registry `mission_approved=true` → runtime profile → NX smoke → Primary A pilot.
