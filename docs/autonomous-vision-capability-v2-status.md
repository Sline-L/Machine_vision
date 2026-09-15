# Autonomous Vision Capability v2 — session status

```text
Final state: A (Scratch v2 exploratory primary)
Teammate audit: B (useful components; formal capability incomplete)
```

## Repo

| item | value |
| --- | --- |
| branch | `experiment/vision-capability-v2` |
| worktree | `G:/CODE/Machine_vision-vision-v2` |
| base | `srtp-web` @ `cfdbbe8` |
| backup | `backup/pre-vision-capability-v2-20260915-142247.txt` |
| dataset upstream | `Machine_vision_dataset/main` @ `dca0306` (see teammate audit) |
| measurement tag | untouched (`edgemedic-a2a3-measurement-baseline`) |

---

## Teammate Latest Vision Update Audit

Full audit: [v3/teammate-latest-audit.md](capability-extraction/v3/teammate-latest-audit.md).

| # | question | answer |
| --- | --- | --- |
| 1 | Teammate latest commit? | `dca030654eefd84e15b0bf16a391e1affc17af0b` @ 2026-09-13T23:43:46Z |
| 2 | New models / pipelines? | **Missing Hole V1**, **unified_defect_v1**, `missing_hole_runtime.py`, `infer_gear_defects.py`, expanded `docs/missing_hole_v1/` |
| 3 | unified_defect_v1 trained? | **YES** — EffNet-B0@512 single classifier; config + leaderboard complete |
| 4 | Missing Hole V1 trained? | **YES** — 34 experiments + locked test eval 2026-09-13 |
| 5 | Fresh holdout? | **NO** — `test_scratch` and `test_missing_tooth` both consumed; unified has no sealed test |
| 6 | Best v2 primary? | **`latency_degraded_v2_effnet_det`** (Scratch-exact). unified_classifier **not** promoted (superset semantics, weaker diagnostic test) |
| 7 | Changed VISION REDESIGN judgment? | **Partially.** Teammate work confirms classifier-only / unified paths are **not** drop-in Scratch recovery; effnet+det remains best **existing-artifact** Scratch candidate. Retraining spec still valid if holdout fails. |

```text
Teammate verdict: B
TEAMMATE PRODUCED USEFUL COMPONENTS,
BUT FORMAL CAPABILITY STILL INCOMPLETE
```

Key teammate findings:

- `unified_classifier.pt`: ~15.6 MB, one forward @512, but **Scratch∨MissingHole** semantics → Mission change.  
- Unified diagnostic on locked test: R=0.7606, FPR=0.4177 — worse than specialist OR.  
- Missing Hole V1 mature for **its own** mission; test consumed; do not auto-merge into GearPro.  
- GitHub weights are **LFS pointers**; GearPro bundle unchanged.

---

## 1. GitHub models

[v3/model-inventory.md](capability-extraction/v3/model-inventory.md) + [teammate-latest-audit.md](capability-extraction/v3/teammate-latest-audit.md).

Production Scratch weights: GearPro `model/model2/`. New teammate weights: `Machine_vision_dataset` LFS under `outputs/*/final/`.

## 2. Legal lightweight candidates (Scratch mission)

| route | verdict |
| --- | --- |
| classifier_only_v1 | REJECTED locked |
| unified_classifier (teammate) | **superset — not Scratch admissible** |
| effnet + det @960 α=0.25 | **Scratch v2 exploratory primary** |
| FULL | production baseline |
| Missing Hole V1 | inventory only (different mission) |

## 3. Quality Pareto (Scratch val)

```text
effnet_det_a0.25:  Q_D,val=0.8879  R=0.9767  FPR=0.1121
FULL:               Q_D,val=0.9159  R=0.9767  FPR=0.0841
unified (joint val): Q_D,val=0.8333  R=0.9434  FPR=0.1667  [not Scratch-comparable]
```

## 4. NX latency Pareto

```text
FULL p95:           246.4 ms
effnet_det_a0.25:    85.9 ms  (0.35×)
unified_classifier:  NOT PROBED (weights LFS; est. faster, uncharacterized)
```

## 5. Fresh holdout?

```text
NO
test_scratch — GearPro consumed
test_missing_tooth — Missing Hole V1 consumed 2026-09-13
unified — no independent sealed split
```

## 6. Primary candidate (Scratch)

```text
profile_id:   latency_degraded_v2_effnet_det
components:   EffNet-B0@384 + P2 detector@960, drop ResNet
fusion:       weighted α=0.25
threshold:    0.2653394325872992
```

[v3/v2-primary-candidate-freeze.md](capability-extraction/v3/v2-primary-candidate-freeze.md)

## 7. Formal evaluated?

```text
NO — blocked on fresh holdout
```

## 8. Registry status

Unchanged on `srtp-web`: `implemented=false`, `mission_approved=false`.

## 9. Runtime implemented?

```text
NO
```

## 10. Primary A reopened?

```text
NO
```

---

## Frozen research state (unchanged)

```text
Line 1: COMPLETE / REPRODUCED
A3 effectiveness: NOT ESTABLISHED
classifier_only_v1: REJECTED
Agent/runtime admission framework: ON MAINLINE (srtp-web)
```

## Next steps

1. Vision team: seal **new Scratch-only holdout** (not reuse test_scratch / test_missing_tooth).  
2. Optional: LFS-pull teammate weights for NX latency characterization (diagnostic only).  
3. Preregister one-shot formal eval for `latency_degraded_v2_effnet_det`.  
4. Missing Hole / unified: separate mission track if product expands beyond Scratch.
