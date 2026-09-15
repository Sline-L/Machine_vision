# V3-1 existing-feature FP veto — exploration status

```text
branch: experiment/v3-lightweight-fp-veto
mode: EXPLORATION
fresh holdout: NOT USED / STILL SEALED
test_scratch: NOT USED FOR TUNING
production registry: UNCHANGED
```

## Order obeyed

```text
V3-1 existing-feature lightweight veto   ← THIS ROUND
V3-2 distillation                        (only if V3-1 fails)
V3-3 ultra-light aux branch              (last)
```

## KPI results (val_scratch only)

| profile | Recall | FPR | Spec | Q_D | Mission Q_D≥0.70 |
| --- | ---: | ---: | ---: | ---: | --- |
| V2 baseline (frozen thr 0.265) | 0.977 | 0.112 | 0.888 | 0.888 | PASS |
| **V3-1 primary** logistic replace_score thr=0.845 | 0.930 | **0.056** | 0.944 | **0.930** | PASS |

```text
ΔQ_D vs V2 val: +0.042
ΔFPR vs V2 val: −0.056
```

Train@val-threshold also Mission-pass (sanity; not a second selection set).

Primary artifact: `primary_veto_model.json`  
Full Pareto: `pareto_report.json`

## Latency budget

```text
S1 budget extra ≤ ~10–12 ms vs V2
V3-1 veto: numpy logistic on 13 features (no new backbone)
```

Measured overhead: see `veto_overhead.json` (expect ≪1 ms).  
Integrated S1 p95 should remain ≈ V2 (~178 ms) ⇒ **gate headroom preserved** pending explicit NX S1 paired remeasure at freeze.

## Decision

```text
V3-1 CANDIDATE PROMISING
→ do NOT open fresh holdout yet
→ do NOT set mission_approved
→ next: package engineering freeze + NX S1 confirm
→ V3-2 NOT REQUIRED yet (V3-1 met val quality KPI direction)
```

## Honesty constraints

- Val success ≠ locked-domain / fresh-holdout generalization (V2 itself was strong on val, weak on consumed test).
- `test_scratch` remains diagnostic-only direction signal; never used to pick threshold here.
- Fresh holdout stays sealed until an explicit primary freeze + one-shot protocol.

## Spec link

[v3-lightweight-fp-veto-spec.md](v3-lightweight-fp-veto-spec.md)
